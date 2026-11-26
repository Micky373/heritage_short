"""Generate and validate cached Amharic narration audio for storyboard shots."""

from __future__ import annotations

import argparse
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

from pipeline.utils import (
    DEFAULT_CACHE,
    DEFAULT_STORYBOARD,
    DEFAULT_RUN_LOG,
    ROOT,
    is_cached,
    mark_cached,
    retry_api_call,
    run_logged_call,
    validate_storyboard,
)

DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "narration"
DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_VOICE = "Kore"
REQUEST_TIMEOUT_MS = 30_000
RETRY_ATTEMPTS = 2
RETRY_BASE_DELAY_SEC = 1.0
DEFAULT_MIN_REQUEST_INTERVAL_SEC = 20.0
MAX_DURATION_OVERRUN_SEC = 0.25
MAX_SPEEDUP_RATIO = 1.15
TRANSIENT_API_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _is_transient_api_error(error: Exception) -> bool:
    if not isinstance(error, APIError) or error.code not in TRANSIENT_API_STATUS_CODES:
        return False
    if error.code == 429:
        message = (error.message or str(error)).lower()
        if "per day" in message or "per-day" in message or "daily limit" in message:
            return False
    return True


def _retry_delay_sec(error: Exception, attempt: int) -> float:
    if isinstance(error, APIError) and error.code == 429:
        return 10.0
    return RETRY_BASE_DELAY_SEC * (2**attempt)


def _sleep_with_progress(seconds: float) -> None:
    print(f"  Retrying Gemini TTS in {seconds:.1f}s.", flush=True)
    time.sleep(seconds)


class RequestPacer:
    """Space TTS requests to respect the Gemini free-tier request rate."""

    def __init__(self, min_interval_sec: float) -> None:
        if min_interval_sec < 0:
            raise ValueError("minimum request interval cannot be negative")
        self.min_interval_sec = min_interval_sec
        self.last_request_at: float | None = None

    def wait(self) -> None:
        if self.last_request_at is not None:
            remaining = self.min_interval_sec - (
                time.monotonic() - self.last_request_at
            )
            if remaining > 0:
                print(
                    f"Waiting {remaining:.1f}s to respect the Gemini TTS request rate.",
                    flush=True,
                )
                time.sleep(remaining)
        self.last_request_at = time.monotonic()


def probe_audio_duration(path: str | Path) -> float:
    """Read an audio file duration in seconds using ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise FileNotFoundError("ffprobe is required to validate narration duration")

    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise ValueError(
            f"ffprobe could not read narration audio {path}: {result.stderr.strip()}"
        )
    try:
        duration = float(result.stdout.strip())
    except ValueError as error:
        raise ValueError(f"ffprobe returned an invalid duration for {path}") from error
    if duration <= 0:
        raise ValueError(f"Narration audio has a non-positive duration: {path}")
    return duration


def check_shot_duration(
    actual_sec: float,
    allowed_sec: float,
    *,
    tolerance_sec: float = MAX_DURATION_OVERRUN_SEC,
) -> None:
    """Reject empty audio or narration that exceeds its storyboard slot."""
    if actual_sec <= 0:
        raise ValueError("Narration audio duration must be positive")
    if allowed_sec <= 0:
        raise ValueError("Storyboard shot duration must be positive")
    if actual_sec > allowed_sec + tolerance_sec:
        raise ValueError(
            f"Narration is {actual_sec:.2f}s but the shot allows {allowed_sec:.2f}s "
            f"(maximum overrun {tolerance_sec:.2f}s)"
        )


def fit_audio_to_shot(path: str | Path, allowed_sec: float) -> float:
    """Speed up a small overrun without changing pitch; reject large overruns."""
    audio_path = Path(path)
    actual_sec = probe_audio_duration(audio_path)
    if actual_sec <= allowed_sec:
        check_shot_duration(actual_sec, allowed_sec)
        return actual_sec

    speedup = actual_sec / allowed_sec
    if speedup > MAX_SPEEDUP_RATIO:
        raise ValueError(
            f"Narration is {actual_sec:.2f}s for a {allowed_sec:.2f}s shot and "
            f"would need {speedup:.2f}x speed to fit; maximum is "
            f"{MAX_SPEEDUP_RATIO:.2f}x"
        )

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to fit overlong narration")

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=audio_path.parent,
            prefix=f".{audio_path.stem}.fit.",
            suffix=".wav",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(audio_path),
                "-af",
                f"atempo={speedup:.8f}",
                "-c:a",
                "pcm_s16le",
                temporary_path,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg could not fit narration audio: {result.stderr.strip()}"
            )
        fitted_duration = probe_audio_duration(temporary_path)
        check_shot_duration(fitted_duration, allowed_sec)
        os.replace(temporary_path, audio_path)
        temporary_path = None
        return fitted_duration
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _request_audio(
    client: genai.Client,
    *,
    model: str,
    voice: str,
    narration_am: str,
    tts_style: str,
    duration_sec: float,
) -> bytes:
    effective_style = (
        f"{tts_style}. Read the full narration naturally in about "
        f"{duration_sec:g} seconds."
    )

    def report_attempt(attempt: int) -> None:
        print(
            f"  TTS request attempt {attempt}/{RETRY_ATTEMPTS} ({model})...",
            flush=True,
        )

    response: Any = retry_api_call(
        lambda: client.interactions.create(
            model=model,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": narration_am,
                            "annotations": [
                                {
                                    "type": "speech_metadata",
                                    "style": effective_style,
                                }
                            ],
                        }
                    ],
                }
            ],
            response_format={"type": "audio"},
            generation_config={"speech_config": [{"voice": voice}]},
        ),
        retryable_exceptions=(APIError,),
        max_attempts=RETRY_ATTEMPTS,
        base_delay_sec=RETRY_BASE_DELAY_SEC,
        should_retry=_is_transient_api_error,
        retry_delay_sec=_retry_delay_sec,
        sleep=_sleep_with_progress,
        on_attempt=report_attempt,
    )
    output_audio = getattr(response, "output_audio", None)
    encoded_audio = getattr(output_audio, "data", None)
    if not isinstance(encoded_audio, str) or not encoded_audio:
        raise RuntimeError("Gemini TTS response did not contain audio data")
    audio = base64.b64decode(encoded_audio, validate=True)
    if not audio:
        raise RuntimeError("Gemini TTS response decoded to empty audio")
    return audio


def generate_shot_narration(
    shot: dict[str, Any],
    *,
    client: genai.Client,
    model: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    cache_path: str | Path = DEFAULT_CACHE,
    log_path: str | Path = DEFAULT_RUN_LOG,
    request_pacer: RequestPacer | None = None,
) -> Path:
    """Generate one shot's narration unless its unchanged valid output is cached."""
    shot_id = shot["shot_id"]
    duration_sec = float(shot["duration_sec"])
    audio_path = Path(output_dir) / f"{shot_id}.wav"
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    tts_style = shot["tts_style"]
    effective_style = (
        f"{tts_style}. Read the full narration naturally in about "
        f"{duration_sec:g} seconds."
    )
    inputs = {
        "model": model,
        "voice": voice,
        "narration_am": shot["narration_am"],
        "tts_style": effective_style,
        "duration_sec": duration_sec,
    }

    if is_cached("narration", inputs, shot_id=shot_id, cache_path=cache_path):
        if audio_path.is_file():
            duration = probe_audio_duration(audio_path)
            check_shot_duration(duration, duration_sec)
            print(f"{shot_id}: using cached narration ({duration:.2f}s).", flush=True)
            return audio_path

    print(f"{shot_id}: generating Amharic narration with {model}.", flush=True)
    if request_pacer is not None:
        request_pacer.wait()
    audio = run_logged_call(
        lambda: _request_audio(
            client,
            model=model,
            voice=voice,
            narration_am=shot["narration_am"],
            tts_style=tts_style,
            duration_sec=duration_sec,
        ),
        stage="narration",
        shot_id=shot_id,
        model=model,
        parameters={
            "voice": voice,
            "narration_am": shot["narration_am"],
            "tts_style": effective_style,
            "duration_sec": duration_sec,
        },
        seed=shot.get("seed"),
        cost_usd_est=None,
        log_path=log_path,
    )

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=audio_path.parent,
            prefix=f".{shot_id}.",
            suffix=".wav",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(audio)
        actual_duration = fit_audio_to_shot(temporary_path, duration_sec)
        os.replace(temporary_path, audio_path)
        temporary_path = None
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    mark_cached("narration", inputs, shot_id=shot_id, cache_path=cache_path)
    print(
        f"{shot_id}: saved {audio_path.relative_to(ROOT) if audio_path.is_relative_to(ROOT) else audio_path} "
        f"({actual_duration:.2f}s / {duration_sec:.2f}s).",
        flush=True,
    )
    return audio_path


def generate_narrations(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    cache_path: str | Path = DEFAULT_CACHE,
    log_path: str | Path = DEFAULT_RUN_LOG,
    model: str = DEFAULT_MODEL,
    voice: str = DEFAULT_VOICE,
) -> list[Path]:
    """Validate the storyboard and generate narration for each shot."""
    storyboard = validate_storyboard(storyboard_path)
    shot_ids = [shot["shot_id"] for shot in storyboard["shots"]]
    if len(shot_ids) != len(set(shot_ids)):
        raise ValueError("Storyboard shot_id values must be unique")

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env or the environment")

    request_pacer = RequestPacer(
        float(
            os.getenv(
                "GEMINI_TTS_MIN_INTERVAL_SEC",
                str(DEFAULT_MIN_REQUEST_INTERVAL_SEC),
            )
        )
    )
    client = genai.Client(
        api_key=api_key,
        http_options={
            "api_version": "v1beta",
            "timeout": REQUEST_TIMEOUT_MS,
            "retry_options": {"attempts": 1},
        },
    )
    outputs: list[Path] = []
    try:
        for shot in storyboard["shots"]:
            outputs.append(
                generate_shot_narration(
                    shot,
                    client=client,
                    model=model,
                    voice=voice,
                    output_dir=output_dir,
                    cache_path=cache_path,
                    log_path=log_path,
                    request_pacer=request_pacer,
                )
            )
    finally:
        client.close()
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Amharic shot narration")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    try:
        paths = generate_narrations(
            storyboard_path=args.storyboard,
            output_dir=args.output_dir,
            model=os.getenv("GEMINI_TTS_MODEL", DEFAULT_MODEL),
            voice=os.getenv("GEMINI_TTS_VOICE", DEFAULT_VOICE),
        )
    except Exception as error:
        print(f"Narration stage failed: {error}", file=sys.stderr, flush=True)
        return 1
    print(f"Generated or reused {len(paths)} narration clips.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Assemble narration with placeholder music over a black screen."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.music import DEFAULT_OUTPUT as DEFAULT_MUSIC
from pipeline.narration import (
    DEFAULT_OUTPUT_DIR as DEFAULT_NARRATION_DIR,
    check_shot_duration,
    probe_audio_duration,
)
from pipeline.utils import DEFAULT_STORYBOARD, ROOT, validate_storyboard

DEFAULT_OUTPUT = ROOT / "outputs" / "radio_cut.mp4"
FRAME_SIZE = "1280x720"
FRAME_RATE = 24
SAMPLE_RATE = 48_000


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.6f}".rstrip("0").rstrip(".")


def _run_ffprobe(path: Path) -> float:
    return probe_audio_duration(path)


def assemble_radio_cut(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    narration_dir: str | Path = DEFAULT_NARRATION_DIR,
    music_path: str | Path = DEFAULT_MUSIC,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    """Render a black-screen MP4 with padded voice clips and local music."""
    storyboard = validate_storyboard(storyboard_path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to assemble the radio cut")

    shots: list[dict[str, Any]] = storyboard["shots"]
    shot_ids = [shot["shot_id"] for shot in shots]
    if len(shot_ids) != len(set(shot_ids)):
        raise ValueError("Storyboard shot_id values must be unique")
    narration_paths: list[Path] = []
    for shot in shots:
        audio_path = Path(narration_dir) / f"{shot['shot_id']}.wav"
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing narration for {shot['shot_id']}: {audio_path}; "
                "run `make narration` first"
            )
        audio_duration = _run_ffprobe(audio_path)
        check_shot_duration(audio_duration, float(shot["duration_sec"]))
        narration_paths.append(audio_path)

    total_duration = sum(float(shot["duration_sec"]) for shot in shots)
    music_file = Path(music_path)
    if not music_file.is_absolute():
        music_file = ROOT / music_file
    if not music_file.is_file():
        raise FileNotFoundError(
            f"Missing local score: {music_file}; run `make music` first"
        )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=output.parent,
        prefix=f".{output.stem}.",
        suffix=".mp4",
        delete=False,
    ) as temporary_file:
        temporary_path = temporary_file.name

    try:
        ffmpeg_args = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={FRAME_SIZE}:r={FRAME_RATE}:d={_format_seconds(total_duration)}",
        ]
        for path in narration_paths:
            ffmpeg_args.extend(["-i", str(path)])
        ffmpeg_args.extend(["-i", str(music_file)])

        filter_parts: list[str] = []
        audio_labels: list[str] = []
        for index, shot in enumerate(shots, start=1):
            label = f"narration{index - 1}"
            audio_labels.append(f"[{label}]")
            filter_parts.append(
                f"[{index}:a:0]"
                f"aresample={SAMPLE_RATE},"
                "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad,atrim=duration={_format_seconds(float(shot['duration_sec']))},"
                f"asetpts=PTS-STARTPTS[{label}]"
            )
        filter_parts.append(
            f"{''.join(audio_labels)}concat=n={len(shots)}:v=0:a=1[voice]"
        )
        music_input_index = len(shots) + 1
        music_fade_start = max(0.0, total_duration - 1.0)
        filter_parts.append(
            f"[{music_input_index}:a:0]volume=0.65,"
            f"afade=t=in:st=0:d=1,"
            f"afade=t=out:st={_format_seconds(music_fade_start)}:d=1,"
            f"aresample={SAMPLE_RATE},"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[bed]"
        )
        filter_parts.append(
            "[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:"
            "normalize=0,alimiter=limit=0.95[aout]"
        )
        filter_complex = ";".join(filter_parts)
        ffmpeg_args.extend(
            [
                "-filter_complex",
                filter_complex,
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-t",
                _format_seconds(total_duration),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "stillimage",
                "-crf",
                "28",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                temporary_path,
            ]
        )
        result = subprocess.run(
            ffmpeg_args,
            capture_output=True,
            check=False,
            text=True,
            timeout=max(120, int(total_duration * 4)),
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed with exit code {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        output_duration = _run_ffprobe(Path(temporary_path))
        if abs(output_duration - total_duration) > 0.25:
            raise ValueError(
                f"Radio cut is {output_duration:.2f}s; expected "
                f"{total_duration:.2f}s"
            )
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    print(
        f"Radio cut rendered: {output} ({total_duration:.2f}s, black screen, "
        "local synthetic score).",
        flush=True,
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble narration radio cut")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--narration-dir", type=Path, default=DEFAULT_NARRATION_DIR)
    parser.add_argument("--music", type=Path, default=DEFAULT_MUSIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        assemble_radio_cut(
            storyboard_path=args.storyboard,
            narration_dir=args.narration_dir,
            music_path=args.music,
            output_path=args.output,
        )
    except Exception as error:
        print(f"Radio-cut stage failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

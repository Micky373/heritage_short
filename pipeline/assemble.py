"""Assemble local moving shots with narration and the synthetic score."""

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
from pipeline.visuals import DEFAULT_SHOT_DIR

DEFAULT_OUTPUT = ROOT / "outputs" / "film.mp4"
FRAME_RATE = 24
SAMPLE_RATE = 48_000
FRAME_SIZE = "1280x720"


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.6f}".rstrip("0").rstrip(".")


def _probe_video_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise FileNotFoundError("ffprobe is required to validate the assembled film")
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
    if result.returncode:
        raise RuntimeError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def assemble_film(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    shot_dir: str | Path = DEFAULT_SHOT_DIR,
    narration_dir: str | Path = DEFAULT_NARRATION_DIR,
    music_path: str | Path = DEFAULT_MUSIC,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> Path:
    storyboard = validate_storyboard(storyboard_path)
    shots: list[dict[str, Any]] = storyboard["shots"]
    shot_ids = [shot["shot_id"] for shot in shots]
    if len(shot_ids) != len(set(shot_ids)):
        raise ValueError("Storyboard shot_id values must be unique")

    shot_root = _resolve_path(shot_dir)
    narration_root = _resolve_path(narration_dir)
    music_file = _resolve_path(music_path)
    video_paths: list[Path] = []
    narration_paths: list[Path] = []
    for shot in shots:
        shot_id = shot["shot_id"]
        video_path = shot_root / f"{shot_id}.mp4"
        audio_path = narration_root / f"{shot_id}.wav"
        if not video_path.is_file():
            raise FileNotFoundError(
                f"Missing moving shot {video_path}; run `make shots` first."
            )
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing narration {audio_path}; run `make narration` first."
            )
        video_duration = _probe_video_duration(video_path)
        if abs(video_duration - float(shot["duration_sec"])) > 0.08:
            raise ValueError(
                f"{shot_id} video is {video_duration:.2f}s; expected "
                f"{float(shot['duration_sec']):.2f}s"
            )
        check_shot_duration(
            probe_audio_duration(audio_path),
            float(shot["duration_sec"]),
        )
        video_paths.append(video_path)
        narration_paths.append(audio_path)
    if not music_file.is_file():
        raise FileNotFoundError(
            f"Missing score {music_file}; run `make music` first."
        )

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to assemble the film")
    total_duration = sum(float(shot["duration_sec"]) for shot in shots)
    output = _resolve_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: str | None = None
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=output.parent,
        prefix=f".{output.stem}.",
        suffix=".mp4",
        delete=False,
    ) as temporary:
        temporary_path = temporary.name

    try:
        ffmpeg_args = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]
        for path in video_paths + narration_paths + [music_file]:
            ffmpeg_args.extend(["-i", str(path)])

        count = len(shots)
        music_index = count * 2
        filters: list[str] = []
        video_labels: list[str] = []
        audio_labels: list[str] = []
        for index, shot in enumerate(shots):
            video_label = f"video{index}"
            audio_label = f"audio{index}"
            video_labels.append(f"[{video_label}]")
            audio_labels.append(f"[{audio_label}]")
            filters.append(
                f"[{index}:v:0]fps={FRAME_RATE},scale={FRAME_SIZE},"
                f"setsar=1,format=yuv420p,setpts=PTS-STARTPTS[{video_label}]"
            )
            filters.append(
                f"[{count + index}:a:0]aresample={SAMPLE_RATE},"
                "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad,atrim=duration={_format_seconds(float(shot['duration_sec']))},"
                f"asetpts=PTS-STARTPTS[{audio_label}]"
            )
        filters.append(
            f"{''.join(video_labels)}concat=n={count}:v=1:a=0[vout]"
        )
        filters.append(
            f"{''.join(audio_labels)}concat=n={count}:v=0:a=1[voice]"
        )
        fade_start = max(0.0, total_duration - 1.5)
        filters.append(
            f"[{music_index}:a:0]volume=0.65,"
            "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"afade=t=in:st=0:d=1,"
            f"afade=t=out:st={_format_seconds(fade_start)}:d=1.5[bed]"
        )
        filters.append(
            "[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:"
            "normalize=0,alimiter=limit=0.95[aout]"
        )
        ffmpeg_args.extend(
            [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-t",
                _format_seconds(total_duration),
                "-r",
                str(FRAME_RATE),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "25",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
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
            timeout=max(180, int(total_duration * 10)),
        )
        if result.returncode:
            raise RuntimeError(
                f"ffmpeg failed with exit code {result.returncode}: "
                f"{result.stderr.strip()}"
            )
        actual_duration = _probe_video_duration(Path(temporary_path))
        if abs(actual_duration - total_duration) > 0.25:
            raise ValueError(
                f"Assembled film is {actual_duration:.2f}s; expected "
                f"{total_duration:.2f}s"
            )
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    print(
        f"Film assembled: {output} ({total_duration:.2f}s, local illustrated "
        "shots, Amharic narration, synthetic score).",
        flush=True,
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the finished short film")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--shot-dir", type=Path, default=DEFAULT_SHOT_DIR)
    parser.add_argument("--narration-dir", type=Path, default=DEFAULT_NARRATION_DIR)
    parser.add_argument("--music", type=Path, default=DEFAULT_MUSIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        assemble_film(
            storyboard_path=args.storyboard,
            shot_dir=args.shot_dir,
            narration_dir=args.narration_dir,
            music_path=args.music,
            output_path=args.output,
        )
    except Exception as error:
        print(f"Film assembly failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

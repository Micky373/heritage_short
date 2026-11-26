"""Assemble local moving shots with narration and the synthetic score."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
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
DEFAULT_PORTRAIT_OUTPUT = ROOT / "outputs" / "film_9x16.mp4"
FRAME_RATE = 24
SAMPLE_RATE = 48_000
OUTPUT_PROFILES = {
    "16:9": (1280, 720, DEFAULT_OUTPUT),
    "9:16": (720, 1280, DEFAULT_PORTRAIT_OUTPUT),
}


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


def _ass_time(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    whole_seconds, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _subtitle_chunks(text: str, width: int) -> list[str]:
    lines = textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return [
        r"\N".join(lines[index : index + 2])
        for index in range(0, len(lines), 2)
    ]


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _build_ass_script(
    storyboard: dict[str, Any],
    *,
    width: int,
    height: int,
    narration_durations: list[float] | None = None,
) -> str:
    if narration_durations is not None and len(narration_durations) != len(
        storyboard["shots"]
    ):
        raise ValueError("Narration durations must correspond to every storyboard shot")

    portrait = height > width
    wrap_width = 34 if portrait else 48
    font_size = 34 if portrait else 36
    margin = 42 if portrait else 48
    events: list[str] = []
    elapsed = 0.0
    for index, shot in enumerate(storyboard["shots"]):
        duration = float(shot["duration_sec"])
        caption_duration = (
            duration
            if narration_durations is None
            else min(duration, narration_durations[index])
        )
        chunks = _subtitle_chunks(shot["narration_en"], wrap_width)
        weights = [max(1, len(chunk.replace(r"\N", " "))) for chunk in chunks]
        total_weight = sum(weights)
        chunk_start = elapsed
        for chunk, weight in zip(chunks, weights):
            chunk_end = chunk_start + caption_duration * weight / total_weight
            safe_chunk = r"\N".join(
                _ass_escape(line) for line in chunk.split(r"\N")
            )
            events.append(
                "Dialogue: 0,"
                f"{_ass_time(chunk_start)},{_ass_time(chunk_end)},Caption,"
                f",0,0,0,,{safe_chunk}"
            )
            chunk_start = chunk_end
        elapsed += duration

    end_card = storyboard["project"]["end_card"]
    card_duration = float(end_card["duration_sec"])
    card_text = end_card["text"].replace(" | ", "\n")
    card_lines: list[str] = []
    for paragraph in card_text.splitlines():
        card_lines.extend(
            textwrap.wrap(
                paragraph,
                width=22 if portrait else 36,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    card_caption = r"\N".join(_ass_escape(line) for line in card_lines)
    events.append(
        "Dialogue: 0,"
        f"{_ass_time(elapsed)},{_ass_time(elapsed + card_duration)},EndCard,"
        f",0,0,0,,{card_caption}"
    )

    return "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
            "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,"
            "ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,"
            "MarginR,MarginV,Encoding",
            f"Style: Caption,Noto Sans Ethiopic,{font_size},&H00FFFFFF,"
            "&H000000FF,&HCC000000,&H88000000,0,0,0,0,100,100,0,0,1,2,1,"
            f"2,{margin},{margin},{margin},1",
            "Style: EndCard,Noto Sans Ethiopic,"
            f"{48 if portrait else 54},&H00FFFFFF,&H000000FF,&HCC000000,"
            "&H88000000,1,0,0,0,100,100,0,0,1,2,1,5,45,45,45,1",
            "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,"
            "Effect,Text",
            *events,
            "",
        ]
    )


def _escape_filter_path(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def assemble_film(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    shot_dir: str | Path = DEFAULT_SHOT_DIR,
    narration_dir: str | Path = DEFAULT_NARRATION_DIR,
    music_path: str | Path = DEFAULT_MUSIC,
    output_path: str | Path = DEFAULT_OUTPUT,
) -> list[Path]:
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
    narration_durations: list[float] = []
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
        audio_duration = probe_audio_duration(audio_path)
        check_shot_duration(audio_duration, float(shot["duration_sec"]))
        video_paths.append(video_path)
        narration_paths.append(audio_path)
        narration_durations.append(audio_duration)
    if not music_file.is_file():
        raise FileNotFoundError(
            f"Missing score {music_file}; run `make music` first."
        )

    shot_duration = sum(float(shot["duration_sec"]) for shot in shots)
    end_card_duration = float(storyboard["project"]["end_card"]["duration_sec"])
    total_duration = shot_duration + end_card_duration
    declared_duration = float(storyboard["project"]["target_duration_sec"])
    if abs(total_duration - declared_duration) > 0.25:
        raise ValueError(
            f"Storyboard duration is {declared_duration:.2f}s but shots plus "
            f"end card total {total_duration:.2f}s"
        )

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to assemble the film")
    configured_output = _resolve_path(output_path)
    output_paths: list[Path] = []
    for aspect_ratio in storyboard["project"]["aspect_ratios"]:
        profile_width, profile_height, default_output = OUTPUT_PROFILES[aspect_ratio]
        output = (
            configured_output
            if aspect_ratio == "16:9"
            else configured_output.with_name(
                f"{configured_output.stem}_9x16{configured_output.suffix}"
            )
        )
        if aspect_ratio == "9:16" and output_path == DEFAULT_OUTPUT:
            output = default_output
        output.parent.mkdir(parents=True, exist_ok=True)
        ass_script = _build_ass_script(
            storyboard,
            width=profile_width,
            height=profile_height,
            narration_durations=narration_durations,
        )
        temporary_ass: str | None = None
        temporary_video: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=output.parent,
                prefix=f".{output.stem}.",
                suffix=".ass",
                delete=False,
            ) as subtitle_file:
                temporary_ass = subtitle_file.name
                subtitle_file.write(ass_script)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=output.parent,
                prefix=f".{output.stem}.",
                suffix=".mp4",
                delete=False,
            ) as temporary:
                temporary_video = temporary.name

            ffmpeg_args = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
            ]
            for path in video_paths + narration_paths + [music_file]:
                ffmpeg_args.extend(["-i", str(path)])
            ffmpeg_args.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:s={profile_width}x{profile_height}:"
                    f"r={FRAME_RATE}:d={_format_seconds(end_card_duration)}",
                ]
            )

            count = len(shots)
            music_index = count * 2
            card_index = music_index + 1
            filters: list[str] = []
            video_labels: list[str] = []
            audio_labels: list[str] = []
            for index, shot in enumerate(shots):
                video_label = f"video{index}"
                audio_label = f"audio{index}"
                video_labels.append(f"[{video_label}]")
                audio_labels.append(f"[{audio_label}]")
                filters.append(
                    f"[{index}:v:0]fps={FRAME_RATE},"
                    f"scale={profile_width}:{profile_height}:"
                    "force_original_aspect_ratio=increase,"
                    f"crop={profile_width}:{profile_height},setsar=1,"
                    f"format=yuv420p,setpts=PTS-STARTPTS[{video_label}]"
                )
                filters.append(
                    f"[{count + index}:a:0]aresample={SAMPLE_RATE},"
                    "aformat=sample_fmts=fltp:channel_layouts=stereo,"
                    f"apad,atrim=duration={_format_seconds(float(shot['duration_sec']))},"
                    f"asetpts=PTS-STARTPTS[{audio_label}]"
                )
            filters.append(
                f"[{card_index}:v:0]fps={FRAME_RATE},setsar=1,"
                f"format=yuv420p,setpts=PTS-STARTPTS[card]"
            )
            filters.append(
                f"{''.join(video_labels)}[card]concat=n={count + 1}:v=1:a=0[base]"
            )
            subtitle_path = _escape_filter_path(Path(temporary_ass))
            filters.append(
                f"[base]subtitles=filename='{subtitle_path}':charenc=UTF-8[vout]"
            )
            filters.append(
                f"{''.join(audio_labels)}concat=n={count}:v=0:a=1[voice]"
            )
            fade_start = max(0.0, total_duration - 1.5)
            filters.append(
                f"[{music_index}:a:0]volume=0.65,"
                "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"apad=pad_dur={_format_seconds(end_card_duration)},"
                f"atrim=duration={_format_seconds(total_duration)},"
                "afade=t=in:st=0:d=1,"
                f"afade=t=out:st={_format_seconds(fade_start)}:d=1.5[bed]"
            )
            filters.append(
                f"[voice]apad=pad_dur={_format_seconds(end_card_duration)},"
                f"atrim=duration={_format_seconds(total_duration)}[voiceext]"
            )
            filters.append(
                "[voiceext]asplit=2[voiceprogram][voicesidechain]"
            )
            filters.append(
                "[bed][voicesidechain]sidechaincompress=threshold=0.04:ratio=8:"
                "attack=20:release=350:makeup=1[ducked]"
            )
            filters.append(
                "[voiceprogram][ducked]amix=inputs=2:duration=first:"
                "dropout_transition=0:normalize=0,alimiter=limit=0.95[aout]"
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
                    temporary_video,
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
                    f"ffmpeg failed for {aspect_ratio} with exit code "
                    f"{result.returncode}: {result.stderr.strip()}"
                )
            actual_duration = _probe_video_duration(Path(temporary_video))
            if abs(actual_duration - total_duration) > 0.25:
                raise ValueError(
                    f"Assembled {aspect_ratio} film is {actual_duration:.2f}s; "
                    f"expected {total_duration:.2f}s"
                )
            os.replace(temporary_video, output)
            temporary_video = None
        finally:
            for temporary_path in (temporary_ass, temporary_video):
                if temporary_path is not None and os.path.exists(temporary_path):
                    os.unlink(temporary_path)

        print(
            f"Film assembled: {output} ({profile_width}x{profile_height}, "
            f"{total_duration:.2f}s, English subtitles and AI end card).",
            flush=True,
        )
        output_paths.append(output)
    return output_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the finished short film")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--shot-dir", type=Path, default=DEFAULT_SHOT_DIR)
    parser.add_argument("--narration-dir", type=Path, default=DEFAULT_NARRATION_DIR)
    parser.add_argument("--music", type=Path, default=DEFAULT_MUSIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        outputs = assemble_film(
            storyboard_path=args.storyboard,
            shot_dir=args.shot_dir,
            narration_dir=args.narration_dir,
            music_path=args.music,
            output_path=args.output,
        )
    except Exception as error:
        print(f"Film assembly failed: {error}", file=sys.stderr, flush=True)
        return 1
    print(f"Rendered {len(outputs)} film exports.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

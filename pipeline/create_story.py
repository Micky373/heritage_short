"""Interactively turn an Amharic story into a validated storyboard and film."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

from pipeline.utils import (
    DEFAULT_RUN_LOG,
    DEFAULT_STORYBOARD,
    ROOT,
    retry_api_call,
    run_logged_call,
    validate_storyboard,
)

DEFAULT_MODEL = "gemini-3.8-flash"
TEXT_REQUEST_TIMEOUT_MS = 30_000
RETRY_ATTEMPTS = 2
RETRY_BASE_DELAY_SEC = 1.0
TRANSIENT_API_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _is_transient_api_error(error: Exception) -> bool:
    return isinstance(error, APIError) and error.code in TRANSIENT_API_STATUS_CODES


def read_story_multiline() -> str:
    """Read an interactive story, accepting multiple lines until a blank line."""
    print("Enter your story in Amharic. Finish with a blank line:")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line.strip())
    story = "\n".join(lines).strip()
    if not story:
        raise ValueError("A story is required")
    return story


def read_text(prompt: str, default: str | None = None) -> str:
    """Prompt for a required text value, with an optional default."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if value:
        return value
    if default:
        return default
    raise ValueError(f"{prompt} is required")


def allocate_shot_durations(
    target_duration_sec: float,
    shot_count: int,
) -> list[float]:
    """Allocate the shot portion of the film duration evenly across shots."""
    if target_duration_sec <= 3:
        raise ValueError("target duration must be greater than the 3-second end card")
    if shot_count < 1:
        raise ValueError("shot count must be positive")

    available = target_duration_sec - 3.0
    total_hundredths = round(available * 100)
    base, remainder = divmod(total_hundredths, shot_count)
    durations: list[float] = []
    for index in range(shot_count):
        hundredths = base + (1 if index < remainder else 0)
        durations.append(hundredths / 100)
    return durations


def extract_json_object(response_text: str) -> dict[str, Any]:
    """Extract a JSON object from a model response, allowing Markdown fences."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Gemini must return a JSON object")
    return parsed


def build_storyboard(
    generated: dict[str, Any],
    *,
    title: str,
    duration_sec: float,
    story_style: str,
    shot_count: int,
) -> dict[str, Any]:
    """Merge generated content with required project values and stable shot timing."""
    durations = allocate_shot_durations(duration_sec, shot_count)
    generated_shots = generated.get("shots")
    if not isinstance(generated_shots, list):
        raise ValueError("Gemini response is missing an array of shots")
    if len(generated_shots) != shot_count:
        raise ValueError(
            f"Gemini generated {len(generated_shots)} shots; expected {shot_count}"
        )

    shots: list[dict[str, Any]] = []
    for index, (raw_shot, duration) in enumerate(
        zip(generated_shots, durations, strict=True),
        start=1,
    ):
        if not isinstance(raw_shot, dict):
            raise ValueError(f"Shot {index} is not a JSON object")
        shot = dict(raw_shot)
        shot["shot_id"] = f"shot_{index:02d}"
        shot["duration_sec"] = duration
        shot["seed"] = 1000 + index
        shots.append(shot)

    generated_music = generated.get("music")
    if not isinstance(generated_music, dict):
        raise ValueError("Gemini response is missing a music object")

    generated_characters = generated.get("characters")
    if not isinstance(generated_characters, dict):
        raise ValueError("Gemini response is missing a characters object")

    storyboard: dict[str, Any] = {
        "project": {
            "title": title,
            "language": "am",
            "target_duration_sec": duration_sec,
            "aspect_ratios": ["9:16", "16:9"],
            "end_card": {
                "duration_sec": 3,
                "text": "Created with AI | በሰው ሰራሽ አስተውሎት (AI) የተዘጋጀ",
            },
        },
        "style_block": story_style,
        "characters": generated_characters,
        "music": {
            "cue_id": generated_music.get("cue_id", "cue_main_score"),
            "caption": generated_music.get(
                "caption",
                "Warm reflective Amharic instrumental score, no vocals",
            ),
            "tempo_bpm": generated_music.get("tempo_bpm", 82),
            "key": generated_music.get("key", "C major"),
            "duration_sec": duration_sec - 3,
            "seed": generated_music.get("seed", 4201),
        },
        "shots": shots,
    }
    return storyboard


def create_storyboard_prompt(
    story: str,
    *,
    title: str,
    duration_sec: float,
    story_style: str,
    shot_count: int,
) -> str:
    durations = allocate_shot_durations(duration_sec, shot_count)
    return f"""
Create a heritage-short storyboard for this Amharic story.

Project title: {title}
Target duration: {duration_sec:g} seconds, including a 3-second end card.
Shot count: {shot_count}
Shot durations: {durations}
Visual style: {story_style}

Return only one valid JSON object. Do not use Markdown fences or comments.
Use exactly these top-level keys: project, style_block, characters, music, shots.
Use exactly these character keys: father, young_son, adult_narrator.
The Amharic and English character descriptions must remain appropriate for the
story and may adapt clothing, age, and setting.

Each shot object must contain exactly:
shot_id, duration_sec, shot_type, reason, narration_am, narration_en,
tts_style, keyframe_prompt, motion_prompt, camera_movement, seed.

Rules:
- narration_am must be faithful Amharic narration from the supplied story.
- narration_en must be an accurate English subtitle translation.
- Duration values must exactly match: {durations}
- shot_id values must be shot_01 through shot_{shot_count:02d}.
- Seed values must be positive integers.
- Do not copy the source project's unrelated people or setting.
- Keep the language, setting, characters, and emotional arc consistent.
- End the narration with a brief visual ending, but do not insert "Created with AI"
  into the final shot because the pipeline already adds an AI disclosure card.
- Keep visual prompts concrete, safe, and suitable for a 16:9 and 9:16 crop.

Source story:
\"\"\"
{story}
\"\"\"
"""


def generate_storyboard(
    story: str,
    *,
    title: str,
    duration_sec: float,
    story_style: str,
    shot_count: int,
    model: str,
    api_key: str,
) -> dict[str, Any]:
    prompt = create_storyboard_prompt(
        story,
        title=title,
        duration_sec=duration_sec,
        story_style=story_style,
        shot_count=shot_count,
    )
    client = genai.Client(
        api_key=api_key,
        http_options={
            "api_version": "v1beta",
            "timeout": TEXT_REQUEST_TIMEOUT_MS,
            "retry_options": {"attempts": 1},
        },
    )
    try:
        print(f"Generating storyboard with {model}...", flush=True)

        def operation() -> str:
            response = client.models.generate_content(model=model, contents=prompt)
            if not response.text or not response.text.strip():
                raise RuntimeError("Gemini text response was empty")
            return response.text.strip()

        response_text = run_logged_call(
            lambda: retry_api_call(
                operation,
                retryable_exceptions=(APIError,),
                max_attempts=RETRY_ATTEMPTS,
                base_delay_sec=RETRY_BASE_DELAY_SEC,
                should_retry=_is_transient_api_error,
            ),
            stage="storyboard",
            shot_id=None,
            model=model,
            parameters={"prompt": prompt},
        )
        generated = extract_json_object(response_text)
        return build_storyboard(
            generated,
            title=title,
            duration_sec=duration_sec,
            story_style=story_style,
            shot_count=shot_count,
        )
    finally:
        client.close()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON safely so a failed write cannot corrupt the storyboard."""
    temporary_path: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            Path(temporary_path).unlink(missing_ok=True)


def save_storyboard(storyboard: dict[str, Any], storyboard_path: Path) -> None:
    if storyboard_path.exists():
        backup_path = storyboard_path.with_suffix(".previous.json")
        shutil.copy2(storyboard_path, backup_path)
        print(f"Previous storyboard saved to {backup_path}", flush=True)
    atomic_write_json(storyboard_path, storyboard)


def run_film_pipeline() -> int:
    make = shutil.which("make")
    if make is None:
        print("Make is required to build the film.", file=sys.stderr)
        return 2
    result = subprocess.run([make, "film"], cwd=ROOT, check=False)
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and build an Amharic heritage short from your story",
    )
    parser.add_argument("--title", help="Project title")
    parser.add_argument(
        "--story-file",
        type=Path,
        help="Read the Amharic story from a text file instead of interactive input",
    )
    parser.add_argument("--shots", type=int, default=9, help="Number of shots")
    parser.add_argument(
        "--duration",
        type=float,
        default=78,
        help="Target film duration including the 3-second end card",
    )
    parser.add_argument(
        "--style",
        default=(
            "Warm cinematic realism in Ethiopia, gentle golden-hour light, "
            "soft shadows, natural colors, 35mm film grain, and compositions "
            "safe for both 9:16 and 16:9 framing"
        ),
        help="Visual style applied to the generated storyboard",
    )
    parser.add_argument(
        "--storyboard",
        type=Path,
        default=DEFAULT_STORYBOARD,
        help="Storyboard file to replace",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Generate and validate the storyboard without running make film",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT / ".env")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print(
            "GEMINI_API_KEY is missing; set it in .env or the environment.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.story_file:
            story = args.story_file.read_text(encoding="utf-8").strip()
            if not story:
                raise ValueError(f"The story file is empty: {args.story_file}")
        else:
            story = read_story_multiline()

        title = args.title or read_text("Story title", "My Amharic Story")
        if args.shots < 1:
            raise ValueError("shot count must be positive")
        if args.duration <= 3:
            raise ValueError("duration must be greater than 3 seconds")

        model = os.getenv("GEMINI_TEXT_MODEL", DEFAULT_MODEL)
        storyboard = generate_storyboard(
            story,
            title=title,
            duration_sec=args.duration,
            story_style=args.style,
            shot_count=args.shots,
            model=model,
            api_key=api_key,
        )
        save_storyboard(storyboard, args.storyboard)
        validate_storyboard(args.storyboard)
        print(
            f"Validated storyboard: {args.storyboard} "
            f"({args.shots} shots, {args.duration:g}s)",
            flush=True,
        )

        if args.no_build:
            print("Storyboard generated. Run 'make film' when ready.", flush=True)
            return 0
        return run_film_pipeline()
    except (OSError, ValueError, json.JSONDecodeError, APIError, RuntimeError) as error:
        print(f"Could not create the story: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

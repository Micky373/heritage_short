"""Synthesize a deterministic, local placeholder score from storyboard metadata."""

from __future__ import annotations

import argparse
import array
import math
import os
import re
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from pipeline.utils import (
    DEFAULT_CACHE,
    DEFAULT_STORYBOARD,
    ROOT,
    is_cached,
    mark_cached,
    validate_storyboard,
)

DEFAULT_OUTPUT = ROOT / "outputs" / "music" / "main_score.wav"
SAMPLE_RATE = 22_050
RENDERER_VERSION = 1
NOTE_SEMITONES = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}


def _root_midi(key: str) -> int:
    match = re.match(r"\s*([A-Ga-g](?:#|b)?)", key)
    if match is None:
        raise ValueError(f"Unsupported music key: {key!r}")
    note = match.group(1).upper()
    if note.endswith("B") and len(note) == 2:
        note = note[0] + "B"
    if note not in NOTE_SEMITONES:
        raise ValueError(f"Unsupported music key: {key!r}")
    return 60 + NOTE_SEMITONES[note]


def _midi_frequency(note: int) -> float:
    return 440.0 * (2 ** ((note - 69) / 12))


def _render_samples(music: dict[str, Any]) -> array.array[int]:
    duration = float(music["duration_sec"])
    bpm = float(music["tempo_bpm"])
    if duration <= 0 or bpm <= 0:
        raise ValueError("Music duration and tempo must be positive")

    root = _root_midi(music["key"])
    pentatonic = [root + interval for interval in (0, 2, 4, 7, 9)]
    melody = [pentatonic[index] for index in (0, 1, 2, 4, 3, 2, 1, 2)]
    melody_hz = [_midi_frequency(note) for note in melody]
    root_hz = _midi_frequency(root - 12)
    fifth_hz = _midi_frequency(root - 5)
    beat_sec = 60.0 / bpm
    phase_offset = int(music.get("seed", 0)) % len(melody)
    frame_count = round(duration * SAMPLE_RATE)
    samples = array.array("h")
    for frame in range(frame_count):
        seconds = frame / SAMPLE_RATE
        beat_position = seconds / beat_sec
        beat_index = int(beat_position)
        beat_phase = beat_position - beat_index
        frequency = melody_hz[(beat_index + phase_offset) % len(melody)]
        envelope = min(1.0, beat_phase * 30.0) * math.exp(-3.2 * beat_phase)
        pluck = (
            math.sin(2 * math.pi * frequency * seconds)
            + 0.32 * math.sin(4 * math.pi * frequency * seconds)
            + 0.12 * math.sin(6 * math.pi * frequency * seconds)
        )
        measure_phase = (seconds % (beat_sec * 4)) / (beat_sec * 4)
        pad = (
            math.sin(2 * math.pi * root_hz * seconds)
            + 0.72 * math.sin(2 * math.pi * fifth_hz * seconds)
        ) * (0.5 + 0.5 * math.sin(math.pi * measure_phase))
        fade_in = min(1.0, seconds / 1.5)
        fade_out = min(1.0, max(0.0, duration - seconds) / 2.0)
        sample = (0.075 * pluck * envelope + 0.018 * pad) * fade_in * fade_out
        samples.append(round(max(-1.0, min(1.0, sample)) * 32767))
    if samples.itemsize != 2:
        raise RuntimeError("The current platform does not support 16-bit audio samples")
    return samples


def synthesize_score(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    output_path: str | Path = DEFAULT_OUTPUT,
    cache_path: str | Path = DEFAULT_CACHE,
) -> Path:
    storyboard = validate_storyboard(storyboard_path)
    music = storyboard["music"]
    output = Path(output_path)
    if not output.is_absolute():
        output = ROOT / output
    inputs = {"renderer_version": RENDERER_VERSION, "music": music}
    if output.is_file() and is_cached("music", inputs, cache_path=cache_path):
        print(f"Music stage: using cached local score {output}.", flush=True)
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    samples = _render_samples(music)
    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent,
            prefix=f".{output.stem}.",
            suffix=".wav",
            delete=False,
        ) as temporary:
            temporary_path = temporary.name
        with wave.open(temporary_path, "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(SAMPLE_RATE)
            audio_file.writeframes(samples.tobytes())
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)

    with wave.open(str(output), "rb") as audio_file:
        actual_duration = audio_file.getnframes() / audio_file.getframerate()
    expected_duration = float(music["duration_sec"])
    if abs(actual_duration - expected_duration) > 1 / SAMPLE_RATE:
        raise ValueError(
            f"Local score is {actual_duration:.3f}s; expected "
            f"{expected_duration:.3f}s"
        )
    mark_cached("music", inputs, cache_path=cache_path)
    print(
        f"Local synthetic score rendered: {output} ({actual_duration:.2f}s, "
        f"{music['tempo_bpm']:g} BPM, {music['key']}).",
        flush=True,
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local placeholder score")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        synthesize_score(
            storyboard_path=args.storyboard,
            output_path=args.output,
        )
    except Exception as error:
        print(f"Music stage failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

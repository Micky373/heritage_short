"""Create local illustrated reference sheets, keyframes, and moving shots."""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pipeline.utils import (
    DEFAULT_CACHE,
    DEFAULT_STORYBOARD,
    ROOT,
    file_hash,
    is_cached,
    mark_cached,
    validate_storyboard,
)

DEFAULT_REFERENCE = ROOT / "outputs" / "refs" / "character_sheet.png"
DEFAULT_KEYFRAME_DIR = ROOT / "outputs" / "keyframes"
DEFAULT_SHOT_DIR = ROOT / "outputs" / "shots"
WIDTH = 1920
HEIGHT = 1080
RENDERER_VERSION = 1
FPS = 24

PALETTE = {
    "ink": "#28332e",
    "cream": "#f6edda",
    "gold": "#f2bc70",
    "sun": "#ffe0a0",
    "earth": "#806b55",
    "leaf": "#526c58",
    "leaf_light": "#78906a",
    "stone": "#c5ad8b",
    "blue": "#4c7592",
    "shirt": "#f1e8d5",
    "blazer": "#54594d",
    "skin": "#9b654a",
    "skin_light": "#bc8060",
    "hair": "#222420",
    "trouser": "#393f3c",
    "window": "#d8d0b4",
}


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _svg_start(title: str, description: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        f"<title>{html.escape(title)}</title>"
        f"<desc>{html.escape(description)}</desc>"
        "<defs>"
        '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#f6d69d"/>'
        '<stop offset="0.62" stop-color="#eeb578"/>'
        '<stop offset="1" stop-color="#cb9670"/>'
        "</linearGradient>"
        '<linearGradient id="windowLight" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#fff0bd"/>'
        '<stop offset="1" stop-color="#d79862"/>'
        "</linearGradient>"
        "</defs>"
    )


def _ground_svg() -> str:
    return (
        '<rect width="1920" height="1080" fill="url(#sky)"/>'
        '<circle cx="1520" cy="210" r="118" fill="#ffe0a0" opacity=".8"/>'
        '<path d="M0 680 Q350 610 700 680 T1400 650 T1920 660 V1080 H0Z" '
        'fill="#64705a"/>'
        '<path d="M820 690 L1130 690 L1690 1080 H250Z" fill="#b9a17f"/>'
        '<path d="M910 700 L1025 700 L1190 1080 H735Z" fill="#d2bd98"/>'
        '<path d="M0 915 Q420 840 760 940 T1450 910 T1920 925" '
        'fill="none" stroke="#8c7c62" stroke-width="14" opacity=".55"/>'
    )


def _trees_svg() -> str:
    pieces: list[str] = []
    for x, y, scale in (
        (90, 735, 1.15),
        (340, 650, 0.82),
        (1580, 660, 0.95),
        (1830, 735, 1.2),
    ):
        pieces.append(
            f'<g transform="translate({x} {y}) scale({scale})">'
            '<path d="M-18 20 Q0 -135 7 -290" fill="none" '
            'stroke="#594d3d" stroke-width="24" stroke-linecap="round"/>'
            '<path d="M2 -180 Q-85 -245 -116 -320 M4 -225 Q75 -285 110 -350 '
            'M-2 -135 Q-70 -175 -126 -198" fill="none" stroke="#594d3d" '
            'stroke-width="12" stroke-linecap="round"/>'
            '<ellipse cx="-105" cy="-326" rx="98" ry="36" fill="#526c58"/>'
            '<ellipse cx="93" cy="-350" rx="112" ry="42" fill="#617b5e"/>'
            '<ellipse cx="-119" cy="-204" rx="88" ry="32" fill="#78906a"/>'
            '<ellipse cx="0" cy="-275" rx="118" ry="47" fill="#6c825f"/>'
            "</g>"
        )
    return "".join(pieces)


def _character_svg(kind: str, x: int, foot_y: int, scale: float = 1.0, gesture: bool = False) -> str:
    is_son = kind == "young_son"
    is_adult = kind == "adult_narrator"
    coat = PALETTE["blue"] if is_son else (
        "#343b3c" if is_adult else PALETTE["blazer"]
    )
    legs = PALETTE["trouser"]
    bag = (
        '<path d="M119 -283 Q160 -270 160 -205 L132 -180 L108 -251Z" '
        'fill="#79583e" stroke="#4d4235" stroke-width="5"/>'
        if is_son
        else (
            '<path d="M112 -270 Q160 -245 154 -178 L123 -159 L96 -248Z" '
            'fill="#79583e" stroke="#4d4235" stroke-width="5"/>'
            if not is_adult else ""
        )
    )
    arm = (
        '<path d="M111 -278 Q180 -252 202 -208" fill="none" '
        'stroke="#9b654a" stroke-width="23" stroke-linecap="round"/>'
        if gesture
        else ""
    )
    height_scale = 0.82 if is_son else 1.0
    scale *= height_scale
    shirt = (
        '<path d="M-21 -321 L0 -291 L21 -321 L12 -174 L-12 -174Z" '
        'fill="#f1e8d5"/>'
        if not is_son and not is_adult
        else (
            '<path d="M-17 -310 L0 -288 L17 -310 L9 -178 L-9 -178Z" '
            'fill="#f1e8d5"/>'
            if is_son else ""
        )
    )
    return (
        f'<g transform="translate({x} {foot_y}) scale({scale})">'
        f'<path d="M-42 -156 L-13 -156 L-20 -20 L-52 0 L-66 -10Z" fill="{legs}"/>'
        f'<path d="M13 -156 L43 -156 L63 -10 L43 0 L13 -22Z" fill="{legs}"/>'
        '<path d="M-66 -10 Q-39 -24 -15 -10 L-8 1 H-68Z" fill="#44392f"/>'
        '<path d="M38 -10 Q63 -24 86 -8 L91 2 H39Z" fill="#44392f"/>'
        f'<path d="M-58 -322 Q0 -344 58 -322 L76 -168 Q0 -139 -76 -168Z" fill="{coat}"/>'
        f"{shirt}{bag}"
        '<path d="M-54 -296 Q-82 -268 -87 -212" fill="none" '
        'stroke="#9b654a" stroke-width="22" stroke-linecap="round"/>'
        f"{arm if gesture else ''}"
        '<path d="M-24 -340 L-24 -316 L0 -298 L24 -316 L24 -340Z" '
        'fill="#9b654a"/>'
        '<ellipse cx="0" cy="-391" rx="54" ry="66" fill="#9b654a"/>'
        '<path d="M-53 -397 Q-54 -465 0 -461 Q54 -458 54 -399 '
        'Q24 -428 4 -429 Q-23 -425 -53 -397Z" fill="#222420"/>'
        '<ellipse cx="-20" cy="-390" rx="4" ry="5" fill="#252522"/>'
        '<ellipse cx="19" cy="-390" rx="4" ry="5" fill="#252522"/>'
        '<path d="M-16 -362 Q0 -351 17 -363" fill="none" stroke="#673f32" '
        'stroke-width="4" stroke-linecap="round"/>'
        '<path d="M-43 -404 Q-22 -419 -4 -406 M7 -406 Q28 -419 45 -403" '
        'fill="none" stroke="#252522" stroke-width="6" stroke-linecap="round"/>'
        "</g>"
    )


def _reference_svg(storyboard: dict[str, Any]) -> str:
    characters = list(storyboard["characters"].items())
    body = [
        '<rect width="1920" height="1080" fill="#f3ead7"/>',
        '<rect x="74" y="58" width="1772" height="964" rx="38" '
        'fill="#fffaf0" stroke="#c8b99c" stroke-width="3"/>',
        '<text x="120" y="142" font-family="sans-serif" font-size="46" '
        'font-weight="700" fill="#28332e">MORNING STEPS IN SIX KILO</text>',
        '<text x="120" y="190" font-family="sans-serif" font-size="25" '
        'fill="#6b705f">LOCAL CHARACTER REFERENCE · WARM DAWN PALETTE</text>',
    ]
    card_width = 500
    for index, (name, character) in enumerate(characters[:3]):
        x = 120 + index * 560
        body.extend(
            [
                f'<rect x="{x}" y="245" width="{card_width}" height="690" rx="26" '
                'fill="#efe2c9" stroke="#d3c3a7" stroke-width="2"/>',
                f'<rect x="{x + 24}" y="270" width="452" height="485" rx="18" '
                'fill="url(#sky)"/>',
                f'<circle cx="{x + 392}" cy="350" r="52" fill="#ffe0a0" opacity=".8"/>',
                f'<path d="M{x + 24} 630 Q{x + 170} 565 {x + 476} 650 '
                f'V755 H{x + 24}Z" fill="#64705a"/>',
                _character_svg(
                    name,
                    x + 250,
                    715,
                    1.0 if name != "young_son" else 1.12,
                ),
                f'<text x="{x + 32}" y="815" font-family="sans-serif" '
                f'font-size="31" font-weight="700" fill="#28332e">'
                f'{html.escape(name.replace("_", " ").title())}</text>',
                f'<text x="{x + 32}" y="860" font-family="sans-serif" '
                f'font-size="20" fill="#4a5149">'
                f'{html.escape(character["id"])}</text>',
                f'<text x="{x + 32}" y="899" font-family="sans-serif" '
                f'font-size="18" fill="#4a5149">'
                f'{html.escape(character["description"][:52])}…</text>',
            ]
        )
    return _svg_start("Character reference sheet", storyboard["style_block"]) + "".join(body) + "</svg>"


def _shot_svg(shot: dict[str, Any]) -> str:
    shot_id = shot["shot_id"]
    scene = [_ground_svg(), _trees_svg()]
    if shot_id in {"shot_01", "shot_02", "shot_03", "shot_04", "shot_05"}:
        scene.append(
            '<path d="M1110 625 L1470 625 L1710 675 L1030 675Z" '
            'fill="#d0bd9b" opacity=".7"/>'
        )
        if shot_id == "shot_01":
            scene.append(_character_svg("father", 840, 890, 1.08))
            scene.append(_character_svg("young_son", 1040, 875, 1.0))
        elif shot_id == "shot_02":
            scene.append(_character_svg("father", 780, 970, 1.43))
            scene.append(_character_svg("young_son", 1100, 965, 1.3))
            scene.append(
                '<path d="M1390 670 V420 H1730 V670" fill="#d5c6a9" '
                'stroke="#766c5b" stroke-width="14"/>'
                '<path d="M1440 670 V500 H1680 V670" fill="#a88e6b"/>'
            )
        elif shot_id == "shot_03":
            scene.append(_character_svg("father", 710, 1110, 1.95))
            scene.append(_character_svg("young_son", 1130, 1110, 1.75))
        elif shot_id == "shot_04":
            scene.append(_character_svg("father", 760, 1040, 1.62))
            scene.append(_character_svg("young_son", 1120, 1040, 1.52, gesture=True))
        else:
            scene.append(_character_svg("young_son", 1010, 1120, 2.45))
            scene.append(
                '<g fill="#fff3d4" opacity=".62" font-family="serif" font-size="58">'
                '<text x="320" y="365">3 × 4</text><text x="1430" y="475">12</text>'
                '<text x="450" y="670">+ 5</text></g>'
            )
    elif shot_id in {"shot_06", "shot_07", "shot_08"}:
        scene.extend(
            [
                '<rect x="1060" y="175" width="620" height="500" rx="18" '
                'fill="#d7d0b7" stroke="#766c5b" stroke-width="20"/>',
                '<rect x="1092" y="207" width="556" height="436" '
                'fill="url(#windowLight)"/>',
            ]
        )
        if shot_id == "shot_06":
            scene.extend(
                [
                    '<rect x="270" y="760" width="1110" height="75" rx="18" '
                    'fill="#765b43"/>',
                    '<rect x="630" y="570" width="450" height="250" rx="18" '
                    'fill="#343b3c"/><rect x="660" y="595" width="390" height="190" '
                    'fill="#cfdbd0"/>',
                    '<path d="M700 735 L760 690 L820 710 L880 646 L945 666 '
                    'L1010 620" fill="none" stroke="#648c71" stroke-width="12"/>',
                    _character_svg("adult_narrator", 430, 1080, 2.05),
                ]
            )
        elif shot_id == "shot_07":
            scene.extend(
                [
                    '<rect x="230" y="760" width="1440" height="250" rx="28" '
                    'fill="#80664a"/>',
                    '<path d="M430 805 L895 790 L990 950 L510 970Z" '
                    'fill="#f5eddc" stroke="#bcae92" stroke-width="8"/>',
                    '<path d="M520 850 L835 835 M535 892 L810 880 M560 933 L790 920" '
                    'stroke="#7a806f" stroke-width="9"/>',
                    '<rect x="1080" y="600" width="450" height="300" rx="22" '
                    'fill="#343b3c"/><rect x="1110" y="630" width="390" height="230" '
                    'fill="#dce4d9"/>',
                    '<path d="M1150 815 L1215 760 L1280 785 L1345 700 L1410 730 '
                    'L1470 670" fill="none" stroke="#648c71" stroke-width="12"/>',
                    '<ellipse cx="1600" cy="760" rx="88" ry="28" fill="#e4d7bf"/>'
                    '<path d="M1525 760 L1545 870 Q1600 900 1655 870 L1675 760Z" '
                    'fill="#f3ead7" stroke="#aa9a7f" stroke-width="8"/>'
                    '<path d="M1655 785 Q1730 790 1700 845 Q1680 865 1655 850" '
                    'fill="none" stroke="#aa9a7f" stroke-width="12"/>',
                ]
            )
        else:
            scene.append(_character_svg("adult_narrator", 800, 1110, 2.25))
    else:
        scene.append(
            '<path d="M650 695 L1270 695 L1820 1080 H100Z" fill="#d2bd98"/>'
            '<path d="M850 705 L1080 705 L1250 1080 H650Z" fill="#e0cba5"/>'
            '<path d="M0 900 Q500 820 850 935 M1330 900 Q1650 830 1920 920" '
            'fill="none" stroke="#8c7c62" stroke-width="16" opacity=".6"/>'
        )
    description = f'{shot["keyframe_prompt"]} | {shot["reason"]}'
    return _svg_start(shot_id, description) + "".join(scene) + "</svg>"


def _svg_to_png(svg_path: Path, png_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to rasterize local SVG artwork")
    png_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "svg_pipe",
            "-i",
            str(svg_path),
            "-frames:v",
            "1",
            str(png_path),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(f"Could not rasterize {svg_path}: {result.stderr.strip()}")


def _cached_outputs(
    stage: str,
    inputs: dict[str, Any],
    outputs: list[Path],
    *,
    shot_id: str | None,
    cache_path: str | Path,
) -> bool:
    return all(path.is_file() for path in outputs) and is_cached(
        stage, inputs, shot_id=shot_id, cache_path=cache_path
    )


def generate_reference_sheet(
    storyboard: dict[str, Any],
    *,
    output_path: str | Path = DEFAULT_REFERENCE,
    cache_path: str | Path = DEFAULT_CACHE,
) -> Path:
    output = _resolve_path(output_path)
    svg_output = output.with_suffix(".svg")
    inputs = {
        "renderer_version": RENDERER_VERSION,
        "style_block": storyboard["style_block"],
        "characters": storyboard["characters"],
    }
    if _cached_outputs(
        "reference-sheet",
        inputs,
        [output, svg_output],
        shot_id=None,
        cache_path=cache_path,
    ):
        print(f"Reference sheet: using cached {output}.", flush=True)
        return output

    output.parent.mkdir(parents=True, exist_ok=True)
    svg_output.write_text(_reference_svg(storyboard), encoding="utf-8")
    _svg_to_png(svg_output, output)
    mark_cached("reference-sheet", inputs, cache_path=cache_path)
    print(f"Reference sheet rendered locally: {output}.", flush=True)
    return output


def generate_keyframes(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    output_dir: str | Path = DEFAULT_KEYFRAME_DIR,
    cache_path: str | Path = DEFAULT_CACHE,
) -> list[Path]:
    storyboard = validate_storyboard(storyboard_path)
    shots = storyboard["shots"]
    ids = [shot["shot_id"] for shot in shots]
    if len(ids) != len(set(ids)):
        raise ValueError("Storyboard shot_id values must be unique")

    reference_paths = sorted(
        {
            _resolve_path(character["reference_image"])
            for character in storyboard["characters"].values()
        }
    )
    for reference_path in reference_paths:
        generate_reference_sheet(
            storyboard,
            output_path=reference_path,
            cache_path=cache_path,
        )
    reference_hashes = [file_hash(path) for path in reference_paths]
    output_root = _resolve_path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for shot in shots:
        shot_id = shot["shot_id"]
        png_path = output_root / f"{shot_id}.png"
        svg_path = output_root / f"{shot_id}.svg"
        inputs = {
            "renderer_version": RENDERER_VERSION,
            "style_block": storyboard["style_block"],
            "shot": shot,
            "reference_hashes": reference_hashes,
        }
        if _cached_outputs(
            "keyframes",
            inputs,
            [png_path, svg_path],
            shot_id=shot_id,
            cache_path=cache_path,
        ):
            print(f"{shot_id}: using cached keyframe.", flush=True)
            outputs.append(png_path)
            continue
        svg_path.write_text(_shot_svg(shot), encoding="utf-8")
        _svg_to_png(svg_path, png_path)
        mark_cached(
            "keyframes",
            inputs,
            shot_id=shot_id,
            cache_path=cache_path,
        )
        print(f"{shot_id}: local illustrated keyframe rendered.", flush=True)
        outputs.append(png_path)
    return outputs


def _camera_filter(movement: str, frame_count: int) -> str:
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    motion_frames = max(1, frame_count - 1)
    if movement == "slow_pan":
        zoom, x, y = "1.08", f"iw/zoom*on/(2*{motion_frames})", center_y
    elif movement == "subtle_tilt_up":
        zoom, x, y = "1.08", center_x, f"ih/zoom*(1-on/{motion_frames})"
    elif movement == "slow_crane_up":
        zoom, x, y = (
            "min(zoom+0.00025,1.04)",
            center_x,
            f"ih/zoom*(1-on/{motion_frames})",
        )
    elif movement == "subtle_handheld_follow":
        zoom = "1.06"
        x = f"{center_x}+3*sin(on/17)"
        y = f"{center_y}+2*sin(on/13)"
    else:
        increment = "0.00045" if movement == "slow_track_forward" else "0.00055"
        zoom, x, y = f"min(zoom+{increment},1.09)", center_x, center_y
    return (
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frame_count}:"
        f"s=1280x720:fps={FPS},format=yuv420p"
    )


def _probe_video_duration(path: Path) -> float:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise FileNotFoundError("ffprobe is required to validate moving shots")
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


def render_moving_shots(
    *,
    storyboard_path: str | Path = DEFAULT_STORYBOARD,
    keyframe_dir: str | Path = DEFAULT_KEYFRAME_DIR,
    output_dir: str | Path = DEFAULT_SHOT_DIR,
    cache_path: str | Path = DEFAULT_CACHE,
) -> list[Path]:
    storyboard = validate_storyboard(storyboard_path)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("ffmpeg is required to render moving shots")
    keyframes = _resolve_path(keyframe_dir)
    output_root = _resolve_path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for shot in storyboard["shots"]:
        shot_id = shot["shot_id"]
        duration = float(shot["duration_sec"])
        frame_count = round(duration * FPS)
        image_path = keyframes / f"{shot_id}.png"
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Missing keyframe for {shot_id}: {image_path}; run `make keyframes`."
            )
        output = output_root / f"{shot_id}.mp4"
        inputs = {
            "renderer_version": RENDERER_VERSION,
            "keyframe_sha256": file_hash(image_path),
            "duration_sec": duration,
            "camera_movement": shot["camera_movement"],
            "fps": FPS,
        }
        if _cached_outputs(
            "shots",
            inputs,
            [output],
            shot_id=shot_id,
            cache_path=cache_path,
        ):
            actual = _probe_video_duration(output)
            if abs(actual - duration) <= 0.08:
                print(f"{shot_id}: using cached moving shot ({actual:.2f}s).", flush=True)
                rendered.append(output)
                continue
        started = time.perf_counter()
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-loop",
                "1",
                "-framerate",
                str(FPS),
                "-i",
                str(image_path),
                "-vf",
                _camera_filter(shot["camera_movement"], frame_count),
                "-frames:v",
                str(frame_count),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-tune",
                "stillimage",
                "-crf",
                "25",
                "-movflags",
                "+faststart",
                str(output),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=max(90, int(duration * 8)),
        )
        if result.returncode:
            raise RuntimeError(
                f"ffmpeg failed for {shot_id}: {result.stderr.strip()}"
            )
        actual = _probe_video_duration(output)
        if abs(actual - duration) > 0.08:
            raise ValueError(
                f"{shot_id} moving shot is {actual:.2f}s; expected {duration:.2f}s"
            )
        mark_cached("shots", inputs, shot_id=shot_id, cache_path=cache_path)
        print(
            f"{shot_id}: rendered {duration:.2f}s local camera move "
            f"({time.perf_counter() - started:.1f}s).",
            flush=True,
        )
        rendered.append(output)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local Step 4 visuals")
    subparsers = parser.add_subparsers(dest="stage", required=True)
    for stage in ("reference-sheet", "keyframes", "shots"):
        stage_parser = subparsers.add_parser(stage)
        stage_parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
        if stage == "reference-sheet":
            stage_parser.add_argument("--output", type=Path, default=DEFAULT_REFERENCE)
        else:
            stage_parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    try:
        storyboard = validate_storyboard(args.storyboard)
        if args.stage == "reference-sheet":
            generate_reference_sheet(storyboard, output_path=args.output)
        elif args.stage == "keyframes":
            generate_keyframes(
                storyboard_path=args.storyboard,
                output_dir=args.output_dir or DEFAULT_KEYFRAME_DIR,
            )
        else:
            render_moving_shots(
                storyboard_path=args.storyboard,
                output_dir=args.output_dir or DEFAULT_SHOT_DIR,
            )
    except Exception as error:
        print(f"{args.stage} stage failed: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

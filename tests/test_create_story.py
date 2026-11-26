import tempfile
import unittest
import json
from pathlib import Path

from pipeline.create_story import (
    allocate_shot_durations,
    build_storyboard,
    extract_json_object,
)
from pipeline.utils import DEFAULT_SCHEMA, validate_storyboard


class CreateStoryTests(unittest.TestCase):
    def test_allocate_shot_durations_preserves_three_second_end_card(self) -> None:
        durations = allocate_shot_durations(78, 9)

        self.assertEqual(len(durations), 9)
        self.assertAlmostEqual(sum(durations) + 3, 78)
        self.assertEqual(durations, [8.34, 8.34, 8.34] + [8.33] * 6)

    def test_extract_json_object_accepts_markdown_fence(self) -> None:
        parsed = extract_json_object(
            '```json\n{"shots": [], "music": {}, "characters": {}}\n```'
        )

        self.assertEqual(parsed["shots"], [])

    def test_build_storyboard_produces_schema_valid_storyboard(self) -> None:
        shots = [
            {
                "shot_type": "wide",
                "reason": "Establish the story.",
                "narration_am": "የሂሳብ ታሪክ",
                "narration_en": "A story about learning.",
                "tts_style": "Warm and clear",
                "keyframe_prompt": "A warm Ethiopian morning",
                "motion_prompt": "A gentle forward camera move",
                "camera_movement": "slow_track_forward",
            }
            for _ in range(9)
        ]
        generated = {
            "characters": {
                "father": {
                    "id": "char_father",
                    "description": "An Ethiopian father",
                    "reference_image": "outputs/refs/character_sheet.png",
                },
                "young_son": {
                    "id": "char_son",
                    "description": "A young Ethiopian learner",
                    "reference_image": "outputs/refs/character_sheet.png",
                },
                "adult_narrator": {
                    "id": "char_adult",
                    "description": "An Ethiopian adult narrator",
                    "reference_image": "outputs/refs/character_sheet.png",
                },
            },
            "music": {
                "cue_id": "cue_test",
                "caption": "Warm instrumental",
                "tempo_bpm": 80,
                "key": "C major",
                "duration_sec": 75,
                "seed": 42,
            },
            "shots": shots,
        }
        storyboard = build_storyboard(
            generated,
            title="Test Story",
            duration_sec=78,
            story_style="Warm cinematic realism",
            shot_count=9,
        )

        with tempfile.TemporaryDirectory() as directory:
            storyboard_path = Path(directory) / "storyboard.json"
            storyboard_path.write_text(
                json.dumps(storyboard, ensure_ascii=False),
                encoding="utf-8",
            )
            validated = validate_storyboard(storyboard_path, DEFAULT_SCHEMA)

        self.assertEqual(validated["project"]["title"], "Test Story")
        self.assertEqual(len(validated["shots"]), 9)


if __name__ == "__main__":
    unittest.main()

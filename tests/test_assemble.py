import unittest

from pipeline.assemble import _ass_time, _build_ass_script
from pipeline.utils import validate_storyboard


class SubtitleScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.storyboard = validate_storyboard()

    def test_end_card_follows_shots_and_fills_declared_runtime(self) -> None:
        script = _build_ass_script(self.storyboard, width=1280, height=720)
        end_card = next(
            line for line in script.splitlines() if ",EndCard," in line
        )

        self.assertIn("PlayResX: 1280\nPlayResY: 720", script)
        self.assertIn(",0:01:15.00,0:01:18.00,EndCard,", end_card)
        self.assertIn(r"Created with AI\N", end_card)

    def test_portrait_subtitles_use_portrait_play_resolution(self) -> None:
        script = _build_ass_script(self.storyboard, width=720, height=1280)

        self.assertIn("PlayResX: 720\nPlayResY: 1280", script)
        self.assertIn(",EndCard,", script)
        self.assertIn("Walking with my father", script)

    def test_subtitles_end_when_the_shot_narration_ends(self) -> None:
        durations = [0.5] * len(self.storyboard["shots"])
        script = _build_ass_script(
            self.storyboard,
            width=1280,
            height=720,
            narration_durations=durations,
        )

        self.assertIn(",0:00:00.50,Caption,", script)

    def test_ass_timestamps_round_to_centiseconds(self) -> None:
        self.assertEqual(_ass_time(78), "0:01:18.00")
        self.assertEqual(_ass_time(1.239), "0:00:01.24")


if __name__ == "__main__":
    unittest.main()

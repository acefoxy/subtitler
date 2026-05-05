from __future__ import annotations

import unittest

from subtitler.sync.subtitles import SubtitleCue
from subtitler.sync.whisperx_runner import apply_aligned_segments, build_alignment_plan


class WhisperXRunnerTests(unittest.TestCase):
    def test_build_alignment_plan_splits_multi_sentence_cues(self) -> None:
        cues = [SubtitleCue(index=1, start=10.0, end=14.0, lines=("Hello world. Another line!",))]

        plans = build_alignment_plan(cues)

        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].cue_index, 0)
        self.assertEqual(plans[1].cue_index, 0)
        self.assertLess(plans[0].start, plans[0].end)
        self.assertLess(plans[0].end, plans[1].end)

    def test_apply_aligned_segments_merges_sentence_bounds_back_to_cue(self) -> None:
        cues = [SubtitleCue(index=1, start=10.0, end=14.0, lines=("Hello world. Another line!",))]
        plans = build_alignment_plan(cues)

        refined = apply_aligned_segments(
            cues,
            plans,
            [
                {"start": 10.25, "end": 11.15, "text": plans[0].text},
                {"start": 11.35, "end": 13.40, "text": plans[1].text},
            ],
        )

        self.assertEqual(len(refined), 1)
        self.assertAlmostEqual(refined[0].start, 10.25)
        self.assertAlmostEqual(refined[0].end, 13.40)

    def test_apply_aligned_segments_accepts_extra_whisperx_subsegments(self) -> None:
        cues = [
            SubtitleCue(index=1, start=10.0, end=14.0, lines=("Hello world. Another line!",)),
            SubtitleCue(index=2, start=20.0, end=22.0, lines=("Third cue.",)),
        ]
        plans = build_alignment_plan(cues)

        refined = apply_aligned_segments(
            cues,
            plans,
            [
                {"start": 10.10, "end": 10.85, "text": plans[0].text},
                {"start": 11.00, "end": 11.80, "text": "Another"},
                {"start": 11.85, "end": 13.40, "text": "line!"},
                {"start": 20.20, "end": 21.05, "text": plans[2].text},
            ],
        )

        self.assertEqual(len(refined), 2)
        self.assertAlmostEqual(refined[0].start, 10.10)
        self.assertAlmostEqual(refined[0].end, 13.40)
        self.assertAlmostEqual(refined[1].start, 20.20)
        self.assertAlmostEqual(refined[1].end, 21.05)


if __name__ == "__main__":
    unittest.main()
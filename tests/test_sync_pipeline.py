from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from subtitler.config import SyncMode
from subtitler.exceptions import ConfigurationError
from subtitler.sync.base import SyncRequest, SyncResult
from subtitler.sync.pipeline import SyncPipeline


class DummyRunner:
    def __init__(self, name: str, available: bool = True, *, should_fail: bool = False) -> None:
        self.name = name
        self.available = available
        self.should_fail = should_fail
        self.calls = 0

    def is_available(self) -> bool:
        return self.available

    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        self.calls += 1
        if self.should_fail:
            from subtitler.exceptions import SyncError

            raise SyncError("forced failure")
        destination.write_text(request.subtitle_path.read_text(encoding="utf-8"), encoding="utf-8")
        return SyncResult(subtitle_path=destination, tool=self.name)


class DummyRefiner(DummyRunner):
    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        self.calls += 1
        if self.should_fail:
            from subtitler.exceptions import SyncError

            raise SyncError("refinement failed")
        destination.write_text(request.subtitle_path.read_text(encoding="utf-8") + "\n# refined", encoding="utf-8")
        return SyncResult(subtitle_path=destination, tool=self.name)


class SyncPipelineTests(unittest.TestCase):
    def test_auto_mode_uses_first_available_runner(self) -> None:
        runner = DummyRunner("ffsubsync")
        pipeline = SyncPipeline(SyncMode.AUTO, runners=[runner], high_quality_runner=DummyRefiner("whisperx", available=False))
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")

            result = pipeline.sync(
                SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                temp_dir / "output.srt",
            )

            self.assertEqual(result.tool, "ffsubsync")
            self.assertEqual(runner.calls, 1)

    def test_skip_mode_copies_subtitle(self) -> None:
        pipeline = SyncPipeline(SyncMode.SKIP, runners=[])
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            destination = temp_dir / "output.srt"
            subtitle.write_text("payload", encoding="utf-8")

            result = pipeline.sync(
                SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                destination,
            )

            self.assertEqual(result.tool, "skip")
            self.assertEqual(destination.read_text(encoding="utf-8"), "payload")

    def test_auto_mode_requires_sync_engine(self) -> None:
        pipeline = SyncPipeline(SyncMode.AUTO, runners=[], high_quality_runner=DummyRefiner("whisperx", available=False))
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            subtitle.write_text("payload", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                pipeline.sync(
                    SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                    temp_dir / "output.srt",
                )

    def test_auto_mode_runs_high_quality_refinement_when_available(self) -> None:
        baseline = DummyRunner("ffsubsync")
        refiner = DummyRefiner("whisperx")
        pipeline = SyncPipeline(SyncMode.AUTO, runners=[baseline], high_quality_runner=refiner)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            subtitle.write_text("payload", encoding="utf-8")

            result = pipeline.sync(
                SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                temp_dir / "output.srt",
            )

            self.assertEqual(result.tool, "ffsubsync+whisperx")
            self.assertEqual(baseline.calls, 1)
            self.assertEqual(refiner.calls, 1)

    def test_high_quality_mode_requires_refiner(self) -> None:
        pipeline = SyncPipeline(
            SyncMode.HIGH_QUALITY,
            runners=[DummyRunner("ffsubsync")],
            high_quality_runner=DummyRefiner("whisperx", available=False),
        )
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            subtitle.write_text("payload", encoding="utf-8")

            with self.assertRaises(ConfigurationError):
                pipeline.sync(
                    SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                    temp_dir / "output.srt",
                )

    def test_high_quality_mode_raises_when_refiner_failure_occurs(self) -> None:
        baseline = DummyRunner("ffsubsync")
        refiner = DummyRefiner("whisperx", should_fail=True)
        pipeline = SyncPipeline(SyncMode.HIGH_QUALITY, runners=[baseline], high_quality_runner=refiner)
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            subtitle = temp_dir / "input.srt"
            subtitle.write_text("payload", encoding="utf-8")

            with self.assertRaisesRegex(Exception, "refinement failed"):
                pipeline.sync(
                    SyncRequest(video_path=temp_dir / "video.mkv", subtitle_path=subtitle, audio_path=temp_dir / "audio.wav"),
                    temp_dir / "output.srt",
                )


if __name__ == "__main__":
    unittest.main()


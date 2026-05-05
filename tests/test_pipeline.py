from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from subtitler.config import AppConfig, OpenSubtitlesCredentials
from subtitler.exceptions import ConfigurationError, SubtitleNotFoundError
from subtitler.jobs import VideoJob, VideoMetadata
from subtitler.pipeline import _build_providers, _download_subtitle
from subtitler.providers.base import DownloadedSubtitle, SubtitleCandidate


class FakeProvider:
    def __init__(self, name: str, result: DownloadedSubtitle | None = None, error: Exception | None = None) -> None:
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    def download_best_subtitle(self, job: VideoJob, destination_dir: Path) -> DownloadedSubtitle:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class PipelineProviderTests(unittest.TestCase):
    def test_build_providers_uses_web_provider_without_credentials(self) -> None:
        providers = _build_providers(AppConfig())

        self.assertEqual([provider.name for provider in providers], ["subliminal"])

    def test_build_providers_adds_opensubtitles_when_credentials_exist(self) -> None:
        config = AppConfig(
            credentials=OpenSubtitlesCredentials(api_key="key", username="user", password="pass")
        )

        providers = _build_providers(config)

        self.assertEqual([provider.name for provider in providers], ["subliminal", "opensubtitles"])

    def test_download_subtitle_falls_back_to_next_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            result_path = temp_dir / "subtitle.srt"
            result_path.write_text("payload", encoding="utf-8")
            downloaded = DownloadedSubtitle(
                candidate=SubtitleCandidate(
                    provider_name="podnapisi",
                    file_id="abc123",
                    file_name="subtitle.srt",
                    score=100.0,
                ),
                path=result_path,
            )
            failing = FakeProvider("subliminal", error=SubtitleNotFoundError("nothing found"))
            succeeding = FakeProvider("opensubtitles", result=downloaded)

            job = VideoJob(
                video_path=temp_dir / "movie.mkv",
                output_path=temp_dir / "movie.srt",
                metadata=VideoMetadata(title="Movie", query="Movie 2001", kind="movie", year=2001),
            )

            resolved = _download_subtitle(job, [failing, succeeding], temp_dir, logging.getLogger("test"))

            self.assertEqual(resolved.path, result_path)
            self.assertEqual(failing.calls, 1)
            self.assertEqual(succeeding.calls, 1)

    def test_download_subtitle_raises_when_all_providers_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            failing = FakeProvider("subliminal", error=ConfigurationError("missing dependency"))
            job = VideoJob(
                video_path=temp_dir / "movie.mkv",
                output_path=temp_dir / "movie.srt",
                metadata=VideoMetadata(title="Movie", query="Movie 2001", kind="movie", year=2001),
            )

            with self.assertRaises(SubtitleNotFoundError):
                _download_subtitle(job, [failing], temp_dir, logging.getLogger("test"))


if __name__ == "__main__":
    unittest.main()
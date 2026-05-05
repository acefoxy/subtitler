from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..exceptions import ConfigurationError, ProviderError, SubtitleNotFoundError
from ..jobs import VideoJob
from .base import DownloadedSubtitle, SubtitleCandidate

MOVIE_PROVIDERS = ("opensubtitles", "podnapisi")
EPISODE_PROVIDERS = ("opensubtitles", "podnapisi", "tvsubtitles")


class SubliminalProvider:
    name = "subliminal"

    def __init__(self, config: AppConfig) -> None:
        self._timeout = config.request_timeout_seconds

    def download_best_subtitle(self, job: VideoJob, destination_dir: Path) -> DownloadedSubtitle:
        if importlib.util.find_spec("subliminal") is None:
            raise ConfigurationError(
                "The default online subtitle search requires subliminal. Install the project dependencies first."
            )

        try:
            subliminal = importlib.import_module("subliminal")
            babelfish = importlib.import_module("babelfish")
        except ImportError as exc:
            raise ConfigurationError(
                "The default online subtitle search requires subliminal and babelfish. Install the project dependencies first."
            ) from exc

        providers = self._providers_for(job)
        try:
            video = subliminal.scan_video(str(job.video_path))
        except Exception as exc:  # pragma: no cover - depends on subliminal internals
            raise ProviderError(f"Could not inspect video for online subtitle search: {exc}") from exc

        try:
            downloaded = subliminal.download_best_subtitles(
                {video},
                {babelfish.Language("eng")},
                providers=providers,
                min_score=0,
                only_one=True,
            )
        except Exception as exc:  # pragma: no cover - network/provider runtime
            raise ProviderError(f"Online subtitle search failed: {exc}") from exc

        subtitles = downloaded.get(video) or []
        if not subtitles:
            raise SubtitleNotFoundError(f"No English subtitles found online for {job.video_path.name}")

        subtitle = subtitles[0]
        destination_dir.mkdir(parents=True, exist_ok=True)
        try:
            saved = subliminal.save_subtitles(
                video,
                [subtitle],
                single=True,
                directory=str(destination_dir),
                encoding="utf-8",
                subtitle_format="srt",
                extension=".srt",
            )
        except Exception as exc:  # pragma: no cover - depends on subtitle format conversion
            raise ProviderError(f"Downloaded subtitle could not be converted to SRT: {exc}") from exc

        if not saved:
            raise ProviderError("Online subtitle search found a subtitle, but it could not be saved")

        saved_path = destination_dir / f"{job.video_path.stem}.srt"
        if not saved_path.exists():
            srt_candidates = sorted(destination_dir.glob("*.srt"))
            if len(srt_candidates) == 1:
                saved_path = srt_candidates[0]
            else:
                raise ProviderError("Subtitle was downloaded, but the converted SRT file could not be located")

        candidate = SubtitleCandidate(
            provider_name=str(getattr(subtitle, "provider_name", self.name)),
            file_id=str(getattr(subtitle, "id", saved_path.name)),
            file_name=saved_path.name,
            score=100.0,
            hearing_impaired=bool(getattr(subtitle, "hearing_impaired", False)),
        )
        return DownloadedSubtitle(candidate=candidate, path=saved_path)

    def _providers_for(self, job: VideoJob) -> tuple[str, ...]:
        if job.metadata.kind == "episode":
            return EPISODE_PROVIDERS
        return MOVIE_PROVIDERS

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import AppConfig
from .exceptions import ConfigurationError, MediaProcessingError, ProviderError, SubtitleNotFoundError, SubtitlerError, SyncError
from .jobs import VideoJob, discover_video_jobs
from .media.ffmpeg import ensure_binary, extract_audio
from .providers import OpenSubtitlesProvider, SubliminalProvider
from .providers.base import DownloadedSubtitle, SubtitleProvider
from .sync.base import SyncRequest
from .sync.pipeline import SyncPipeline


@dataclass(frozen=True)
class ProcessingResult:
    video_path: Path
    output_path: Path
    success: bool
    message: str
    provider_name: str = "-"
    sync_tool: str = "-"


@dataclass(frozen=True)
class ProcessingSummary:
    results: list[ProcessingResult]

    @property
    def failed(self) -> int:
        return sum(1 for result in self.results if not result.success)


def process_input(input_path: Path, *, config: AppConfig, logger: logging.Logger) -> ProcessingSummary:
    ffmpeg_bin = ensure_binary(config.ffmpeg_bin, "ffmpeg")

    jobs = discover_video_jobs(input_path, config.output_dir)
    providers = _build_providers(config)
    sync_pipeline = SyncPipeline(config.sync_mode, prefer_gpu=config.prefer_gpu)

    results: list[ProcessingResult] = []
    for job in jobs:
        logger.info("processing %s", job.video_path)
        result = _process_job(
            job,
            config=config,
            ffmpeg_bin=ffmpeg_bin,
            providers=providers,
            sync_pipeline=sync_pipeline,
            logger=logger,
        )
        results.append(result)

    return ProcessingSummary(results=results)


def _process_job(
    job: VideoJob,
    *,
    config: AppConfig,
    ffmpeg_bin: str,
    providers: Sequence[SubtitleProvider],
    sync_pipeline: SyncPipeline,
    logger: logging.Logger,
) -> ProcessingResult:
    if job.output_path.exists() and not config.overwrite:
        return ProcessingResult(
            video_path=job.video_path,
            output_path=job.output_path,
            success=True,
            message="output already exists; skipped",
            sync_tool="skipped",
        )

    try:
        if config.keep_temp:
            temp_root = config.cache_dir / "jobs"
            temp_root.mkdir(parents=True, exist_ok=True)
            temp_dir_name = tempfile.mkdtemp(prefix=f"{job.video_path.stem}-", dir=temp_root)
            temp_dir = Path(temp_dir_name)
            result = _run_job(temp_dir, job, config, ffmpeg_bin, providers, sync_pipeline, logger)
            logger.info("temporary files kept at %s", temp_dir)
            return result
        with tempfile.TemporaryDirectory(prefix=f"{job.video_path.stem}-", dir=config.cache_dir) as temp_dir_name:
            return _run_job(
                Path(temp_dir_name),
                job,
                config,
                ffmpeg_bin,
                providers,
                sync_pipeline,
                logger,
            )
    except (MediaProcessingError, ProviderError, SyncError, SubtitlerError) as exc:
        return ProcessingResult(
            video_path=job.video_path,
            output_path=job.output_path,
            success=False,
            message=str(exc),
        )


def _run_job(
    temp_dir: Path,
    job: VideoJob,
    config: AppConfig,
    ffmpeg_bin: str,
    providers: Sequence[SubtitleProvider],
    sync_pipeline: SyncPipeline,
    logger: logging.Logger,
) -> ProcessingResult:
    audio_path = temp_dir / "audio.wav"
    extract_audio(job.video_path, audio_path, ffmpeg_bin=ffmpeg_bin, overwrite=True)
    logger.debug("audio extracted for %s", job.video_path.name)

    downloaded = _download_subtitle(job, providers, temp_dir, logger)
    synced_path = temp_dir / f"synced{downloaded.path.suffix or '.srt'}"
    sync_request = SyncRequest(video_path=job.video_path, subtitle_path=downloaded.path, audio_path=audio_path)
    sync_result = sync_pipeline.sync(sync_request, synced_path)

    job.output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sync_result.subtitle_path, job.output_path)
    return ProcessingResult(
        video_path=job.video_path,
        output_path=job.output_path,
        success=True,
        message="synced subtitle written",
        provider_name=downloaded.candidate.provider_name,
        sync_tool=sync_result.tool,
    )


def _build_providers(config: AppConfig) -> list[SubtitleProvider]:
    providers: list[SubtitleProvider] = [SubliminalProvider(config)]
    if config.credentials.configured:
        providers.append(OpenSubtitlesProvider(config))
    return providers


def _download_subtitle(
    job: VideoJob,
    providers: Sequence[SubtitleProvider],
    destination_dir: Path,
    logger: logging.Logger,
) -> DownloadedSubtitle:
    errors: list[str] = []
    for provider in providers:
        try:
            downloaded = provider.download_best_subtitle(job, destination_dir)
            logger.info("subtitle resolved via %s", downloaded.candidate.provider_name)
            return downloaded
        except SubtitleNotFoundError as exc:
            errors.append(f"{provider.name}: {exc}")
        except (ConfigurationError, ProviderError) as exc:
            errors.append(f"{provider.name}: {exc}")

    if not providers:
        raise ConfigurationError("No subtitle providers are configured")
    raise SubtitleNotFoundError("No usable English subtitles found. " + " | ".join(errors))

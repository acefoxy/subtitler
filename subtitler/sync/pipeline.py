from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence

from ..config import SyncMode
from ..exceptions import ConfigurationError, SyncError
from .alass_runner import AlassRunner
from .base import SyncRequest, SyncResult, SyncRunner
from .ffsubsync_runner import FfsubsyncRunner
from .whisperx_runner import WhisperXRunner


class SyncPipeline:
    def __init__(
        self,
        sync_mode: SyncMode,
        runners: Sequence[SyncRunner] | None = None,
        *,
        high_quality_runner: SyncRunner | None = None,
        prefer_gpu: bool = True,
    ) -> None:
        self.sync_mode = sync_mode
        self.runners = list(runners or [FfsubsyncRunner(), AlassRunner()])
        self.high_quality_runner = high_quality_runner if high_quality_runner is not None else WhisperXRunner(prefer_gpu=prefer_gpu)

    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        if self.sync_mode == SyncMode.SKIP:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(request.subtitle_path, destination)
            return SyncResult(subtitle_path=destination, tool="skip", note="subtitle copied without resync")

        if self.sync_mode == SyncMode.FFSUBSYNC:
            return self._run_named("ffsubsync", request, destination)
        if self.sync_mode == SyncMode.ALASS:
            return self._run_named("alass", request, destination)
        if self.sync_mode == SyncMode.HIGH_QUALITY:
            return self._run_high_quality(request, destination, require_refiner=True)

        if self.high_quality_runner.is_available():
            return self._run_high_quality(request, destination, require_refiner=False)
        return self._run_best_baseline(request, destination)

    def _run_high_quality(self, request: SyncRequest, destination: Path, *, require_refiner: bool) -> SyncResult:
        if not self.high_quality_runner.is_available():
            if require_refiner:
                raise ConfigurationError(
                    "High-quality sync requires WhisperX. Install the hq-sync extra or use a different sync mode."
                )
            return self._run_best_baseline(request, destination)

        baseline_result: SyncResult | None = None
        baseline_request = request
        available_baselines = [runner for runner in self.runners if runner.is_available()]
        if available_baselines:
            baseline_destination = destination.parent / f"{destination.stem}.baseline.srt"
            baseline_result = self._run_best_baseline(request, baseline_destination)
            baseline_request = SyncRequest(
                video_path=request.video_path,
                subtitle_path=baseline_result.subtitle_path,
                audio_path=request.audio_path,
            )
        elif require_refiner and request.subtitle_path.suffix.lower() != ".srt":
            raise ConfigurationError("High-quality sync requires SRT subtitles when no baseline sync engine is available.")

        refined_destination = self._high_quality_destination(destination)
        try:
            refined = self.high_quality_runner.sync(baseline_request, refined_destination)
        except SyncError as exc:
            if require_refiner:
                raise
            if baseline_result is not None:
                refined_destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(baseline_result.subtitle_path, refined_destination)
                return SyncResult(
                    subtitle_path=refined_destination,
                    tool=baseline_result.tool,
                    note=f"high-quality refinement failed; using baseline sync instead: {exc}",
                )
            raise

        if baseline_result is None:
            return refined
        return SyncResult(
            subtitle_path=refined.subtitle_path,
            tool=f"{baseline_result.tool}+{refined.tool}",
            note=refined.note,
        )

    def _run_best_baseline(self, request: SyncRequest, destination: Path) -> SyncResult:
        available = [runner for runner in self.runners if runner.is_available()]
        if not available:
            raise ConfigurationError("No sync engine available. Install ffsubsync or alass, or use --sync-mode skip.")

        errors: list[str] = []
        for runner in available:
            try:
                return runner.sync(request, destination)
            except SyncError as exc:
                errors.append(f"{runner.name}: {exc}")

        raise SyncError("All sync engines failed: " + "; ".join(errors))

    def _run_named(self, name: str, request: SyncRequest, destination: Path) -> SyncResult:
        for runner in self.runners:
            if runner.name == name:
                return runner.sync(request, destination)
        raise ConfigurationError(f"Configured sync engine is not available in this build: {name}")

    def _high_quality_destination(self, destination: Path) -> Path:
        if destination.suffix.lower() == ".srt":
            return destination
        if destination.suffix:
            return destination.with_suffix(".srt")
        return destination.with_name(f"{destination.name}.srt")

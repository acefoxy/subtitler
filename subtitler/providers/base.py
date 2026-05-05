from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..jobs import VideoJob


@dataclass(frozen=True)
class SubtitleCandidate:
    provider_name: str
    file_id: str
    file_name: str
    score: float
    language: str = "en"
    hearing_impaired: bool = False
    download_count: int = 0

    @property
    def suffix(self) -> str:
        suffix = Path(self.file_name).suffix.lower()
        return suffix or ".srt"


@dataclass(frozen=True)
class DownloadedSubtitle:
    candidate: SubtitleCandidate
    path: Path


class SubtitleProvider(Protocol):
    name: str

    def download_best_subtitle(self, job: VideoJob, destination_dir: Path) -> DownloadedSubtitle:
        raise NotImplementedError

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SyncRequest:
    video_path: Path
    subtitle_path: Path
    audio_path: Path | None = None


@dataclass(frozen=True)
class SyncResult:
    subtitle_path: Path
    tool: str
    note: str = ""


class SyncRunner(Protocol):
    name: str

    def is_available(self) -> bool:
        raise NotImplementedError

    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        raise NotImplementedError

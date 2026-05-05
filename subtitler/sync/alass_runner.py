from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..exceptions import SyncError
from .base import SyncRequest, SyncResult


class AlassRunner:
    name = "alass"

    def __init__(self, binary: str = "alass") -> None:
        self.binary = binary

    def is_available(self) -> bool:
        return shutil.which(self.binary) is not None

    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        resolved_binary = shutil.which(self.binary)
        if resolved_binary is None:
            raise SyncError("alass is not installed or not available in PATH")

        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [resolved_binary, str(request.video_path), str(request.subtitle_path), str(destination)]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            message = exc.stderr.strip() or exc.stdout.strip() or "alass failed"
            raise SyncError(message) from exc
        return SyncResult(subtitle_path=destination, tool=self.name)

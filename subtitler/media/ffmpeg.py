from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..exceptions import ConfigurationError, MediaProcessingError


def ensure_binary(binary: str, label: str) -> str:
    resolved = shutil.which(binary)
    if resolved:
        return resolved
    binary_path = Path(binary)
    if binary_path.exists() and binary_path.is_file():
        return str(binary_path)
    raise ConfigurationError(f"{label} binary not found: {binary}")


def _run_command(command: list[str], timeout_seconds: int | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessingError(f"Command timed out: {' '.join(command)}") from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "FFmpeg command failed"
        raise MediaProcessingError(message) from exc


def extract_audio(
    video_path: Path,
    destination: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    overwrite: bool = True,
    timeout_seconds: int | None = 1800,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    overwrite_flag = "-y" if overwrite else "-n"
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        overwrite_flag,
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    _run_command(command, timeout_seconds=timeout_seconds)
    return destination

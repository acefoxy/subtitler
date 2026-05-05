from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path


class SyncMode(StrEnum):
    AUTO = "auto"
    HIGH_QUALITY = "high-quality"
    FFSUBSYNC = "ffsubsync"
    ALASS = "alass"
    SKIP = "skip"


@dataclass(frozen=True)
class OpenSubtitlesCredentials:
    api_key: str | None = None
    username: str | None = None
    password: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.username and self.password)


@dataclass(frozen=True)
class AppConfig:
    credentials: OpenSubtitlesCredentials = field(default_factory=OpenSubtitlesCredentials)
    ffmpeg_bin: str = "ffmpeg"
    opensubtitles_base_url: str = "https://api.opensubtitles.com/api/v1"
    request_timeout_seconds: int = 30
    sync_mode: SyncMode = SyncMode.HIGH_QUALITY
    output_dir: Path | None = None
    keep_temp: bool = False
    overwrite: bool = False
    log_level: str = "INFO"
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "subtitler")
    prefer_gpu: bool = True
    user_agent: str = "subtitler/0.1.0"

    @classmethod
    def from_env(cls) -> "AppConfig":
        credentials = OpenSubtitlesCredentials(
            api_key=os.getenv("SUBTITLER_OPENSUBTITLES_API_KEY"),
            username=os.getenv("SUBTITLER_OPENSUBTITLES_USERNAME"),
            password=os.getenv("SUBTITLER_OPENSUBTITLES_PASSWORD"),
        )
        output_dir_value = os.getenv("SUBTITLER_OUTPUT_DIR")
        sync_mode_value = os.getenv("SUBTITLER_SYNC_MODE", SyncMode.HIGH_QUALITY.value)
        return cls(
            credentials=credentials,
            ffmpeg_bin=os.getenv("SUBTITLER_FFMPEG_BIN", "ffmpeg"),
            request_timeout_seconds=int(os.getenv("SUBTITLER_REQUEST_TIMEOUT", "30")),
            sync_mode=SyncMode(sync_mode_value),
            output_dir=Path(output_dir_value).expanduser() if output_dir_value else None,
            keep_temp=os.getenv("SUBTITLER_KEEP_TEMP", "0") == "1",
            overwrite=os.getenv("SUBTITLER_OVERWRITE", "0") == "1",
            log_level=os.getenv("SUBTITLER_LOG_LEVEL", "INFO").upper(),
            cache_dir=Path(os.getenv("SUBTITLER_CACHE_DIR", Path.home() / ".cache" / "subtitler")).expanduser(),
            prefer_gpu=os.getenv("SUBTITLER_PREFER_GPU", "1") != "0",
        )

    def with_overrides(
        self,
        *,
        api_key: str | None = None,
        username: str | None = None,
        password: str | None = None,
        ffmpeg_bin: str | None = None,
        sync_mode: SyncMode | None = None,
        output_dir: Path | None = None,
        keep_temp: bool | None = None,
        overwrite: bool | None = None,
        log_level: str | None = None,
        cache_dir: Path | None = None,
        prefer_gpu: bool | None = None,
    ) -> "AppConfig":
        credentials = replace(
            self.credentials,
            api_key=api_key or self.credentials.api_key,
            username=username or self.credentials.username,
            password=password or self.credentials.password,
        )
        return replace(
            self,
            credentials=credentials,
            ffmpeg_bin=ffmpeg_bin or self.ffmpeg_bin,
            sync_mode=sync_mode or self.sync_mode,
            output_dir=output_dir if output_dir is not None else self.output_dir,
            keep_temp=self.keep_temp if keep_temp is None else keep_temp,
            overwrite=self.overwrite if overwrite is None else overwrite,
            log_level=(log_level or self.log_level).upper(),
            cache_dir=cache_dir or self.cache_dir,
            prefer_gpu=self.prefer_gpu if prefer_gpu is None else prefer_gpu,
        )

    def ensure_runtime_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

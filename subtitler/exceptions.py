from __future__ import annotations


class SubtitlerError(Exception):
    """Base exception for the application."""


class ConfigurationError(SubtitlerError):
    """Raised when runtime configuration is invalid or incomplete."""


class InputPathError(SubtitlerError):
    """Raised when the input path is missing or unsupported."""


class ProviderError(SubtitlerError):
    """Raised when subtitle lookup or download fails."""


class SubtitleNotFoundError(ProviderError):
    """Raised when no subtitle match can be found."""


class SyncError(SubtitlerError):
    """Raised when subtitle synchronization fails."""


class MediaProcessingError(SubtitlerError):
    """Raised when FFmpeg execution fails."""

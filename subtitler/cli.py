from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .config import AppConfig, SyncMode
from .exceptions import ConfigurationError, InputPathError, SubtitlerError
from .logging_utils import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subtitler",
        description="Find English subtitles online, sync them, and save them as a standalone SRT file.",
    )
    parser.add_argument("input_path", type=Path, help="Video file or folder containing video files.")
    parser.add_argument("--output-dir", type=Path, help="Optional output directory. Defaults to next to the source video.")
    parser.add_argument("--api-key", help="OpenSubtitles API key. Falls back to SUBTITLER_OPENSUBTITLES_API_KEY.")
    parser.add_argument("--username", help="OpenSubtitles username. Falls back to SUBTITLER_OPENSUBTITLES_USERNAME.")
    parser.add_argument("--password", help="OpenSubtitles password. Falls back to SUBTITLER_OPENSUBTITLES_PASSWORD.")
    parser.add_argument(
        "--sync-mode",
        choices=[mode.value for mode in SyncMode],
        default=None,
        help="Synchronization mode. Defaults to high-quality.",
    )
    parser.add_argument(
        "--keep-temp",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Keep temporary files for inspection.",
    )
    parser.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Overwrite an existing output subtitle file.",
    )
    parser.add_argument("--ffmpeg-bin", help="Custom ffmpeg binary path.")
    parser.add_argument("--cache-dir", type=Path, help="Cache directory for provider lookups.")
    parser.add_argument(
        "--no-gpu",
        action="store_true",
        help="Disable GPU preference for WhisperX alignment. GPU is preferred by default.",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log verbosity.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = AppConfig.from_env().with_overrides(
        api_key=args.api_key,
        username=args.username,
        password=args.password,
        ffmpeg_bin=args.ffmpeg_bin,
        sync_mode=SyncMode(args.sync_mode) if args.sync_mode else None,
        output_dir=args.output_dir.expanduser() if args.output_dir else None,
        keep_temp=args.keep_temp,
        overwrite=args.overwrite,
        log_level=args.log_level,
        cache_dir=args.cache_dir.expanduser() if args.cache_dir else None,
        prefer_gpu=not args.no_gpu,
    )
    config.ensure_runtime_dirs()

    logger = setup_logging(config.log_level)

    try:
        from .pipeline import process_input

        summary = process_input(args.input_path, config=config, logger=logger)
    except (ConfigurationError, InputPathError, SubtitlerError) as exc:
        logger.error(str(exc))
        return 1

    for result in summary.results:
        if result.success:
            logger.info(
                "processed %s -> %s [%s/%s]",
                result.video_path,
                result.output_path,
                result.provider_name,
                result.sync_tool,
            )
        else:
            logger.error("failed %s: %s", result.video_path, result.message)

    return 0 if summary.failed == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

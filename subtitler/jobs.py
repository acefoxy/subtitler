from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .exceptions import InputPathError

VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".flv",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
    ".wmv",
}

NOISE_TOKENS = {
    "1080p",
    "2160p",
    "480p",
    "720p",
    "aac",
    "amzn",
    "bluray",
    "brrip",
    "ddp5",
    "dl",
    "dvdrip",
    "eac3",
    "h264",
    "h265",
    "hevc",
    "hdr",
    "nf",
    "proper",
    "repack",
    "remux",
    "web",
    "webrip",
    "webdl",
    "x264",
    "x265",
}

SEASON_EPISODE_PATTERNS = (
    re.compile(r"(?i)\bs(?P<season>\d{1,2})e(?P<episode>\d{1,2})\b"),
    re.compile(r"(?i)\b(?P<season>\d{1,2})x(?P<episode>\d{1,2})\b"),
)
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")


@dataclass(frozen=True)
class VideoMetadata:
    title: str
    query: str
    kind: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None


@dataclass(frozen=True)
class VideoJob:
    video_path: Path
    output_path: Path
    metadata: VideoMetadata


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def parse_video_metadata(video_path: Path) -> VideoMetadata:
    name = video_path.stem
    season = None
    episode = None
    kind = "movie"
    matched_token = None

    for pattern in SEASON_EPISODE_PATTERNS:
        match = pattern.search(name)
        if match:
            season = int(match.group("season"))
            episode = int(match.group("episode"))
            matched_token = match.group(0)
            kind = "episode"
            break

    year_match = YEAR_PATTERN.search(name)
    year = int(year_match.group(1)) if year_match else None

    cleaned = re.sub(r"[._]+", " ", name)
    cleaned = cleaned.replace("-", " ")

    tokens: list[str] = []
    for token in cleaned.split():
        lowered = token.lower()
        if matched_token and lowered == matched_token.lower():
            continue
        if year and token == str(year):
            continue
        if lowered in NOISE_TOKENS:
            continue
        tokens.append(token)

    title = " ".join(tokens).strip() or cleaned.strip()
    title = re.sub(r"\s+", " ", title)
    query = f"{title} {year}".strip() if year and kind == "movie" else title
    return VideoMetadata(
        title=title,
        query=query,
        kind=kind,
        year=year,
        season=season,
        episode=episode,
    )


def build_output_path(video_path: Path, output_dir: Path | None, input_root: Path) -> Path:
    file_name = f"{video_path.stem}.srt"
    if output_dir is None:
        return video_path.with_name(file_name)

    if input_root.is_dir():
        relative_parent = video_path.parent.relative_to(input_root)
        return output_dir / relative_parent / file_name

    return output_dir / file_name


def discover_video_jobs(input_path: Path, output_dir: Path | None = None) -> list[VideoJob]:
    resolved_input = input_path.expanduser().resolve()
    if not resolved_input.exists():
        raise InputPathError(f"Input path does not exist: {resolved_input}")

    video_files: list[Path]
    if resolved_input.is_file():
        if not is_video_file(resolved_input):
            raise InputPathError(f"Unsupported video file: {resolved_input}")
        video_files = [resolved_input]
    else:
        video_files = sorted(path for path in resolved_input.rglob("*") if is_video_file(path))
        if not video_files:
            raise InputPathError(f"No supported video files found under: {resolved_input}")

    return [
        VideoJob(
            video_path=video_path,
            output_path=build_output_path(video_path, output_dir, resolved_input),
            metadata=parse_video_metadata(video_path),
        )
        for video_path in video_files
    ]

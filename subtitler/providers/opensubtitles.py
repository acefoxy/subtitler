from __future__ import annotations

import gzip
import io
import json
import re
import struct
import zipfile
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from ..config import AppConfig, OpenSubtitlesCredentials
from ..exceptions import ConfigurationError, ProviderError, SubtitleNotFoundError
from ..jobs import VideoJob
from .base import DownloadedSubtitle, SubtitleCandidate
from .cache import SubtitleSearchCache

SUPPORTED_SUBTITLE_EXTENSIONS = {".ass", ".srt", ".ssa", ".sub"}


@dataclass(frozen=True)
class VideoHash:
    moviehash: str
    moviebytesize: int


class OpenSubtitlesProvider:
    name = "opensubtitles"

    def __init__(self, config: AppConfig) -> None:
        self._credentials: OpenSubtitlesCredentials = config.credentials
        self._base_url = config.opensubtitles_base_url.rstrip("/")
        self._timeout = config.request_timeout_seconds
        self._user_agent = config.user_agent
        self._cache = SubtitleSearchCache(config.cache_dir / "opensubtitles.json")
        self._token: str | None = None

    def download_best_subtitle(self, job: VideoJob, destination_dir: Path) -> DownloadedSubtitle:
        if not self._credentials.configured:
            raise ConfigurationError(
                "OpenSubtitles credentials are required. Set SUBTITLER_OPENSUBTITLES_API_KEY, "
                "SUBTITLER_OPENSUBTITLES_USERNAME, and SUBTITLER_OPENSUBTITLES_PASSWORD."
            )

        destination_dir.mkdir(parents=True, exist_ok=True)
        candidate = self._load_cached_candidate(job)
        if candidate is None:
            candidate = self._search_best_candidate(job)
            self._cache.set(self._cache_key(job), {
                "download_count": candidate.download_count,
                "file_id": candidate.file_id,
                "file_name": candidate.file_name,
                "hearing_impaired": candidate.hearing_impaired,
                "language": candidate.language,
                "score": candidate.score,
            })

        payload = self._request_json(
            "POST",
            "/download",
            payload={"file_id": int(candidate.file_id)},
            auth_required=True,
        )
        link = payload.get("link")
        if not isinstance(link, str) or not link:
            raise ProviderError("OpenSubtitles download response did not include a download link")
        filename_hint = str(payload.get("file_name") or candidate.file_name)
        subtitle_bytes = self._download_bytes(link)
        subtitle_path = self._materialize_download(subtitle_bytes, filename_hint, destination_dir)
        return DownloadedSubtitle(candidate=candidate, path=subtitle_path)

    def _search_best_candidate(self, job: VideoJob) -> SubtitleCandidate:
        candidates: list[SubtitleCandidate] = []
        seen_ids: set[int] = set()
        for use_hash in (True, False):
            for candidate in self._search(job, use_hash=use_hash):
                if candidate.file_id in seen_ids:
                    continue
                seen_ids.add(candidate.file_id)
                candidates.append(candidate)
            if candidates:
                break

        if not candidates:
            raise SubtitleNotFoundError(f"No English subtitles found online for {job.video_path.name}")

        return max(candidates, key=lambda item: item.score)

    def _search(self, job: VideoJob, *, use_hash: bool) -> list[SubtitleCandidate]:
        params = self._build_search_params(job, use_hash=use_hash)
        if params is None:
            return []
        payload = self._request_json("GET", "/subtitles", params=params)
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            return []

        candidates: list[SubtitleCandidate] = []
        for item in raw_items:
            candidate = self._candidate_from_item(job, item)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _build_search_params(self, job: VideoJob, *, use_hash: bool) -> dict[str, Any] | None:
        params: dict[str, Any] = {
            "languages": "en",
            "order_by": "download_count",
            "order_direction": "desc",
        }
        if use_hash:
            video_hash = compute_opensubtitles_hash(job.video_path)
            if video_hash is None:
                return None
            params["moviehash"] = video_hash.moviehash
            params["moviebytesize"] = video_hash.moviebytesize
            return params

        params["query"] = job.metadata.query
        params["type"] = "episode" if job.metadata.kind == "episode" else "movie"
        if job.metadata.season is not None:
            params["season_number"] = job.metadata.season
        if job.metadata.episode is not None:
            params["episode_number"] = job.metadata.episode
        if job.metadata.year is not None and job.metadata.kind == "movie":
            params["year"] = job.metadata.year
        return params

    def _candidate_from_item(self, job: VideoJob, item: Any) -> SubtitleCandidate | None:
        if not isinstance(item, dict):
            return None
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            return None
        files = attributes.get("files")
        if not isinstance(files, list) or not files:
            return None

        selected_file = self._pick_file(files)
        if selected_file is None:
            return None

        file_id = selected_file.get("file_id")
        if file_id is None:
            return None

        file_name = str(selected_file.get("file_name") or attributes.get("release") or f"{file_id}.srt")
        feature_details = attributes.get("feature_details")
        feature = feature_details if isinstance(feature_details, dict) else {}
        title = str(feature.get("movie_name") or feature.get("title") or attributes.get("release") or file_name)
        season = _to_int(feature.get("season_number"))
        episode = _to_int(feature.get("episode_number"))
        year = _to_int(feature.get("year"))
        download_count = _to_int(attributes.get("download_count")) or 0
        hearing_impaired = bool(attributes.get("hearing_impaired"))
        score = self._score_candidate(
            job,
            title=title,
            file_name=file_name,
            season=season,
            episode=episode,
            year=year,
            download_count=download_count,
        )
        return SubtitleCandidate(
            provider_name=self.name,
            file_id=str(file_id),
            file_name=file_name,
            score=score,
            hearing_impaired=hearing_impaired,
            download_count=download_count,
        )

    def _pick_file(self, files: list[Any]) -> dict[str, Any] | None:
        ranked: list[tuple[int, dict[str, Any]]] = []
        for file_item in files:
            if not isinstance(file_item, dict):
                continue
            file_name = str(file_item.get("file_name") or "")
            suffix = Path(file_name).suffix.lower()
            rank = 0
            if suffix == ".srt":
                rank = 3
            elif suffix in {".ass", ".ssa"}:
                rank = 2
            elif suffix in SUPPORTED_SUBTITLE_EXTENSIONS:
                rank = 1
            ranked.append((rank, file_item))
        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1]

    def _score_candidate(
        self,
        job: VideoJob,
        *,
        title: str,
        file_name: str,
        season: int | None,
        episode: int | None,
        year: int | None,
        download_count: int,
    ) -> float:
        normalized_query = _normalize(job.metadata.query)
        normalized_title = _normalize(title)
        normalized_file_name = _normalize(Path(file_name).stem)
        ratio = max(
            SequenceMatcher(None, normalized_query, normalized_title).ratio(),
            SequenceMatcher(None, normalized_query, normalized_file_name).ratio(),
        )
        score = ratio * 100

        suffix = Path(file_name).suffix.lower()
        if suffix == ".srt":
            score += 8
        elif suffix in {".ass", ".ssa"}:
            score += 4

        if job.metadata.kind == "episode":
            if season == job.metadata.season:
                score += 15
            elif season is not None:
                score -= 40

            if episode == job.metadata.episode:
                score += 20
            elif episode is not None:
                score -= 50
        elif job.metadata.year is not None:
            if year == job.metadata.year:
                score += 15
            elif year is not None:
                score -= 10

        score += min(download_count, 5000) / 500
        return score

    def _load_cached_candidate(self, job: VideoJob) -> SubtitleCandidate | None:
        cached = self._cache.get(self._cache_key(job))
        if cached is None:
            return None
        try:
            return SubtitleCandidate(
                provider_name=self.name,
                file_id=str(cached["file_id"]),
                file_name=str(cached["file_name"]),
                score=float(cached.get("score", 0.0)),
                language=str(cached.get("language", "en")),
                hearing_impaired=bool(cached.get("hearing_impaired", False)),
                download_count=int(cached.get("download_count", 0)),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _cache_key(self, job: VideoJob) -> str:
        parts = [
            job.video_path.name,
            job.metadata.query,
            job.metadata.kind,
            str(job.metadata.year or ""),
            str(job.metadata.season or ""),
            str(job.metadata.episode or ""),
            str(job.video_path.stat().st_size),
        ]
        return "|".join(parts)

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        auth_required: bool = False,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        if params:
            url = f"{url}?{parse.urlencode(params)}"

        headers = {
            "Accept": "application/json",
            "Api-Key": self._credentials.api_key or "",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }
        if auth_required:
            headers["Authorization"] = f"Bearer {self._login()}"

        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(url, data=body, method=method.upper(), headers=headers)
        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"OpenSubtitles API error {exc.code}: {detail or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderError(f"OpenSubtitles request failed: {exc.reason}") from exc

        if not raw:
            return {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ProviderError("OpenSubtitles returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise ProviderError("OpenSubtitles returned an unexpected response format")
        return decoded

    def _login(self) -> str:
        if self._token:
            return self._token
        payload = self._request_json(
            "POST",
            "/login",
            payload={
                "username": self._credentials.username,
                "password": self._credentials.password,
            },
        )
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise ProviderError("OpenSubtitles login did not return an access token")
        self._token = token
        return token

    def _download_bytes(self, url: str) -> bytes:
        req = request.Request(url, headers={"User-Agent": self._user_agent})
        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                return response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProviderError(f"Subtitle download failed with HTTP {exc.code}: {detail or exc.reason}") from exc
        except error.URLError as exc:
            raise ProviderError(f"Subtitle download failed: {exc.reason}") from exc

    def _materialize_download(self, payload: bytes, filename_hint: str, destination_dir: Path) -> Path:
        archive_buffer = io.BytesIO(payload)
        if zipfile.is_zipfile(archive_buffer):
            archive_buffer.seek(0)
            with zipfile.ZipFile(archive_buffer) as archive:
                members = [
                    member for member in archive.namelist() if Path(member).suffix.lower() in SUPPORTED_SUBTITLE_EXTENSIONS
                ]
                if not members:
                    raise ProviderError("Downloaded archive did not contain a supported subtitle file")
                members.sort(key=_archive_member_rank)
                member = members[0]
                return self._write_subtitle_bytes(archive.read(member), Path(member).name, destination_dir)

        if filename_hint.lower().endswith(".gz") or payload[:2] == b"\x1f\x8b":
            try:
                uncompressed = gzip.decompress(payload)
            except OSError as exc:
                raise ProviderError("Downloaded subtitle archive could not be decompressed") from exc
            unpacked_name = Path(filename_hint).with_suffix("").name
            return self._write_subtitle_bytes(uncompressed, unpacked_name, destination_dir)

        return self._write_subtitle_bytes(payload, filename_hint, destination_dir)

    def _write_subtitle_bytes(self, payload: bytes, filename_hint: str, destination_dir: Path) -> Path:
        suffix = Path(filename_hint).suffix.lower()
        if suffix not in SUPPORTED_SUBTITLE_EXTENSIONS:
            suffix = ".srt"
        destination = destination_dir / f"subtitle{suffix}"
        destination.write_bytes(payload)
        return destination


def compute_opensubtitles_hash(video_path: Path) -> VideoHash | None:
    file_size = video_path.stat().st_size
    if file_size < 131072:
        return None

    hash_value = file_size
    with video_path.open("rb") as handle:
        for _ in range(65536 // 8):
            chunk = handle.read(8)
            hash_value += struct.unpack("<Q", chunk)[0]
        handle.seek(max(0, file_size - 65536))
        for _ in range(65536 // 8):
            chunk = handle.read(8)
            hash_value += struct.unpack("<Q", chunk)[0]

    return VideoHash(moviehash=f"{hash_value & 0xFFFFFFFFFFFFFFFF:016x}", moviebytesize=file_size)


def _normalize(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", collapsed).strip()


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _archive_member_rank(member: str) -> tuple[int, int, str]:
    suffix = Path(member).suffix.lower()
    extension_rank = {
        ".srt": 0,
        ".ass": 1,
        ".ssa": 2,
        ".sub": 3,
    }.get(suffix, 9)
    return (extension_rank, len(member), member)

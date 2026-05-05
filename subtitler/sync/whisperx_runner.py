from __future__ import annotations

import gc
import importlib
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..exceptions import SyncError
from .base import SyncRequest, SyncResult
from .subtitles import SubtitleCue, load_srt, write_srt

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
MATCH_KEY_RE = re.compile(r"[\W_]+", re.UNICODE)


@dataclass(frozen=True)
class AlignmentSegmentPlan:
    cue_index: int
    start: float
    end: float
    text: str


class WhisperXRunner:
    name = "whisperx"

    def __init__(self, *, prefer_gpu: bool = True, language_code: str = "en") -> None:
        self.prefer_gpu = prefer_gpu
        self.language_code = language_code

    def is_available(self) -> bool:
        return importlib.util.find_spec("whisperx") is not None

    def sync(self, request: SyncRequest, destination: Path) -> SyncResult:
        if request.audio_path is None:
            raise SyncError("High-quality sync requires an extracted audio path")
        if request.subtitle_path.suffix.lower() != ".srt":
            raise SyncError("High-quality sync currently supports SRT subtitles only")

        cues = load_srt(request.subtitle_path)
        if not cues:
            raise SyncError("High-quality sync could not read any subtitle cues from the SRT file")

        plans = build_alignment_plan(cues)
        if not plans:
            raise SyncError("High-quality sync could not derive any alignable subtitle segments")

        whisperx = importlib.import_module("whisperx")
        device, torch_module = _select_device(self.prefer_gpu)
        audio = whisperx.load_audio(str(request.audio_path))
        align_model, metadata = whisperx.load_align_model(language_code=self.language_code, device=device)

        try:
            aligned = whisperx.align(
                [_plan_to_payload(plan) for plan in plans],
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
                print_progress=False,
            )
        except Exception as exc:  # pragma: no cover - depends on external runtime
            raise SyncError(f"WhisperX forced alignment failed: {exc}") from exc
        finally:
            del align_model
            gc.collect()
            if torch_module is not None and hasattr(torch_module, "cuda") and torch_module.cuda.is_available():
                torch_module.cuda.empty_cache()

        aligned_segments = aligned.get("segments")
        if not isinstance(aligned_segments, list) or not aligned_segments:
            raise SyncError("WhisperX returned an unexpected alignment shape")

        refined_cues = apply_aligned_segments(cues, plans, aligned_segments)
        final_destination = _ensure_srt_destination(destination)
        write_srt(refined_cues, final_destination)
        return SyncResult(subtitle_path=final_destination, tool=self.name)


def build_alignment_plan(cues: list[SubtitleCue]) -> list[AlignmentSegmentPlan]:
    plans: list[AlignmentSegmentPlan] = []
    for cue_index, cue in enumerate(cues):
        sentence_texts = split_cue_sentences(cue)
        if not sentence_texts:
            continue

        total_units = sum(max(len(normalize_text(text)), 1) for text in sentence_texts)
        cue_duration = max(cue.end - cue.start, 0.001)
        current_start = cue.start
        for sentence_index, sentence_text in enumerate(sentence_texts):
            units = max(len(normalize_text(sentence_text)), 1)
            proportional_duration = cue_duration * (units / total_units)
            segment_end = cue.end if sentence_index == len(sentence_texts) - 1 else min(
                cue.end,
                current_start + proportional_duration,
            )
            if segment_end <= current_start:
                segment_end = min(cue.end, current_start + 0.05)
            plans.append(
                AlignmentSegmentPlan(
                    cue_index=cue_index,
                    start=current_start,
                    end=segment_end,
                    text=sentence_text,
                )
            )
            current_start = segment_end
    return plans


def apply_aligned_segments(
    cues: list[SubtitleCue],
    plans: list[AlignmentSegmentPlan],
    aligned_segments: list[dict[str, Any]],
) -> list[SubtitleCue]:
    grouped_segments = _group_aligned_segments_by_cue(cues, plans, aligned_segments)

    refined: list[SubtitleCue] = []
    previous_end = 0.0
    for cue_index, cue in enumerate(cues):
        cue_segments = grouped_segments.get(cue_index)
        if cue_segments:
            start = min(_coerce_timestamp(segment.get("start"), cue.start) for segment in cue_segments)
            end = max(_coerce_timestamp(segment.get("end"), cue.end) for segment in cue_segments)
            start = max(start, 0.0)
            if end <= start:
                start, end = cue.start, cue.end
            if start < previous_end < end:
                start = previous_end
            refined_cue = cue.with_timing(start, max(end, start + 0.05))
        else:
            refined_cue = cue
        previous_end = refined_cue.end
        refined.append(refined_cue)
    return refined


def _group_aligned_segments_by_cue(
    cues: list[SubtitleCue],
    plans: list[AlignmentSegmentPlan],
    aligned_segments: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    minimum_segments_by_cue = [0] * len(cues)
    for plan in plans:
        if 0 <= plan.cue_index < len(cues):
            minimum_segments_by_cue[plan.cue_index] += 1

    required_segments_after = [0] * (len(cues) + 1)
    for cue_index in range(len(cues) - 1, -1, -1):
        required_segments_after[cue_index] = required_segments_after[cue_index + 1] + minimum_segments_by_cue[cue_index]

    grouped: dict[int, list[dict[str, Any]]] = {}
    segment_index = 0
    for cue_index, cue in enumerate(cues):
        required = minimum_segments_by_cue[cue_index]
        if required <= 0 or segment_index >= len(aligned_segments):
            continue

        take = min(required, len(aligned_segments) - segment_index)
        current_segments = aligned_segments[segment_index : segment_index + take]
        segment_index += take

        target_key = _match_key(cue.text)
        current_key = "".join(_match_key(_segment_text(segment)) for segment in current_segments)
        remaining_required = required_segments_after[cue_index + 1]

        while segment_index < len(aligned_segments) and len(aligned_segments) - segment_index > remaining_required:
            if not target_key or not current_key or not target_key.startswith(current_key):
                break

            next_segment = aligned_segments[segment_index]
            candidate_key = current_key + _match_key(_segment_text(next_segment))
            if not candidate_key or not target_key.startswith(candidate_key):
                break

            current_segments.append(next_segment)
            segment_index += 1
            current_key = candidate_key

        grouped[cue_index] = current_segments

    return grouped


def split_cue_sentences(cue: SubtitleCue) -> list[str]:
    text = cue.text
    if not text:
        return []
    text = re.sub(r"\s+", " ", text).strip()
    return [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _match_key(value: str) -> str:
    return MATCH_KEY_RE.sub("", value).casefold()


def _segment_text(segment: dict[str, Any]) -> str:
    text = segment.get("text")
    return text if isinstance(text, str) else ""


def _plan_to_payload(plan: AlignmentSegmentPlan) -> dict[str, float | str]:
    return {"start": plan.start, "end": plan.end, "text": plan.text}


def _coerce_timestamp(value: Any, fallback: float) -> float:
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _ensure_srt_destination(destination: Path) -> Path:
    if destination.suffix.lower() == ".srt":
        return destination
    if destination.suffix:
        return destination.with_suffix(".srt")
    return destination.with_name(f"{destination.name}.srt")


def _select_device(prefer_gpu: bool) -> tuple[str, Any | None]:
    try:
        torch_module = importlib.import_module("torch")
    except ImportError:
        return ("cpu", None)
    if prefer_gpu and hasattr(torch_module, "cuda") and torch_module.cuda.is_available():
        return ("cuda", torch_module)
    return ("cpu", torch_module)

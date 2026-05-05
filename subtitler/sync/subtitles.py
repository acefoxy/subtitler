from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SRT_TIME_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})$"
)


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start: float
    end: float
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        return " ".join(line.strip() for line in self.lines if line.strip()).strip()

    def with_timing(self, start: float, end: float) -> "SubtitleCue":
        return SubtitleCue(index=self.index, start=start, end=end, lines=self.lines)


def load_srt(path: Path) -> list[SubtitleCue]:
    return parse_srt(path.read_text(encoding="utf-8-sig", errors="replace"))


def parse_srt(contents: str) -> list[SubtitleCue]:
    normalized = contents.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    blocks = re.split(r"\n\s*\n", normalized)
    cues: list[SubtitleCue] = []
    for fallback_index, block in enumerate(blocks, start=1):
        lines = [line.rstrip("\n") for line in block.split("\n")]
        if len(lines) < 2:
            continue

        cue_index = fallback_index
        timing_line_index = 0
        if lines[0].strip().isdigit():
            cue_index = int(lines[0].strip())
            timing_line_index = 1

        if len(lines) <= timing_line_index + 1:
            continue

        match = SRT_TIME_RE.match(lines[timing_line_index].strip())
        if match is None:
            continue

        cues.append(
            SubtitleCue(
                index=cue_index,
                start=parse_timestamp(match.group("start")),
                end=parse_timestamp(match.group("end")),
                lines=tuple(lines[timing_line_index + 1 :]),
            )
        )
    return cues


def write_srt(cues: list[SubtitleCue], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    for index, cue in enumerate(cues, start=1):
        parts.append(str(index))
        parts.append(f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}")
        parts.extend(cue.lines or ("",))
        parts.append("")
    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return path


def parse_timestamp(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_timestamp(value: float) -> str:
    total_milliseconds = max(int(round(value * 1000)), 0)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

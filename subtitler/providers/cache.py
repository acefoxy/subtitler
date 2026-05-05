from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class SubtitleSearchCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._data[key] = value
        self._save()

    def _save(self) -> None:
        with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent) as handle:
            json.dump(self._data, handle, indent=2, sort_keys=True)
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

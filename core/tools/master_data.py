"""
core.tools.master_data
======================
A reusable, domain-agnostic lookup tool over a CSV "master" file. Give it a file
path, a key column and a value; it returns the matching row (or not-found). It
caches per file and reloads automatically when the file changes on disk, so the
master files stay a live, editable input — edit the CSV and the next run sees it.

Reusable anywhere a system-of-record lookup is needed (employees, parts, assets…).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Optional

from core.tools.base_tool import BaseTool


class MasterDataTool(BaseTool):
    name = "master_data"
    description = "Look up a single row in a CSV master file by a key column (case-insensitive)."
    params = {
        "path": "path to the master CSV",
        "key_column": "column to match on",
        "value": "value to look up",
    }

    def __init__(self) -> None:
        super().__init__()
        self._cache: Dict[str, Any] = {}  # path -> (mtime, key_column, index)

    def _index(self, path: Path, key_column: str) -> Dict[str, Dict[str, Any]]:
        mtime = path.stat().st_mtime
        cached = self._cache.get(str(path))
        if cached and cached[0] == mtime and cached[1] == key_column:
            return cached[2]
        index: Dict[str, Dict[str, Any]] = {}
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                key = (row.get(key_column) or "").strip().lower()
                if key:
                    index[key] = row
        self._cache[str(path)] = (mtime, key_column, index)
        return index

    def _run(self, path: str, key_column: str, value: Any = None, **_: Any) -> Dict[str, Any]:
        # "checked" is False when we genuinely couldn't look up (no file / no value)
        if value in (None, ""):
            return {"checked": False, "found": False, "row": None}
        p = Path(path)
        if not p.exists():
            return {"checked": False, "found": False, "row": None}
        row = self._index(p, key_column).get(str(value).strip().lower())
        return {"checked": True, "found": row is not None, "row": row}

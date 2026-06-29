"""
core.tools.record_store
=====================
A reusable lookup tool over **structured data** (CSV or JSON). Generic on
purpose: "find the record(s) where field == value". Use it for policy masters,
customer tables, KYC registries, product catalogues, claims history — anything
tabular.

    store.run(source="data/structured/policies.csv",
              key="policy_number", value="AUTO-2024-88231")
    -> {"record": {...}, "count": 1}

    store.run(source="...", where={"policy_number": "X", "status": "PAID"}, multi=True)
    -> {"records": [...], "count": n}
"""
from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.tools.base_tool import BaseTool


@lru_cache(maxsize=32)
def _load_rows(source: str) -> tuple:
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(source)
    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("records", [])
    elif p.suffix.lower() in {".csv", ".tsv"}:
        delim = "\t" if p.suffix.lower() == ".tsv" else ","
        with p.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f, delimiter=delim))
    else:
        raise ValueError(f"Unsupported structured source: {p.suffix}")
    # tuple of items() so it's hashable/cacheable
    return tuple(tuple(sorted(r.items())) for r in rows)


def _rows(source: str) -> List[Dict[str, Any]]:
    return [dict(r) for r in _load_rows(source)]


def clear_cache() -> None:
    """Invalidate the file cache (call after a structured-data file is replaced)."""
    _load_rows.cache_clear()


def _eq(a: Any, b: Any) -> bool:
    return str(a).strip().lower() == str(b).strip().lower()


class RecordStoreTool(BaseTool):
    name = "record_store"
    description = "Look up structured records (CSV/JSON) by a key field or filter."
    params = {
        "source": "path to a .csv or .json structured data file",
        "key": "field name to match on (use with `value`)",
        "value": "value to match for `key`",
        "where": "dict of {field: value} that must ALL match (alternative to key/value)",
        "multi": "if true, return all matches under 'records' instead of one",
    }

    def _run(
        self,
        source: str,
        key: Optional[str] = None,
        value: Any = None,
        where: Optional[Dict[str, Any]] = None,
        multi: bool = False,
        **_: Any,
    ) -> Dict[str, Any]:
        rows = _rows(source)
        if where:
            matches = [r for r in rows if all(_eq(r.get(k), v) for k, v in where.items())]
        elif key is not None and value is not None:
            matches = [r for r in rows if _eq(r.get(key), value)]
        else:
            matches = rows
        if multi:
            return {"records": matches, "count": len(matches)}
        return {"record": matches[0] if matches else None, "count": len(matches)}

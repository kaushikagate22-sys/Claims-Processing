"""
core.utils.matching
=================
Generic, reusable helpers for fuzzy comparison of the kind almost every
record-validation task needs: lenient date parsing, name normalisation/matching,
and numeric coercion. Domain-agnostic — usable for KYC, dedup, entity matching.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d %b %Y", "%d %B %Y")


def parse_date(value: Any, formats=DATE_FORMATS) -> Optional[datetime]:
    """Parse a date string trying several common formats; None if unparseable."""
    if not value:
        return None
    s = str(value).strip()
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def normalize_name(name: Any) -> set:
    """Lowercase, strip parentheticals/punctuation -> set of name tokens."""
    s = re.sub(r"\(.*?\)", " ", str(name or "").lower())
    s = re.sub(r"[^a-z\s]", " ", s)
    return {t for t in s.split() if t}


def names_match(candidate: Any, *targets: Any, jaccard: float = 0.5) -> bool:
    """
    True if `candidate` plausibly matches any of `targets`.
    Matches when one name's tokens are a subset of the other's, or when token
    Jaccard similarity >= `jaccard` (handles middle names, ordering, suffixes).
    """
    c = normalize_name(candidate)
    if not c:
        return False
    for target in targets:
        t = normalize_name(target)
        if not t:
            continue
        shorter, longer = (c, t) if len(c) <= len(t) else (t, c)
        if shorter and shorter.issubset(longer):
            return True
        if len(c & t) / max(len(c | t), 1) >= jaccard:
            return True
    return False


def to_number(value: Any, default: float = 0.0) -> float:
    """Coerce '₹1,250,000' / '1250000.0' / None -> float, with a default."""
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("₹", "").strip())
    except (TypeError, ValueError):
        return default

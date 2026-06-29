"""
domain.policy_compiler
====================
Make the **policy document the single source of truth**.

`PolicyCompiler` reads `data/policies/master_policy.md`, extracts the per-claim-type
values (coverage limit, deductible, exclusion keywords) and regenerates the
`claim_types:` block of `config/rules.yaml`. The structural `rules:` block (the
rule *definitions*) is preserved untouched, because those don't change when a
limit or exclusion changes.

Two extraction paths (same pattern as the rest of the platform):
  * LLM path  — used when ANTHROPIC_API_KEY is set; robust to free-form wording.
  * offline   — deterministic regex parser; reliably handles the numeric values
                (the most common edits) and best-effort exclusion keywords.

Usage:
    from domain.policy_compiler import PolicyCompiler
    result = PolicyCompiler().compile(dry_run=True)   # preview
    PolicyCompiler().compile()                         # write rules.yaml (+ .bak)
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from config.settings import get_settings
from core.tools.llm_client import LLMClient
from core.utils.logger import get_logger
from core.utils.matching import to_number

log = get_logger("policy_compiler")

# header keyword -> canonical claim type
SECTION_TO_TYPE = {
    "auto": ("auto", "motor"),
    "health": ("health", "medical"),
    "travel": ("travel",),
    "property": ("property", "home"),
    "life": ("life",),
}

DEFAULT_REQUIRED = ["policy_number", "claimant_name", "incident_date", "claim_amount"]

LLM_SCHEMA = {
    "coverage_limit": "maximum coverage amount as a plain number, no symbols",
    "deductible": "deductible amount as a plain number, 0 if none",
    "exclusion_keywords": "JSON array of short lowercase single-word keywords for excluded causes",
}

_STOP = {
    "the", "and", "or", "of", "to", "a", "an", "under", "within", "while", "due",
    "from", "for", "unless", "is", "are", "damage", "claims", "claim", "policy",
    "first", "valid", "no", "not", "any", "all", "purchased", "rider", "months",
    "during", "term", "their", "with", "without", "result", "results", "loss",
    "after", "before", "physical", "products", "product", "period", "items",
    "areas", "manufacturing", "defects", "faults", "term", "this", "that",
}


class PolicyCompiler:
    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or LLMClient()

    # ------------------------------------------------------------------
    def compile(
        self,
        policy_path: Optional[str] = None,
        rules_path: Optional[str] = None,
        write: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        settings = get_settings()
        ppath = Path(policy_path or settings.master_policy)
        rpath = Path(rules_path or settings.rules_path)
        text = ppath.read_text(encoding="utf-8")

        sections = self._split_sections(text)
        claim_types = {ct: self._compile_section(ct, sec) for ct, sec in sections.items()}

        existing = {}
        if rpath.exists():
            existing = yaml.safe_load(rpath.read_text(encoding="utf-8")) or {}

        # Safety: never overwrite a populated config with an empty one. If the
        # document has no numeric-limit sections (e.g. a checklist-style
        # rulebook), keep the existing hand-authored/Admin-managed claim_types.
        if not claim_types and existing.get("claim_types"):
            log.warning("no numeric claim-type sections found; preserving existing claim_types")
            claim_types = existing["claim_types"]

        # Preserve per-type extraction_schema added via Admin (config-driven fields)
        prev_types = (existing or {}).get("claim_types", {})
        for ct, cfg in claim_types.items():
            prev_schema = (prev_types.get(ct) or {}).get("extraction_schema")
            if prev_schema:
                cfg["extraction_schema"] = prev_schema

        compiled = {"claim_types": claim_types, "rules": existing.get("rules", [])}
        diff = self._diff(existing.get("claim_types", {}), claim_types)

        if write and not dry_run:
            if rpath.exists():
                backup = rpath.with_suffix(".yaml.bak")
                shutil.copy(rpath, backup)
                log.info("backed up existing rules to %s", backup.name)
            rpath.write_text(self._dump(compiled), encoding="utf-8")
            log.info("wrote %s (%d claim types)", rpath.name, len(claim_types))

        return {
            "compiled": compiled,
            "diff": diff,
            "n_types": len(claim_types),
            "source": str(ppath),
            "mode": self.llm.mode,
            "written": write and not dry_run,
        }

    # ------------------------------------------------------------------
    def _split_sections(self, text: str) -> Dict[str, str]:
        """Split the doc into {claim_type: section_text} on '## ' headers.

        The claim type is derived from the header itself (alias map for the
        known ones, otherwise the first word of the heading), so a brand-new
        section like '## WARRANTY CLAIMS' becomes a 'warranty' type with no
        code change. Only sections that look like claim-type sections (they
        contain a 'coverage limit' line) are kept — intros are ignored.
        """
        sections: Dict[str, str] = {}
        current_type: Optional[str] = None
        buf: List[str] = []

        def flush():
            if current_type and buf:
                body = "\n".join(buf).strip()
                if re.search(r"coverage\s*limit", body, re.IGNORECASE):
                    sections[current_type] = body

        for line in text.splitlines():
            if line.lstrip().startswith("## "):
                flush()
                buf = [line]
                current_type = self._type_from_header(line)
            elif current_type:
                buf.append(line)
        flush()
        return sections

    @staticmethod
    def _type_from_header(line: str) -> Optional[str]:
        header = line.lstrip("# ").strip().lower()
        for ct, kws in SECTION_TO_TYPE.items():
            if any(k in header for k in kws):
                return ct
        toks = re.findall(r"[a-z]+", header)
        return toks[0] if toks else None

    def _compile_section(self, ctype: str, section: str) -> Dict[str, Any]:
        offline = self._offline(section, ctype)
        if self.llm.mode in ("anthropic", "openai"):
            try:
                via_llm = self._via_llm(section)
                # prefer LLM values, fall back to offline where LLM is empty
                merged = {**offline, **{k: v for k, v in via_llm.items() if v not in (None, [], "")}}
                offline = merged
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM compile failed for %s, using offline (%s)", ctype, exc)
        offline.setdefault("required_fields", DEFAULT_REQUIRED)
        return offline

    # --- LLM path ------------------------------------------------------
    def _via_llm(self, section: str) -> Dict[str, Any]:
        data = self.llm.extract_json(
            f"Insurance policy section:\n'''\n{section}\n'''",
            LLM_SCHEMA,
            system="Extract policy parameters precisely.",
        )
        out: Dict[str, Any] = {}
        if data.get("coverage_limit") is not None:
            out["coverage_limit"] = to_number(data["coverage_limit"])
        if data.get("deductible") is not None:
            out["deductible"] = to_number(data["deductible"])
        kws = data.get("exclusion_keywords")
        if isinstance(kws, str):
            try:
                kws = json.loads(kws)
            except json.JSONDecodeError:
                kws = [k.strip() for k in kws.split(",") if k.strip()]
        if isinstance(kws, list) and kws:
            out["exclusion_keywords"] = [str(k).lower().strip() for k in kws]
        return out

    # --- offline deterministic path ------------------------------------
    def _offline(self, section: str, ctype: str = "") -> Dict[str, Any]:
        bullets = self._bullets(section)
        return {
            "coverage_limit": self._first_number(bullets.get("coverage limit", "")),
            "deductible": self._deductible(bullets.get("deductible", "")),
            "exclusion_keywords": self._exclusions(bullets.get("exclusions", ""), ctype),
            "required_fields": DEFAULT_REQUIRED,
        }

    @staticmethod
    def _bullets(section: str) -> Dict[str, str]:
        """Parse '- **Label:** value' bullets, joining wrapped continuation lines."""
        out: Dict[str, str] = {}
        matches = list(re.finditer(r"-\s*\*\*([^:*]+):\*\*", section))
        for i, mt in enumerate(matches):
            label = mt.group(1).strip().lower()
            start = mt.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
            out[label] = re.sub(r"\s+", " ", section[start:end]).strip()
        return out

    @staticmethod
    def _first_number(text: str) -> Optional[float]:
        m = re.search(r"([\d][\d,]*)", text)
        return to_number(m.group(1)) if m else None

    def _deductible(self, text: str) -> float:
        if re.search(r"\b(none|nil|no deductible)\b", text, re.IGNORECASE):
            return 0.0
        n = self._first_number(text)
        return n if n is not None else 0.0

    def _exclusions(self, seg: str, ctype: str = "") -> List[str]:
        if not seg:
            return []
        seg = seg.lower()
        kws: List[str] = []
        for part in re.split(r"[;,]", seg):
            # single/two-word parentheticals are good keywords; longer ones are
            # usually conditions ("unless a flood rider is purchased") -> skip
            for paren in re.findall(r"\(([^)]+)\)", part):
                if len(paren.split()) <= 2:
                    kws.append(paren.strip())
            cleaned = re.sub(r"\([^)]*\)", " ", part)
            words = [w for w in re.findall(r"[a-z][a-z\-]+", cleaned) if w not in _STOP and len(w) > 3]
            kws.extend(words[:2])
        seen, out = set(), []
        ban = {ctype.lower(), (ctype.lower() + "s")} if ctype else set()
        for k in kws:
            if k and k not in seen and k not in ban:
                seen.add(k)
                out.append(k)
        return out[:8]

    # --- output / diff -------------------------------------------------
    @staticmethod
    def _diff(old: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        changes: List[str] = []
        for ct, cfg in new.items():
            if ct not in old:
                changes.append(f"+ new claim type '{ct}'")
                continue
            for key in ("coverage_limit", "deductible", "exclusion_keywords"):
                o, n = old[ct].get(key), cfg.get(key)
                if o != n:
                    changes.append(f"~ {ct}.{key}: {o} -> {n}")
        for ct in old:
            if ct not in new:
                changes.append(f"- removed claim type '{ct}'")
        return changes or ["(no changes)"]

    @staticmethod
    def _dump(compiled: Dict[str, Any]) -> str:
        header = (
            "# =============================================================\n"
            "# config/rules.yaml  (AUTO-GENERATED by domain.policy_compiler)\n"
            "# Source of truth: data/policies/master_policy.md\n"
            "# Re-run `python examples/compile_policy.py` after editing the policy.\n"
            "# The `claim_types` block below is regenerated; `rules` is preserved.\n"
            "# =============================================================\n\n"
        )
        return header + yaml.safe_dump(compiled, sort_keys=False, allow_unicode=True)

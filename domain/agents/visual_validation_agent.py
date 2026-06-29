"""
domain.agents.visual_validation_agent
=====================================
Step 4.5 · Visual validation — check the claim's photos against the per-type
visual criteria defined in config (Admin -> Claim types -> Visual checks).

Thin domain agent: it pulls the 3 criteria for the claim type and hands the
images + criteria to the reusable ``vision`` tool, which reports an observation
for each criterion. The fact ``photo_consistent`` is true unless a criterion is
positively failed.

Reads  context: image_paths, extracted, claim_type, policy_config
Writes context: facts[photo_consistent], visual_validation
"""
from __future__ import annotations

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context


class VisualValidationAgent(BaseAgent):
    """Step 4.5 · Compare claim photos against the type's 3 visual criteria."""

    name = "visual"

    def _criteria(self, context: Context, ctype):
        cfg = context.get("policy_config") or {}
        crit = cfg.get("visual_checks")
        if crit:
            return crit
        # fall back to loading config directly if policy_config wasn't set
        try:
            from domain.type_config import get_type_config
            return get_type_config(ctype).get("visual_checks") or []
        except Exception:  # noqa: BLE001
            return []

    def act(self, context: Context) -> str:
        images = context.get("image_paths", []) or []
        ext = context.get("extracted", {}) or {}
        facts = context.get("facts", {}) or {}
        ctype = context.get("claim_type")
        criteria = self._criteria(context, ctype)

        res = self.tools.call(
            "vision", images=images, description=ext.get("description") or "",
            criteria=criteria,
        )
        v = res.data if res.ok else {
            "assessed": False, "photos_provided": bool(images), "photo_count": len(images),
            "checks": [], "consistent": None, "mismatches": [], "confidence": 0.0,
            "findings": "Visual step failed."}

        # benefit of the doubt: only a positive mismatch (consistent is False) penalises
        facts["photo_consistent"] = True if v.get("consistent") is None else bool(v.get("consistent"))
        facts["photos_provided"] = v.get("photos_provided", bool(images))
        facts["visual_confidence"] = v.get("confidence", 0.0)
        context.set("facts", facts)
        context.set("visual_validation", v)

        if not v.get("photos_provided"):
            return "no photos provided"
        if not v.get("assessed"):
            return f"{v.get('photo_count', 0)} photo(s) — not assessed"
        passed = sum(1 for c in v.get("checks", []) if c.get("pass"))
        total = len(v.get("checks", []))
        return (f"{v.get('photo_count', 0)} photo(s) — {passed}/{total} criteria met"
                f"{'' if v.get('consistent') else ' — MISMATCH'}")

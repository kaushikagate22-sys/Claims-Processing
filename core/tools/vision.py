"""
core.tools.vision
=================
Reusable, domain-agnostic image inspector. Given image(s), a description, and a
list of named *criteria*, it asks the vision LLM to judge EACH criterion and
return a per-criterion observation. The overall verdict (consistent) is derived
from the criteria. Never throws into the pipeline.

Result keys:
  assessed, photos_provided, photo_count,
  checks: [{criterion, pass, observation}],
  consistent (all checks pass), mismatches (failed observations),
  confidence, findings

Graceful degradation:
  - no images / vision offline -> assessed=False, consistent=None
  - VISION_MOCK = "match" | "mismatch" -> canned per-criterion verdict (tests/demos)
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from core.tools.base_tool import BaseTool
from core.tools.llm_client import LLMClient


class VisionTool(BaseTool):
    name = "vision"
    description = "Judge image(s) against a list of named criteria for a claim."
    params = {
        "images": "list of image file paths or raw bytes",
        "description": "the claim description for context",
        "criteria": "list of criteria strings to evaluate against the image(s)",
    }

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        super().__init__()
        self.llm = llm or LLMClient()

    def _base(self, images) -> Dict[str, Any]:
        return {"assessed": False, "photos_provided": bool(images), "photo_count": len(images),
                "checks": [], "consistent": None, "mismatches": [], "confidence": 0.0, "findings": ""}

    @staticmethod
    def _finalize(res: Dict[str, Any]) -> Dict[str, Any]:
        checks = res.get("checks") or []
        if checks:
            res["consistent"] = all(c.get("pass") for c in checks)
            res["mismatches"] = [c.get("observation") or c.get("criterion") for c in checks if not c.get("pass")]
        return res

    def _run(self, images: Optional[List[Any]] = None, description: str = "",
             criteria: Optional[List[str]] = None, **_: Any) -> Dict[str, Any]:
        images = images or []
        criteria = [c for c in (criteria or []) if c] or ["The photo is consistent with the claim."]
        res = self._base(images)

        if not images:
            res["findings"] = "No photos were provided with this claim."
            return res

        mock = os.getenv("VISION_MOCK")
        if mock in ("match", "mismatch"):
            ok = mock == "match"
            res["assessed"] = True
            res["checks"] = [{"criterion": c,
                              "pass": ok if i == 0 else ok,  # all pass on match, all fail on mismatch
                              "observation": ("Consistent with the claim (mock)." if ok
                                              else "Not supported by the photo (mock).")}
                             for i, c in enumerate(criteria)]
            res["confidence"] = 0.9 if ok else 0.8
            res["findings"] = ("Photos support the claim (mock)." if ok
                               else "Photos do not support the claim (mock).")
            return self._finalize(res)

        if not getattr(self.llm, "vision_available", False):
            res["findings"] = "Vision model unavailable (offline); photos were not assessed."
            return res

        numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))
        prompt = (
            "You are a claims photo inspector. Evaluate the attached photo(s) against EACH "
            "criterion below. For each, decide pass (true/false) and give a one-sentence "
            "observation of what you actually see.\n\n"
            f"Claim description: {description}\n\n"
            f"Criteria:\n{numbered}\n\n"
            'Respond with ONLY JSON: {"checks":[{"criterion":"<repeat the criterion>",'
            '"pass":true|false,"observation":"..."}],"confidence":0.0-1.0,'
            '"summary":"one-sentence overall assessment"}.'
        )
        try:
            raw = self.llm.analyze_images(prompt, images, json_mode=True)
            v = json.loads(raw) if raw else {}
            checks = v.get("checks") or []
            # normalise to exactly the requested criteria order/labels
            norm = []
            for i, c in enumerate(criteria):
                src = checks[i] if i < len(checks) else {}
                norm.append({"criterion": c, "pass": bool(src.get("pass")),
                             "observation": src.get("observation", "")})
            res.update({"assessed": True, "checks": norm,
                        "confidence": float(v.get("confidence", 0.0)),
                        "findings": v.get("summary", "")})
            return self._finalize(res)
        except Exception as exc:  # noqa: BLE001
            res["findings"] = f"Vision analysis could not be completed ({exc})."
            return res

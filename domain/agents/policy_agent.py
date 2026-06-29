"""
domain.agents.policy_agent
==========================
Step 3 · Compare the claim against its claim-type rulebook.

Loads the per-type config from rules.yaml and derives the facts the shared
checks evaluate: excluded cause, completeness (mandatory fields present),
high-value flag and escalation triggers. The `record`-based duplicate flag is
filled later by the ValidationAgent.

Reads  context: claim_text, claim_type, extracted
Writes context: facts, policy_context, policy_config
"""
from __future__ import annotations

from typing import Any, Dict

from config.settings import get_settings, load_rules
from core.agents.base_agent import BaseAgent
from core.schemas.base import Context


class PolicyAgent(BaseAgent):
    """Step 3 · Build the per-type facts the rulebook checks evaluate."""

    name = "policy"

    def act(self, context: Context) -> str:
        settings = get_settings()
        rules_cfg = load_rules()
        ctype = context.get("claim_type")
        extracted = context.get("extracted", {}) or {}

        configured = bool(ctype) and ctype in rules_cfg.get("claim_types", {})
        context.set("type_configured", configured)
        if not configured:
            context.set("facts", {**self._flat(extracted)})
            context.set("policy_config", {})
            return (f"claim_type {ctype!r} not configured; "
                    f"supported={list(rules_cfg.get('claim_types', {}))}")

        cfg = rules_cfg["claim_types"][ctype]
        context.set("policy_config", cfg)

        flat = self._flat(extracted)
        text = " ".join([
            str(context.get("claim_text", "")),
            str(extracted.get("description") or ""),
        ]).lower()

        required = cfg.get("required_fields", [])
        missing = [f for f in required if not self._present(flat.get(f))]
        amount = self._num(flat.get("claim_amount"))
        excluded = any(kw.lower() in text for kw in cfg.get("exclusion_keywords", []))
        needs_esc = any(kw.lower() in text for kw in cfg.get("escalate_keywords", []))
        threshold = cfg.get("high_value_threshold")
        high_value = bool(threshold) and amount > float(threshold)

        facts: Dict[str, Any] = {
            **flat,
            "claim_amount": amount,
            "excluded": excluded,
            "needs_escalation": needs_esc,
            "high_value": high_value,
            "complete": len(missing) == 0,
            "missing_fields": missing,
            "is_duplicate": False,  # ValidationAgent may set True
        }
        facts.update(self._derive_type_specific(ctype, flat))
        context.set("facts", facts)

        # RAG: pull the relevant rulebook section for citations/context
        try:
            policy_text = settings.master_policy.read_text(encoding="utf-8")
            rag = self.tools.call("retriever", text=policy_text,
                                  query=f"{cfg.get('label', ctype)} rules exclusions documents",
                                  top_k=settings.top_k)
            context.set("policy_context", rag.data["context"] if rag.ok else policy_text)
        except Exception:  # noqa: BLE001
            context.set("policy_context", "")

        return (f"type={ctype} amount={amount} excluded={excluded} "
                f"missing={missing} high_value={high_value}")

    @staticmethod
    def _derive_type_specific(ctype: str, flat: Dict[str, Any]) -> Dict[str, Any]:
        """Extra booleans referenced by per-type checks (only what we can
        compute from the claim's own content — no master data)."""
        from core.utils.matching import parse_date
        out: Dict[str, Any] = {}
        if ctype == "nepi":
            hs = str(flat.get("handover_status") or "").lower()
            # fail only if the customer has explicitly accepted (post-handover)
            out["handover_open"] = "accept" not in hs
            d1 = parse_date(flat.get("dispatch_date"))
            d2 = parse_date(flat.get("inspection_date"))
            # pass unless we positively know dispatch is after inspection
            out["dispatch_before_inspection"] = not (d1 and d2 and d1 > d2)
        if ctype == "employee_reimbursement":
            ma = str(flat.get("manager_approval") or "").strip().lower()
            out["manager_approval_ok"] = ma not in ("", "no", "none", "false", "null", "pending", "0")
        return out

    @staticmethod
    def _flat(extracted: Dict[str, Any]) -> Dict[str, Any]:
        flat = {k: v for k, v in extracted.items() if k != "extra"}
        flat.update(extracted.get("extra") or {})
        return flat

    @staticmethod
    def _present(v: Any) -> bool:
        return v not in (None, "", [], {})

    @staticmethod
    def _num(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

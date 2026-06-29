"""
domain.agents.adjudication_agent
=============================
Step 4. The decision engine. Runs the declarative rules (deterministic) and maps
the outcome to a decision, then writes the final ClaimDecisionReport.

Decision logic:
  * any *eligibility* HARD failure  -> REJECTED   (e.g. excluded cause, lapsed policy)
  * else any *completeness* HARD fail -> PENDING  (missing required info)
  * else if amount exceeds limit (soft) -> PARTIALLY_APPROVED (pay up to limit)
  * else                              -> APPROVED

Payout = (claim_amount or limit) - deductible, floored at 0.

Reads  context: payload["facts"], payload["extracted"], payload["claim_type"],
                payload["policy_context"], payload["policy_config"],
                payload["completeness"]
Writes context: payload["adjudication"], payload["report"]
"""
from __future__ import annotations

from typing import Any, Dict, List

from config.settings import load_rules
from core.agents.base_agent import BaseAgent
from core.schemas.base import Context
from domain.schemas.claim import (
    Adjudication,
    ClaimDecisionReport,
    Decision,
    ExtractedClaim,
    RuleOutcome,
)


class AdjudicationAgent(BaseAgent):
    """Step 4 · Decide the claim and emit the final report.

    Runs the declarative rules deterministically and maps the outcome to a
    decision — REJECTED / PENDING_INFORMATION / MANUAL_REVIEW /
    PARTIALLY_APPROVED / APPROVED — computing payout as
    ``(claim_amount or limit) - deductible`` floored at 0.

    Reads  ``payload['facts','extracted','claim_type','policy_context','policy_config','completeness']``.
    Writes ``payload['adjudication']`` and the ``ClaimDecisionReport`` in ``payload['report']``.
    """

    name = "adjudication"

    def act(self, context: Context) -> str:
        facts = context.get("facts")
        if not facts:
            raise ValueError("adjudication requires payload['facts']")

        # Graceful path: claim type has no configured guidelines.
        if not context.get("type_configured", True):
            from domain.type_config import supported_types
            ctype = context.get("claim_type")
            supported = ", ".join(supported_types())
            adjudication = Adjudication(
                decision=Decision.HOLD,
                approved_amount=0.0,
                confidence=0.3,
                reasons=[
                    f"Claim type {ctype or 'unknown'!r} is not configured, so there "
                    f"are no guidelines to assess it against. Configured types: {supported}."
                ],
                next_steps=[
                    "Add this claim type in Admin (a policy section defines its rules; "
                    "the Claim types tab defines its fields), then resubmit."
                ],
            )
            context.set("adjudication", adjudication.model_dump())
            report = self._build_report(context, adjudication)
            context.set("report", report.model_dump())
            return f"decision=HOLD (unconfigured type {ctype!r})"

        # bring the settlement cap (if any) into facts for payout calc
        cfg = context.get("policy_config", {}) or {}
        if cfg.get("settlement_cap") is not None:
            facts = {**facts, "settlement_cap": cfg.get("settlement_cap")}

        # Per-type checklist if configured, else the shared fallback checks.
        rules = cfg.get("checks") or load_rules()["rules"]
        res = self.tools.call("rules_engine", facts=facts, rules=rules)
        if not res.ok:
            raise RuntimeError(f"rules engine failed: {res.error}")
        engine = res.data

        decision, reasons, payout = self._decide(engine, facts)
        outcomes = [
            RuleOutcome(
                id=r["id"], severity=r["severity"], passed=r["passed"], message=r["message"]
            )
            for r in engine["results"]
        ]

        adjudication = Adjudication(
            decision=decision,
            approved_amount=payout,
            confidence=self._confidence(context, decision),
            reasons=reasons,
            rule_outcomes=outcomes,
            policy_citations=self._citations(context.get("policy_context", "")),
            next_steps=self._next_steps(decision, engine),
        )
        context.set("adjudication", adjudication.model_dump())

        report = self._build_report(context, adjudication)
        context.set("report", report.model_dump())

        return f"decision={decision.value} payout={payout} confidence={adjudication.confidence}"

    # ------------------------------------------------------------------
    def _decide(self, engine: Dict[str, Any], facts: Dict[str, Any]):
        results = engine["results"]
        fails = [r for r in results if not r["passed"]]
        reject = [r for r in fails if r["severity"] == "reject"]
        hold = [r for r in fails if r["severity"] == "hold"]
        escalate = [r for r in fails if r["severity"] == "escalate"]

        amount = float(facts.get("claim_amount") or 0)
        cap = facts.get("settlement_cap")
        cfg_cap = None
        try:
            cfg_cap = float(cap) if cap is not None else None
        except (TypeError, ValueError):
            cfg_cap = None

        if reject:
            return Decision.REJECT, [r["message"] for r in reject], 0.0

        if hold:
            reasons = [r["message"] for r in hold]
            missing = facts.get("missing_fields") or []
            if missing:
                reasons = [f"Missing mandatory fields/documents: {', '.join(missing)}."]
            return Decision.HOLD, reasons, 0.0

        if escalate:
            return Decision.ESCALATE, [r["message"] for r in escalate], 0.0

        payable = amount
        if cfg_cap is not None:
            payable = min(amount, cfg_cap)
        return Decision.APPROVE, ["All eligibility, document and value checks passed."], round(payable, 2)

    @staticmethod
    def _category(rule_id: str) -> str:
        for r in load_rules()["rules"]:
            if r["id"] == rule_id:
                return r.get("category", "eligibility")
        return "eligibility"

    @staticmethod
    def _confidence(context: Context, decision: Decision) -> float:
        completeness = float(context.get("completeness") or 0)
        base = 0.55 + 0.4 * completeness
        if decision == Decision.HOLD:
            base -= 0.15
        return round(min(max(base, 0.0), 0.99), 2)

    @staticmethod
    def _citations(policy_context: str) -> List[str]:
        lines = [ln.strip() for ln in policy_context.splitlines() if ln.strip()]
        return [ln for ln in lines if ln.startswith("##") or "Exclusions" in ln or "Coverage limit" in ln][:4]

    @staticmethod
    def _next_steps(decision: Decision, engine: Dict[str, Any]) -> List[str]:
        if decision == Decision.HOLD:
            return [f"Provide: {r['message']}" for r in engine["results"]
                    if not r["passed"] and r["severity"] == "hold"] or ["Provide the missing documents/fields."]
        if decision == Decision.REJECT:
            return ["Claim does not meet eligibility; claimant may appeal with evidence."]
        if decision == Decision.ESCALATE:
            return ["Route to a human approver: high value or escalation trigger present."]
        return ["Approved — proceed to settlement up to the eligible amount."]

    def _build_report(self, context: Context, adjudication: Adjudication) -> ClaimDecisionReport:
        ctype = context.get("claim_type")
        extracted = ExtractedClaim(**context.get("extracted", {}))
        return ClaimDecisionReport(
            run_id=context.run_id,
            claim_type=ctype,
            extracted=extracted,
            adjudication=adjudication,
            validation=context.get("validation", {}) or {},
            completeness=float(context.get("completeness") or 0),
            trace=[t.model_dump() for t in context.trace],
        )

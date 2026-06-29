"""
domain.agents.summarizer_agent
==============================
Step 6 · Produce the human-readable audit summary of the decision.

Thin domain agent: it only decides *which* claim facts matter, then delegates
the actual prose-writing to the reusable ``summarizer`` core tool.

Reads  context: extracted, claim_type, adjudication
Writes context: summary
"""
from __future__ import annotations

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context


class SummarizerAgent(BaseAgent):
    """Step 6 · Write a concise audit summary via the reusable summarizer tool."""

    name = "summarizer"

    def act(self, context: Context) -> str:
        adj = context.get("adjudication", {}) or {}
        ext = context.get("extracted", {}) or {}
        decision = adj.get("decision")
        decision = getattr(decision, "value", decision)
        outcomes = adj.get("rule_outcomes", []) or []
        npass = sum(1 for o in outcomes if o.get("passed"))
        nfail = len(outcomes) - npass

        facts = {
            "claim type": context.get("claim_type"),
            "claimant": ext.get("claimant_name"),
            "reference": ext.get("claim_reference"),
            "decision": decision,
            "amount payable": adj.get("approved_amount"),
            "amount claimed": ext.get("claim_amount"),
            "checks": f"{npass} passed, {nfail} failed",
            "primary reason": (adj.get("reasons") or [None])[0],
        }
        res = self.tools.call(
            "summarizer",
            headline=f"Claim {decision}",
            facts=facts,
            instructions="Summarise this claims decision for an audit trail. Be plain, factual and neutral.",
            max_words=70,
        )
        summary = res.data.get("summary", "") if res.ok else ""
        context.set("summary", summary)
        return f"summary ready ({len(summary.split())} words)"

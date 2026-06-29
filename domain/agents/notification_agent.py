"""
domain.agents.notification_agent
================================
Step 7 · Notify the right stakeholder about the outcome.

Thin domain agent: it owns only the *routing* (who to tell, in what words, for
each decision) and delegates delivery to the reusable ``notifier`` core tool —
whose sink can be swapped for real email/Slack without changing this agent.

Reads  context: extracted, claim_type, adjudication, summary
Writes context: notification
"""
from __future__ import annotations

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context

# Domain routing: decision -> who is notified and how it's framed.
DECISION_ROUTING = {
    "APPROVED": {"to": "Dealer + Finance", "channel": "email", "verb": "approved for settlement"},
    "HOLD":     {"to": "Dealer",           "channel": "email", "verb": "placed on hold pending documents"},
    "ESCALATE": {"to": "Reviewer / Manager", "channel": "email", "verb": "escalated for review"},
    "REJECTED": {"to": "Dealer",           "channel": "email", "verb": "rejected"},
}


class NotificationAgent(BaseAgent):
    """Step 7 · Prepare and dispatch the stakeholder notification."""

    name = "notification"

    def act(self, context: Context) -> str:
        adj = context.get("adjudication", {}) or {}
        ext = context.get("extracted", {}) or {}
        decision = adj.get("decision")
        decision = getattr(decision, "value", decision)
        route = DECISION_ROUTING.get(decision, {"to": "Reviewer", "channel": "email", "verb": "updated"})

        ctype = (context.get("claim_type") or "claim").replace("_", " ")
        ref = ext.get("claim_reference") or ctype
        subject = f"Claim {ref} — {decision}"
        body = self._draft_email(route, ctype, ref, ext, adj, context.get("summary"))

        res = self.tools.call("notifier", to=route["to"], subject=subject, body=body, channel=route["channel"])
        note = dict(res.data) if res.ok else {"status": "failed"}
        note.update({"recipient": route["to"], "decision": decision})
        context.set("notification", note)
        return f"notification {note.get('status', '?')} -> {route['to']}"

    @staticmethod
    def _draft_email(route, ctype, ref, ext, adj, summary) -> str:
        """Compose the human-readable draft email (domain content; transport is the tool's job)."""
        amount = adj.get("approved_amount")
        reason = (adj.get("reasons") or [None])[0]
        nxt = (adj.get("next_steps") or [None])[0]

        lines = [f"Hi {route['to']},", ""]
        lines.append(f"Claim {ref} ({ctype}) has been {route['verb']}.")
        if amount:
            try:
                lines.append(f"Amount payable: \u20b9{int(round(float(amount))):,}.")
            except (TypeError, ValueError):
                pass
        if reason:
            lines += ["", reason]
        if nxt:
            lines += ["", f"Next step: {nxt}"]
        lines += ["", "Regards,", "Claims Manager (automated notification)"]
        return "\n".join(lines)

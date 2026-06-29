"""Summarizer + Notification agents: reusable tools produce summary & routed notice."""
from core.tools.registry import ToolRegistry
from domain.agents.claims_orchestrator import ClaimsPipeline


def test_pipeline_produces_summary_and_notification():
    r = ClaimsPipeline().process(source_path="data/sample_claims/warranty_clean.txt").model_dump()
    assert r["summary"], "expected a non-empty audit summary"
    note = r["notification"]
    assert note and note["status"] in ("queued", "sent")
    assert note["recipient"]  # routed to a stakeholder
    # all seven agents recorded
    assert [t["agent"] for t in r["trace"]][-2:] == ["summarizer", "notification"]


def test_core_tools_are_reusable_standalone():
    """The tools work without any claims domain object -> proves reusability."""
    reg = ToolRegistry.default()
    s = reg.call("summarizer", headline="Invoice paid", facts={"vendor": "Acme", "amount": 500})
    assert s.ok and "Acme" in s.data["summary"]
    n = reg.call("notifier", to="ap@co.com", subject="Paid", body="ok", channel="slack")
    assert n.ok and n.data["channel"] == "slack" and n.data["status"] == "queued"

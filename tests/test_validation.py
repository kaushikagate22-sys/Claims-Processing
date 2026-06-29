"""Duplicate-detection (system-of-record) tests for the new domain."""
from core.schemas.base import Context
from domain.agents.policy_agent import PolicyAgent
from domain.agents.validation_agent import ValidationAgent

def _run(ctype, extracted, text=""):
    ctx = Context()
    ctx.set("claim_type", ctype)
    ctx.set("extracted", extracted)
    ctx.set("claim_text", text)
    PolicyAgent().run(ctx)
    ValidationAgent().run(ctx)
    return ctx

def test_duplicate_invoice_flagged():
    ctx = _run("parts_replacement", {
        "part_number": "SP-1", "purchase_invoice": "INV-PART-9981",
        "failure_description": "failed", "claim_amount": 100})
    assert ctx.get("facts")["is_duplicate"] is True

def test_new_invoice_not_duplicate():
    ctx = _run("parts_replacement", {
        "part_number": "SP-1", "purchase_invoice": "INV-FRESH-1",
        "failure_description": "failed", "claim_amount": 100})
    assert ctx.get("facts")["is_duplicate"] is False

def test_missing_key_is_graceful():
    ctx = _run("warranty", {
        "machine_serial_number": "M1", "failure_code": "C1",
        "failed_part": "pump", "claim_amount": 100})
    v = ctx.get("validation")
    assert v["is_duplicate"] is False

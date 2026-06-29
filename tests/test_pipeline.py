"""End-to-end pipeline tests for the OEM/dealer claim types (offline mode)."""
from domain.agents.claims_orchestrator import ClaimsPipeline
from domain.schemas.claim import Decision

P = ClaimsPipeline()

def _run(name):
    return P.process(source_path=f"data/sample_claims/{name}.txt")

def test_warranty_clean_approved():
    r = _run("warranty_clean")
    assert r.claim_type == "warranty"
    assert r.adjudication.decision == Decision.APPROVE
    assert r.adjudication.approved_amount == 48000.0

def test_warranty_excluded_rejected():
    r = _run("warranty_excluded")
    assert r.adjudication.decision == Decision.REJECT
    assert any("exclud" in x.lower() for x in r.adjudication.reasons)

def test_reimbursement_missing_docs_hold():
    r = _run("reimbursement_hold")
    assert r.claim_type == "employee_reimbursement"
    assert r.adjudication.decision == Decision.HOLD
    assert any("manager_approval" in x for x in r.adjudication.reasons)

def test_parts_duplicate_rejected():
    r = _run("parts_duplicate")
    assert r.claim_type == "parts_replacement"
    assert r.adjudication.decision == Decision.REJECT
    assert any("duplicate" in x.lower() for x in r.adjudication.reasons)

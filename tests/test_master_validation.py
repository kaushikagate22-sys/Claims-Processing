"""Validation agent cross-checks claims against the editable master files."""
from core.tools.registry import ToolRegistry
from config.settings import get_settings, load_rules
from domain.agents.claims_orchestrator import ClaimsPipeline


def _decision(text):
    load_rules.cache_clear()
    r = ClaimsPipeline().process(claim_text=text).model_dump(mode="json")
    return r["adjudication"]["decision"], r


def test_known_serial_and_dealer_pass():
    dec, r = _decision(
        "WARRANTY CLAIM\nClaim Type: warranty\nClaimant Name: Sunrise Dealers\nDealer Name: Sunrise Dealers\n"
        "Machine Serial Number: MX-88231\nFailure Code: HYD-204\nFailed Part: hydraulic pump\n"
        "Job Card Number: JC-2025-3001\nClaim Amount: 48000\n")
    assert dec == "APPROVED"
    checks = {c["key"]: c["ok"] for c in r["validation"]["record_checks"]}
    assert checks.get("serial_known") and checks.get("dealer_known")


def test_unknown_serial_escalates():
    dec, r = _decision(
        "WARRANTY CLAIM\nClaim Type: warranty\nClaimant Name: Ghost Traders\nDealer Name: Ghost Traders\n"
        "Machine Serial Number: ZZ-00000\nFailure Code: HYD-204\nFailed Part: hydraulic pump\n"
        "Job Card Number: JC-9999-0001\nClaim Amount: 30000\n")
    assert dec == "ESCALATE"
    fails = {o["id"] for o in r["adjudication"]["rule_outcomes"] if not o["passed"]}
    assert "serial_in_master" in fails


def test_master_data_tool_reusable():
    reg = ToolRegistry.default()
    s = get_settings()
    hit = reg.call("master_data", path=str(s.machine_master), key_column="serial_number", value="MX-88231")
    assert hit.ok and hit.data["found"] and hit.data["row"]["status"] == "active"
    miss = reg.call("master_data", path=str(s.machine_master), key_column="serial_number", value="NOPE")
    assert miss.ok and miss.data["checked"] and not miss.data["found"]

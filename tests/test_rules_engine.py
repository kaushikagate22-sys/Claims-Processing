"""Unit tests for the reusable rules engine."""
from core.tools.rules_engine import RulesEngineTool

RULES = [
    {"id": "amt_present", "field": "amount", "op": "exists", "severity": "hard", "message": "missing"},
    {"id": "within_limit", "field": "amount", "op": "lte", "value": "$limit", "severity": "soft", "message": "over"},
    {"id": "not_excluded", "field": "excluded", "op": "falsy", "severity": "hard", "message": "excluded"},
]


def _run(facts):
    return RulesEngineTool().run(facts=facts, rules=RULES).data


def test_all_pass():
    out = _run({"amount": 100, "limit": 500, "excluded": False})
    assert out["passed_all_hard"]
    assert out["n_passed"] == 3


def test_soft_failure_over_limit():
    out = _run({"amount": 1000, "limit": 500, "excluded": False})
    assert out["passed_all_hard"]          # soft failure doesn't break hard
    assert len(out["soft_failures"]) == 1


def test_hard_failure_excluded():
    out = _run({"amount": 100, "limit": 500, "excluded": True})
    assert not out["passed_all_hard"]
    assert any(f["id"] == "not_excluded" for f in out["hard_failures"])


def test_reference_resolution():
    # $limit should resolve against the facts dict
    out = _run({"amount": 500, "limit": 500, "excluded": False})
    within = next(r for r in out["results"] if r["id"] == "within_limit")
    assert within["passed"]

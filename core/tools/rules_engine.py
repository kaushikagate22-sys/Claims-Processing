"""
core.tools.rules_engine
=====================
A small declarative rules engine. Rules are plain dicts (loadable from YAML),
so business users can edit policy logic without touching code.

A rule looks like:
    {
      "id": "amount_within_limit",
      "field": "claim_amount",
      "op": "lte",
      "value": "$coverage_limit",     # "$x" references another field in `facts`
      "severity": "hard",             # hard | soft | info
      "message": "Claim amount exceeds the coverage limit."
    }

Supported ops: eq ne gt gte lt lte in not_in exists not_exists contains
between regex truthy falsy

`severity` drives the decision layer:
  * hard  -> failing it is disqualifying (reject / partial)
  * soft  -> failing it is a warning / needs review
  * info  -> informational only
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from core.tools.base_tool import BaseTool


def _resolve(value: Any, facts: Dict[str, Any]) -> Any:
    """Allow rule values to reference another fact via '$field_name'."""
    if isinstance(value, str) and value.startswith("$"):
        return facts.get(value[1:])
    return value


def _num(x: Any):
    try:
        return float(str(x).replace(",", "").replace("$", "").strip())
    except (TypeError, ValueError):
        return None


OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "exists": lambda a, b: a is not None,
    "not_exists": lambda a, b: a is None,
    "truthy": lambda a, b: bool(a),
    "falsy": lambda a, b: not bool(a),
    "in": lambda a, b: a in (b or []),
    "not_in": lambda a, b: a not in (b or []),
    "contains": lambda a, b: (b in a) if a is not None else False,
    "regex": lambda a, b: bool(re.search(str(b), str(a))) if a is not None else False,
}

NUMERIC_OPS = {
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
}


class RulesEngineTool(BaseTool):
    name = "rules_engine"
    description = "Evaluate a list of declarative rules against a dict of facts."
    params = {
        "facts": "dict of extracted/known values to test",
        "rules": "list of rule dicts (id, field, op, value, severity, message)",
    }

    def _run(self, facts: Dict[str, Any], rules: List[Dict[str, Any]], **_: Any) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        for rule in rules:
            results.append(self._eval_rule(rule, facts))

        hard_fail = [r for r in results if not r["passed"] and r["severity"] == "hard"]
        soft_fail = [r for r in results if not r["passed"] and r["severity"] == "soft"]
        return {
            "results": results,
            "passed_all_hard": len(hard_fail) == 0,
            "hard_failures": hard_fail,
            "soft_failures": soft_fail,
            "n_rules": len(rules),
            "n_passed": sum(1 for r in results if r["passed"]),
        }

    def _eval_rule(self, rule: Dict[str, Any], facts: Dict[str, Any]) -> Dict[str, Any]:
        rid = rule.get("id", "unnamed")
        op = rule.get("op", "exists")
        severity = rule.get("severity", "hard")
        field = rule.get("field")
        actual = facts.get(field) if field else None
        expected = _resolve(rule.get("value"), facts)

        try:
            passed = self._apply(op, actual, expected)
        except Exception as exc:  # noqa: BLE001
            passed = False
            rule = {**rule, "message": f"rule error: {exc}"}

        return {
            "id": rid,
            "field": field,
            "op": op,
            "severity": severity,
            "actual": actual,
            "expected": expected,
            "passed": passed,
            "message": "" if passed else rule.get("message", f"Rule '{rid}' failed."),
        }

    @staticmethod
    def _apply(op: str, actual: Any, expected: Any) -> bool:
        if op == "between":
            a = _num(actual)
            lo, hi = expected
            return a is not None and _num(lo) <= a <= _num(hi)
        if op in NUMERIC_OPS:
            a, b = _num(actual), _num(expected)
            if a is None or b is None:
                return False
            return NUMERIC_OPS[op](a, b)
        if op in OPS:
            return OPS[op](actual, expected)
        raise ValueError(f"Unknown op '{op}'")

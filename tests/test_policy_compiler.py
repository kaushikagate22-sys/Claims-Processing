"""Compiler safety tests for the checklist-style rulebook.

The new rulebook has no numeric coverage-limit sections, so the compiler's
guard must preserve the existing (hand-authored/Admin-managed) claim_types
rather than wiping them.
"""
from domain.policy_compiler import PolicyCompiler

NEW = {"warranty", "nepi", "parts_replacement", "transit_damage", "employee_reimbursement"}

def test_compile_does_not_crash_and_preserves_types():
    res = PolicyCompiler().compile(dry_run=True)
    assert NEW.issubset(set(res["compiled"]["claim_types"]))

def test_guard_reports_no_destructive_change():
    res = PolicyCompiler().compile(dry_run=True)
    # preserving existing types => the diff should be a no-op
    assert res["diff"] == ["(no changes)"]

"""
examples/run_pipeline.py
=====================
Run the claims pipeline over one file or the whole sample folder.

    python examples/run_pipeline.py                      # all samples
    python examples/run_pipeline.py path/to/claim.txt    # single file
"""
from __future__ import annotations

import sys
from pathlib import Path

# make the project root importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings  # noqa: E402
from domain.agents.claims_orchestrator import ClaimsPipeline  # noqa: E402


def _fmt_money(x: float) -> str:
    return f"₹{x:,.0f}"


def show(report) -> None:
    a = report.adjudication
    print("\n" + "=" * 64)
    print(f"RUN {report.run_id}  |  TYPE: {report.claim_type.value if report.claim_type else '?'}")
    print("-" * 64)
    e = report.extracted
    print(f"Claimant : {e.claimant_name}")
    print(f"Policy   : {e.policy_number}")
    print(f"Amount   : {e.claim_amount}")
    print(f"Complete : {report.completeness:.0%}")
    v = report.validation or {}
    if v.get("performed"):
        print("-" * 64)
        print("RECORD VALIDATION (vs structured system of record):")
        print(f"   on record      : {v.get('policy_exists')}")
        print(f"   name match     : {v.get('name_match')}")
        print(f"   policy active  : {v.get('policy_active')}")
        print(f"   within period  : {v.get('within_policy_period')}")
        print(f"   product match  : {v.get('product_matches')}")
        print(f"   not duplicate  : {v.get('not_duplicate')}")
        if "remaining_limit" in v:
            print(f"   sum insured    : {v.get('sum_insured')}")
            print(f"   remaining limit: {v.get('remaining_limit')}")
    elif v:
        print(f"RECORD VALIDATION : not performed ({v.get('reason')})")
    print("-" * 64)
    print(f"DECISION : {a.decision.value}")
    print(f"Payout   : {_fmt_money(a.approved_amount)}")
    print(f"Confidence: {a.confidence:.0%}")
    print("Reasons  :")
    for r in a.reasons:
        print(f"   - {r}")
    if a.next_steps:
        print("Next steps:")
        for s in a.next_steps:
            print(f"   - {s}")
    print("=" * 64)


def main() -> None:
    pipeline = ClaimsPipeline()
    args = sys.argv[1:]
    if args:
        paths = [Path(args[0])]
    else:
        paths = sorted(get_settings().samples_dir.glob("*.txt"))

    for p in paths:
        report = pipeline.process(source_path=str(p))
        show(report)


if __name__ == "__main__":
    main()

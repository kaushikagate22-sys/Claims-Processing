"""
examples/save_and_list.py
=====================
Stage 1 demo: process the sample claims, SAVE each decision to the database,
then read them back out — proving persistence end to end.

    python examples/save_and_list.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings  # noqa: E402
from db.database import get_database_url, init_db  # noqa: E402
from services.claims_service import ClaimsService  # noqa: E402


def main() -> None:
    print(f"Database: {get_database_url()}\n")
    init_db()
    service = ClaimsService()

    samples = sorted(get_settings().samples_dir.glob("*.txt"))
    print(f"Processing & saving {len(samples)} claims...\n")
    for p in samples:
        saved = service.process_and_save(source_path=str(p))
        print(f"  saved #{saved['id']:>3}  {saved['claim_type'] or '?':9s} "
              f"{(saved['decision'] or '?'):20s} "
              f"payout={saved['approved_amount']:>12,.0f}  ({p.name})")

    print("\nReading back the most recent claims from the database:\n")
    print(f"  {'ID':>3}  {'TYPE':9s} {'DECISION':20s} {'CLAIMANT':20s} {'PAYOUT':>12}")
    print("  " + "-" * 70)
    for c in service.list(limit=20):
        print(f"  {c['id']:>3}  {c['claim_type'] or '?':9s} "
              f"{(c['decision'] or '?'):20s} {(c['claimant_name'] or '?'):20s} "
              f"{c['approved_amount']:>12,.0f}")


if __name__ == "__main__":
    main()

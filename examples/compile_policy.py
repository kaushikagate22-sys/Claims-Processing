"""
examples/compile_policy.py
=======================
Regenerate config/rules.yaml from the master policy document.

    python examples/compile_policy.py            # write rules.yaml (backs up old)
    python examples/compile_policy.py --dry-run  # preview the diff, write nothing

Workflow: edit data/policies/master_policy.md -> run this -> decisions update.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain.policy_compiler import PolicyCompiler  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Compile policy document -> rules.yaml")
    ap.add_argument("--dry-run", action="store_true", help="preview only, do not write")
    ap.add_argument("--policy", help="path to the policy document")
    ap.add_argument("--rules", help="path to the rules.yaml to write")
    args = ap.parse_args()

    result = PolicyCompiler().compile(
        policy_path=args.policy, rules_path=args.rules, dry_run=args.dry_run
    )

    print(f"\nSource     : {result['source']}")
    print(f"Mode       : {result['mode']}  (set ANTHROPIC_API_KEY for LLM extraction)")
    print(f"Claim types: {result['n_types']}")
    print("\nChanges vs current rules.yaml:")
    for c in result["diff"]:
        print(f"   {c}")

    print("\nCompiled claim_types:")
    for ct, cfg in result["compiled"]["claim_types"].items():
        print(f"   {ct:9s} limit={cfg.get('coverage_limit')!s:>10}  "
              f"deductible={cfg.get('deductible')!s:>7}  "
              f"exclusions={cfg.get('exclusion_keywords')}")

    print("\n" + ("DRY RUN — nothing written." if args.dry_run else "rules.yaml updated (backup: rules.yaml.bak)."))


if __name__ == "__main__":
    main()

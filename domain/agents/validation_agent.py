"""
domain.agents.validation_agent
==============================
Step 3.5 · Validate against the system of record.

Two kinds of check, both graceful (never crash, never block on missing data):
  1. Duplicate detection — claims-history lookup on the per-type duplicate_key.
  2. Master-data validation — cross-checks the claim against editable master
     files (machine, parts, employee, dealer, transit) via the reusable
     ``master_data`` tool. The *files* are the input you change; this agent just
     reads them and derives validation flags the rules engine then acts on.

Derived facts (consumed by rules in rules.yaml):
  serial_known, warranty_active, part_known, consignment_known,
  employee_known, employee_active, within_reimb_limit, dealer_known
Each defaults to True when it cannot be checked (no value / no file), so a
missing master never penalises a claim — only a positive mismatch does.
"""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from config.settings import get_settings
from core.agents.base_agent import BaseAgent
from core.schemas.base import Context


class ValidationAgent(BaseAgent):
    """Step 3.5 · Duplicate detection + master-data validation."""

    name = "validation"

    def act(self, context: Context) -> str:
        settings = get_settings()
        facts = context.get("facts", {}) or {}
        ext = context.get("extracted", {}) or {}
        cfg = context.get("policy_config", {}) or {}
        ctype = context.get("claim_type")

        record_checks: List[Dict[str, Any]] = []

        # ---- 1. duplicate detection (unchanged) ----------------------------
        dup_key = cfg.get("duplicate_key")
        dup_val = facts.get(dup_key) if dup_key else None
        performed = False
        is_dup = False
        hist = Path(settings.claims_history_db)
        if dup_key and dup_val and hist.exists():
            try:
                refs = set()
                with hist.open(newline="", encoding="utf-8") as fh:
                    for row in csv.DictReader(fh):
                        ref = row.get("reference") or row.get(dup_key) or ""
                        if ref:
                            refs.add(str(ref).strip())
                performed = True
                is_dup = str(dup_val).strip() in refs
            except Exception:  # noqa: BLE001
                performed = False
        facts["is_duplicate"] = is_dup
        if performed:
            record_checks.append({"key": "duplicate", "label": "Not a duplicate",
                                  "ok": not is_dup, "detail": f"{dup_key} = {dup_val}"})

        # ---- 2. master-data validation -------------------------------------
        def lookup(path, key_column, value):
            r = self.tools.call("master_data", path=str(path), key_column=key_column, value=value)
            return r.data if r.ok else {"checked": False, "found": False, "row": None}

        def set_flag(name, result, label, detail):
            facts[name] = result["found"] if result["checked"] else True
            if result["checked"]:
                record_checks.append({"key": name, "label": label, "ok": facts[name], "detail": detail})
            return result.get("row") or {}

        # dealer / retail master — for dealer-raised claim types
        if ctype in ("warranty", "nepi", "parts_replacement", "transit_damage"):
            dealer_val = facts.get("dealer_name") or ext.get("claimant_name")
            set_flag("dealer_known", lookup(settings.dealer_master, "dealer_name", dealer_val),
                     "Dealer in master", dealer_val)

        # machine / serial master
        if ctype in ("warranty", "nepi", "parts_replacement", "transit_damage"):
            serial = facts.get("machine_serial_number")
            row = set_flag("serial_known", lookup(settings.machine_master, "serial_number", serial),
                           "Machine serial in master", serial)
            if ctype == "warranty" and row:
                active = (row.get("status") == "active") and (str(row.get("warranty_end", "")) >= date.today().isoformat())
                facts["warranty_active"] = active
                record_checks.append({"key": "warranty_active", "label": "Warranty active",
                                      "ok": active, "detail": f"ends {row.get('warranty_end')}"})

        # parts master
        if ctype == "parts_replacement":
            set_flag("part_known", lookup(settings.parts_master, "part_number", facts.get("part_number")),
                     "Part in master", facts.get("part_number"))

        # transit / consignment master
        if ctype == "transit_damage":
            set_flag("consignment_known", lookup(settings.transit_master, "consignment_note", facts.get("consignment_note")),
                     "Consignment in master", facts.get("consignment_note"))

        # employee master
        if ctype == "employee_reimbursement":
            row = set_flag("employee_known", lookup(settings.employee_master, "employee_id", facts.get("employee_id")),
                           "Employee in master", facts.get("employee_id"))
            if row:
                facts["employee_active"] = row.get("status") == "active"
                record_checks.append({"key": "employee_active", "label": "Employee active",
                                      "ok": facts["employee_active"], "detail": row.get("status")})
                try:
                    limit = float(row.get("reimbursement_limit") or 0)
                    amount = float(ext.get("claim_amount") or facts.get("claim_amount") or 0)
                    facts["within_reimb_limit"] = (amount <= limit) if limit else True
                    record_checks.append({"key": "within_reimb_limit", "label": "Within reimbursement limit",
                                          "ok": facts["within_reimb_limit"],
                                          "detail": f"\u20b9{int(amount):,} of \u20b9{int(limit):,}"})
                except (TypeError, ValueError):
                    pass

        context.set("facts", facts)
        # benefit of the doubt: any flag not positively disproven passes
        for k in ("dealer_known", "serial_known", "warranty_active", "part_known",
                  "consignment_known", "employee_known", "employee_active", "within_reimb_limit"):
            facts.setdefault(k, True)
        context.set("validation", {
            "performed": performed or bool(record_checks),
            "duplicate_key": dup_key,
            "duplicate_value": dup_val,
            "is_duplicate": is_dup,
            "record_checks": record_checks,
        })
        return f"validation: duplicate={is_dup}, master_checks={len(record_checks)}"

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

        # NEPI service reimbursement — finance validations
        if ctype == "nepi_reimbursement":
            import csv as _csv
            from datetime import date as _date
            serial = facts.get("machine_serial_number")
            row = set_flag("serial_known", lookup(settings.machine_master, "serial_number", serial),
                           "Machine serial in master", serial)
            # sale date on record (dealer -> customer)
            sale = (row or {}).get("sale_date")
            facts["sale_date_known"] = bool(sale)
            record_checks.append({"key": "sale_date_known", "label": "Machine sale date on record",
                                  "ok": bool(sale), "detail": sale or "not found"})
            # claim amount vs approved NEPI rate (service_type + region) — compare the
            # PRE-TAX base value, since the policy rate excludes GST.
            stype = (facts.get("service_type") or "").strip().lower()
            region = (facts.get("region") or "standard").strip().lower()
            rate_row = lookup(settings.nepi_rates, "rate_key", f"{stype}|{region}").get("row") or {}
            def _num(v):
                try:
                    return float(str(v).replace(",", "").replace("\u20b9", "").strip())
                except (TypeError, ValueError):
                    return None
            total = _num(ext.get("claim_amount") or facts.get("claim_amount"))
            base = _num(facts.get("base_amount"))
            tax = _num(facts.get("tax_amount"))
            # candidate pre-tax values to test against the rate
            candidates = []
            if base is not None:
                candidates.append(base)
            if total is not None:
                if tax is not None:
                    candidates.append(total - tax)       # explicit GST line
                candidates.append(round(total / 1.18, 2))  # strip standard 18% GST
                candidates.append(total)                  # in case total is already pre-tax
            try:
                rate = float(rate_row.get("approved_rate")) if rate_row else None
                if rate is None or not candidates:
                    facts["amount_matches_rate"] = True; detail = "rate or amount not found"
                else:
                    facts["amount_matches_rate"] = any(abs(c - rate) <= 1 for c in candidates)
                    shown = base if base is not None else (round(total / 1.18) if total else None)
                    detail = f"base \u20b9{int(shown):,} vs approved \u20b9{int(rate):,}" if shown is not None else "could not compare"
                    if total and shown is not None and abs(total - shown) > 1:
                        detail += f" (invoice \u20b9{int(total):,} incl. GST)"
            except (TypeError, ValueError):
                facts["amount_matches_rate"] = True; detail = "could not compare"
            record_checks.append({"key": "amount_matches_rate", "label": "Amount matches approved rate",
                                  "ok": facts["amount_matches_rate"], "detail": detail})
            # HMR eligibility window for the service claimed
            try:
                hmr = float(facts.get("hmr_hours") or 0)
            except (TypeError, ValueError):
                hmr = 0.0
            windows = {"nepi_500": (400, 700), "nepi_1500": (1300, 1700), "commissioning_installation": (0, 150)}
            lo, hi = windows.get(stype, (0, 10**9))
            facts["hmr_eligible"] = (lo <= hmr <= hi) if hmr else True
            record_checks.append({"key": "hmr_eligible", "label": "Hours eligible for service",
                                  "ok": facts["hmr_eligible"], "detail": f"{int(hmr)} hrs (window {lo}-{hi})"})
            # NEPI period eligibility — service performed within the allowed window
            # from the machine sale date (the time side of "1500 hrs OR 1 year").
            def _parse_date(s):
                from datetime import datetime
                if not s:
                    return None
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d"):
                    try:
                        return datetime.strptime(str(s).strip(), fmt).date()
                    except ValueError:
                        continue
                return None
            sale_d = _parse_date(sale)
            svc_d = _parse_date(facts.get("service_date"))
            period_months = {"commissioning_installation": 3, "nepi_500": 9, "nepi_1500": 15}
            limit_m = period_months.get(stype)
            if sale_d and svc_d and limit_m:
                months = (svc_d.year - sale_d.year) * 12 + (svc_d.month - sale_d.month)
                facts["period_eligible"] = (0 <= months <= limit_m)
                pdetail = f"{months} mo after sale (limit {limit_m} mo)"
            else:
                facts["period_eligible"] = True
                pdetail = "service/sale date not available — not checked"
            record_checks.append({"key": "period_eligible", "label": "Within eligible service period",
                                  "ok": facts["period_eligible"], "detail": pdetail})
            # NEPI-1/NEPI-2 not already claimed for this serial (duplicate reimbursement)
            already = False
            if serial and stype and hist.exists():
                try:
                    key = f"{serial}|{stype}".lower()
                    with hist.open(newline="", encoding="utf-8") as fh:
                        for r in _csv.DictReader(fh):
                            ref = (r.get("reference") or "").strip().lower()
                            if ref == key:
                                already = True; break
                except Exception:  # noqa: BLE001
                    already = False
            facts["nepi_not_claimed"] = not already
            record_checks.append({"key": "nepi_not_claimed", "label": "NEPI not already claimed",
                                  "ok": not already, "detail": f"{serial} / {stype}"})
            # invoice/claim duplicate accounting — FSR / claim (or IC ticket) number
            # not already accounted (invoice number is handled by is_duplicate above).
            fsr_no = str(facts.get("fsr_number") or "").strip().lower()
            ic_no = str(facts.get("ic_ticket_number") or "").strip().lower()
            fsr_dup = False
            if (fsr_no or ic_no) and hist.exists():
                try:
                    refs = set()
                    with hist.open(newline="", encoding="utf-8") as fh:
                        for r in _csv.DictReader(fh):
                            refs.add((r.get("reference") or "").strip().lower())
                    fsr_dup = (bool(fsr_no) and fsr_no in refs) or (bool(ic_no) and ic_no in refs)
                except Exception:  # noqa: BLE001
                    fsr_dup = False
            facts["fsr_not_duplicate"] = not fsr_dup
            record_checks.append({"key": "fsr_not_duplicate", "label": "FSR / claim not already accounted",
                                  "ok": not fsr_dup, "detail": fsr_no or ic_no or "n/a"})
            # approval before invoicing. In the real DMS flow the invoice is only
            # generated AFTER the claim is approved, so a present invoice implies
            # approval. Only an explicit pending/rejected status fails the check.
            status = str(facts.get("approval_status") or "").strip().lower()
            has_invoice = bool(facts.get("invoice_number"))
            if status in ("pending", "rejected", "not approved", "unapproved", "on hold"):
                facts["approval_ok"] = False; adetail = f"status: {status}"
            elif status == "approved":
                facts["approval_ok"] = True; adetail = "approved"
            else:
                facts["approval_ok"] = has_invoice
                adetail = "implied by issued invoice" if has_invoice else "no approval and no invoice"
            record_checks.append({"key": "approval_ok", "label": "Approved before invoice",
                                  "ok": facts["approval_ok"], "detail": adetail})

        # ---- cross-document reconciliation (multi-document claims) ---------
        doc_texts = context.get("doc_texts") or []
        if len(doc_texts) >= 2:
            KEY = {"machine_serial_number": "machine serial number",
                   "failed_part": "failed or replaced part name",
                   "claim_amount": "the main claim or invoice amount as a number"}
            per = []
            for d in doc_texts:
                try:
                    r = self.tools.call("extractor", text=(d.get("text") or "")[:4000], schema=KEY)
                    f = r.data["fields"] if r.ok else {}
                except Exception:  # noqa: BLE001
                    f = {}
                per.append({"role": d.get("role"), "fields": f})

            def _norm(v):
                return str(v).strip().lower() if v not in (None, "", "null") else None

            def _collect(field):
                return [(p["role"], _norm(p["fields"].get(field))) for p in per if _norm(p["fields"].get(field))]

            serials = _collect("machine_serial_number")
            s_ok = len({v for _, v in serials}) <= 1
            facts["docs_serial_match"] = s_ok
            record_checks.append({"key": "docs_serial_match", "label": "Serial consistent across documents",
                                  "ok": s_ok, "detail": "; ".join(f"{r}={v}" for r, v in serials) or "n/a"})

            parts = _collect("failed_part")
            p_ok = len({v for _, v in parts}) <= 1 if parts else True
            facts["docs_part_match"] = p_ok
            record_checks.append({"key": "docs_part_match", "label": "Failed part consistent across documents",
                                  "ok": p_ok, "detail": "; ".join(f"{r}={v}" for r, v in parts) or "n/a"})

            amts = []
            for _r, v in _collect("claim_amount"):
                try:
                    amts.append(float(v.replace(",", "").replace("\u20b9", "")))
                except ValueError:
                    pass
            a_ok, adetail = True, "n/a"
            if len(amts) >= 2:
                lo, hi = min(amts), max(amts)
                a_ok = (abs(hi - lo) <= 1) or (abs(hi - lo * 1.18) <= 2) or (abs(hi / 1.18 - lo) <= 2)
                adetail = ", ".join(str(int(a)) for a in amts) + (" (reconcile incl. GST)" if a_ok and abs(hi - lo) > 1 else "")
            facts["docs_amount_match"] = a_ok
            record_checks.append({"key": "docs_amount_match", "label": "Amounts reconcile across documents",
                                  "ok": a_ok, "detail": adetail})
            context.set("cross_document", per)

        context.set("facts", facts)
        # benefit of the doubt: any flag not positively disproven passes
        for k in ("dealer_known", "serial_known", "warranty_active", "part_known",
                  "consignment_known", "employee_known", "employee_active", "within_reimb_limit",
                  "amount_matches_rate", "hmr_eligible", "nepi_not_claimed",
                  "period_eligible", "fsr_not_duplicate",
                  "docs_serial_match", "docs_part_match", "docs_amount_match"):
            facts.setdefault(k, True)
        context.set("validation", {
            "performed": performed or bool(record_checks),
            "duplicate_key": dup_key,
            "duplicate_value": dup_val,
            "is_duplicate": is_dup,
            "record_checks": record_checks,
        })
        return f"validation: duplicate={is_dup}, master_checks={len(record_checks)}"

"""
db.repository
============
The only place that knows how to read/write the tables. Keeps SQL/ORM details
out of the services and API (clean separation, easy to test).
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import Claim, ClaimHistoryRow, Policy


# --- claims ---------------------------------------------------------------
def save_claim_report(
    session: Session,
    report: Dict[str, Any],
    source_filename: Optional[str] = None,
    raw_text: Optional[str] = None,
) -> Claim:
    """Persist a ClaimDecisionReport (as a dict) into the claims table."""
    extracted = report.get("extracted", {}) or {}
    adjudication = report.get("adjudication", {}) or {}
    claim = Claim(
        run_id=report.get("run_id"),
        source_filename=source_filename,
        claim_type=report.get("claim_type"),
        claimant_name=extracted.get("claimant_name"),
        policy_number=extracted.get("policy_number"),
        claim_amount=extracted.get("claim_amount"),
        decision=adjudication.get("decision"),
        approved_amount=adjudication.get("approved_amount", 0.0) or 0.0,
        confidence=adjudication.get("confidence", 0.0) or 0.0,
        completeness=report.get("completeness", 0.0) or 0.0,
        reasons=adjudication.get("reasons", []),
        extracted=extracted,
        validation=report.get("validation", {}) or {},
        adjudication=adjudication,
        summary=report.get("summary"),
        notification=report.get("notification"),
        visual_validation=report.get("visual_validation"),
        raw_text=raw_text,
    )
    session.add(claim)
    session.flush()  # assigns claim.id without ending the transaction
    return claim


def list_claims(session: Session, limit: int = 50, offset: int = 0) -> List[Claim]:
    stmt = select(Claim).order_by(Claim.created_at.desc()).limit(limit).offset(offset)
    return list(session.scalars(stmt))


def get_claim(session: Session, claim_id: int) -> Optional[Claim]:
    return session.get(Claim, claim_id)


def count_claims(session: Session) -> int:
    return len(list(session.scalars(select(Claim.id))))


def stats(session: Session) -> Dict[str, Any]:
    """Aggregate dashboard metrics computed in the database layer."""
    from collections import Counter
    from datetime import date, datetime, timedelta

    claims = list(session.scalars(select(Claim)))
    by_decision: Counter = Counter()
    by_type: Counter = Counter()
    reason_counts: Counter = Counter()
    total_payout = 0.0
    total_claimed = 0.0
    per_day_map: Counter = Counter()
    today = datetime.utcnow().date()
    today_count = 0

    for c in claims:
        by_decision[c.decision or "UNKNOWN"] += 1
        if c.claim_type:
            by_type[c.claim_type] += 1
        total_payout += c.approved_amount or 0.0
        total_claimed += c.claim_amount or 0.0
        for r in (c.reasons or []):
            reason_counts[r] += 1
        d = (c.created_at or datetime.utcnow()).date()
        per_day_map[d] += 1
        if d == today:
            today_count += 1

    # last 14 days, zero-filled
    per_day = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        per_day.append({"date": d.strftime("%d %b"), "count": per_day_map.get(d, 0)})

    return {
        "total": len(claims),
        "by_decision": dict(by_decision),
        "by_type": dict(by_type),
        "total_payout": round(total_payout, 2),
        "total_claimed": round(total_claimed, 2),
        "today_count": today_count,
        "per_day": per_day,
        "top_reasons": [{"reason": r, "count": n} for r, n in reason_counts.most_common(6)],
    }


# --- structured data seeding ---------------------------------------------
def seed_policies(session: Session, csv_path: str) -> int:
    rows = _read_csv(csv_path)
    existing = {p.policy_number for p in session.scalars(select(Policy))}
    added = 0
    for r in rows:
        if r.get("policy_number") in existing:
            continue
        session.add(
            Policy(
                policy_number=r.get("policy_number"),
                policyholder_name=r.get("policyholder_name") or None,
                nominee_name=r.get("nominee_name") or None,
                product_type=r.get("product_type") or None,
                status=r.get("status") or None,
                start_date=r.get("start_date") or None,
                end_date=r.get("end_date") or None,
                sum_insured=_to_float(r.get("sum_insured")),
                premium_status=r.get("premium_status") or None,
            )
        )
        added += 1
    return added


def seed_history(session: Session, csv_path: str) -> int:
    rows = _read_csv(csv_path)
    added = 0
    for r in rows:
        session.add(
            ClaimHistoryRow(
                claim_ref=r.get("claim_id") or None,
                policy_number=r.get("policy_number"),
                incident_date=r.get("incident_date") or None,
                paid_amount=_to_float(r.get("paid_amount")),
                status=r.get("status") or None,
            )
        )
        added += 1
    return added


# --- admin: replace + list -----------------------------------------------
def replace_policies(session: Session, csv_path: str) -> int:
    session.execute(delete(Policy))
    return seed_policies(session, csv_path)


def replace_history(session: Session, csv_path: str) -> int:
    session.execute(delete(ClaimHistoryRow))
    return seed_history(session, csv_path)


def list_policies(session: Session) -> List[Dict[str, Any]]:
    out = []
    for p in session.scalars(select(Policy).order_by(Policy.policy_number)):
        out.append({
            "policy_number": p.policy_number,
            "policyholder_name": p.policyholder_name,
            "nominee_name": p.nominee_name,
            "product_type": p.product_type,
            "status": p.status,
            "start_date": p.start_date,
            "end_date": p.end_date,
            "sum_insured": p.sum_insured,
            "premium_status": p.premium_status,
        })
    return out


def list_history(session: Session) -> List[Dict[str, Any]]:
    out = []
    for h in session.scalars(select(ClaimHistoryRow).order_by(ClaimHistoryRow.policy_number)):
        out.append({
            "claim_ref": h.claim_ref,
            "policy_number": h.policy_number,
            "incident_date": h.incident_date,
            "paid_amount": h.paid_amount,
            "status": h.status,
        })
    return out


# --- helpers --------------------------------------------------------------
def _read_csv(path: str) -> List[Dict[str, str]]:
    p = Path(path)
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None

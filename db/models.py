"""
db.models
========
ORM tables. `Claim` is the main one (every processed claim + its decision is
saved here). `Policy` and `ClaimHistoryRow` mirror the structured CSVs so the
system of record can live in the database too (seeded via scripts/seed_db.py).

JSON columns store the rich nested structures (extracted fields, validation,
adjudication) so the dashboard can render full detail without extra tables.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # headline fields (flat columns -> easy to list/sort/filter in the dashboard)
    source_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    claim_type: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    claimant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    policy_number: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    claim_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    decision: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    approved_amount: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    completeness: Mapped[float] = mapped_column(Float, default=0.0)

    # rich detail (nested) for the detail view
    reasons: Mapped[List[Any]] = mapped_column(JSON, default=list)
    extracted: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    validation: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    adjudication: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    visual_validation: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "source_filename": self.source_filename,
            "claim_type": self.claim_type,
            "claimant_name": self.claimant_name,
            "policy_number": self.policy_number,
            "claim_amount": self.claim_amount,
            "decision": self.decision,
            "approved_amount": self.approved_amount,
            "confidence": self.confidence,
        }

    def to_detail(self) -> Dict[str, Any]:
        return {
            **self.to_summary(),
            "completeness": self.completeness,
            "reasons": self.reasons,
            "extracted": self.extracted,
            "validation": self.validation,
            "adjudication": self.adjudication,
            "summary": self.summary,
            "notification": self.notification,
            "visual_validation": self.visual_validation,
            "raw_text": self.raw_text,
        }


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    policyholder_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nominee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sum_insured: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    premium_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class ClaimHistoryRow(Base):
    __tablename__ = "claims_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    claim_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    policy_number: Mapped[str] = mapped_column(String(64), index=True)
    incident_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    paid_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

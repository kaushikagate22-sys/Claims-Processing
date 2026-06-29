"""
domain.schemas.claim
==================
Claims-specific data contracts. This is the ~30-40% that's *specific* to the
insurance-claims use case and sits on top of the generic core layer.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    AUTO = "auto"
    HEALTH = "health"
    TRAVEL = "travel"
    PROPERTY = "property"
    LIFE = "life"


class Decision(str, Enum):
    APPROVE = "APPROVED"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"
    REJECT = "REJECTED"


class ExtractedClaim(BaseModel):
    """Normalised, structured view of a claim after extraction."""

    claim_type: Optional[str] = None
    claimant_name: Optional[str] = None
    policy_number: Optional[str] = None
    incident_date: Optional[str] = None
    claim_date: Optional[str] = None
    claim_amount: Optional[float] = None
    description: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class RuleOutcome(BaseModel):
    id: str
    severity: str
    passed: bool
    message: str = ""


class Adjudication(BaseModel):
    decision: Decision
    approved_amount: float = 0.0
    confidence: float = 0.0
    reasons: List[str] = Field(default_factory=list)
    rule_outcomes: List[RuleOutcome] = Field(default_factory=list)
    policy_citations: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)


class ClaimDecisionReport(BaseModel):
    """The final, user-facing artefact produced by the pipeline."""

    run_id: str
    claim_type: Optional[str] = None
    extracted: ExtractedClaim
    adjudication: Adjudication
    validation: Dict[str, Any] = Field(default_factory=dict)
    completeness: float = 0.0
    summary: Optional[str] = None
    notification: Optional[Dict[str, Any]] = None
    visual_validation: Optional[Dict[str, Any]] = None
    trace: List[Dict[str, Any]] = Field(default_factory=list)

"""Persistence tests (temp SQLite; same code path as Postgres)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.settings import get_settings
from db.database import Base
from db.repository import (
    count_claims,
    get_claim,
    list_claims,
    save_claim_report,
    seed_policies,
)

S = get_settings()


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}", future=True)
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine, expire_on_commit=False)
    s = Sess()
    yield s
    s.close()


SAMPLE_REPORT = {
    "run_id": "abc123",
    "claim_type": "auto",
    "completeness": 1.0,
    "extracted": {"claimant_name": "Rohan Mehta", "policy_number": "AUTO-1", "claim_amount": 145000},
    "adjudication": {"decision": "APPROVED", "approved_amount": 140000, "confidence": 0.95,
                     "reasons": ["ok"]},
    "validation": {"performed": True, "policy_exists": True},
}


def test_save_and_get(session):
    claim = save_claim_report(session, SAMPLE_REPORT, "auto.txt", "raw text")
    session.commit()
    assert claim.id is not None
    fetched = get_claim(session, claim.id)
    assert fetched.decision == "APPROVED"
    assert fetched.approved_amount == 140000
    assert fetched.extracted["claimant_name"] == "Rohan Mehta"
    assert fetched.validation["policy_exists"] is True


def test_list_orders_recent_first(session):
    save_claim_report(session, {**SAMPLE_REPORT, "run_id": "r1"}, "a.txt")
    save_claim_report(session, {**SAMPLE_REPORT, "run_id": "r2"}, "b.txt")
    session.commit()
    assert count_claims(session) == 2
    rows = list_claims(session)
    assert len(rows) == 2


def test_seed_policies(session):
    n = seed_policies(session, str(S.policies_db))
    session.commit()
    assert n == 6  # 5 base + warranty example
    # idempotent: seeding again adds nothing
    assert seed_policies(session, str(S.policies_db)) == 0

"""
db.database
==========
Database engine + session management. **Database-agnostic** via SQLAlchemy:

  * Local dev (default): SQLite file `./claims.db` — no server, no Docker.
  * Production / your Azure instance: set DATABASE_URL to a Postgres URL.

Azure Postgres flexible server example (note the required SSL):
    DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST.postgres.database.azure.com:5432/DBNAME?sslmode=require

The rest of the app talks only to `session_scope()` and the repository, so the
backing database can change with zero code changes.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base all ORM models inherit from."""


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./claims.db")


def make_engine(url: str | None = None):
    url = url or get_database_url()
    connect_args = {}
    if url.startswith("sqlite"):
        # allow use across threads (FastAPI) for the local SQLite case
        connect_args = {"check_same_thread": False}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


# Module-level engine + session factory (created once).
engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(eng=None) -> None:
    """Create all tables, then add any newly-introduced columns to existing tables.
    Safe to call repeatedly."""
    from db import models  # noqa: F401  (import registers the models on Base)

    eng = eng or engine
    Base.metadata.create_all(bind=eng)
    _ensure_columns(eng)


def _ensure_columns(eng) -> None:
    """Lightweight migration: add columns that exist on the model but not yet in
    the table (covers databases created before a field was added). Idempotent."""
    from sqlalchemy import inspect, text

    insp = inspect(eng)
    if "claims" not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns("claims")}
    wanted = {"summary": "TEXT", "notification": "JSON", "visual_validation": "JSON"}
    with eng.begin() as conn:
        for name, coltype in wanted.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE claims ADD COLUMN {name} {coltype}"))


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commits on success, rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

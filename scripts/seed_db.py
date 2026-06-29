"""
scripts/seed_db.py
===============
Create all tables and load the policy master + claims history into the database.

    python scripts/seed_db.py

Uses DATABASE_URL if set (your Azure Postgres), else a local SQLite file.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings  # noqa: E402
from db.database import get_database_url, init_db, session_scope  # noqa: E402
from db.repository import seed_history, seed_policies  # noqa: E402


def main() -> None:
    settings = get_settings()
    print(f"Database: {get_database_url()}")
    init_db()
    print("Tables created.")
    with session_scope() as session:
        n_pol = seed_policies(session, str(settings.policies_db))
        n_hist = seed_history(session, str(settings.claims_history_db))
    print(f"Seeded {n_pol} policies and {n_hist} history rows.")


if __name__ == "__main__":
    main()

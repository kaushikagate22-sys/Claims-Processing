"""
config.settings
=============
Central configuration. Reads from environment with sensible defaults so the
project runs immediately after clone.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parent.parent

# Load environment variables from a .env file in the project root, if present.
# This is what makes OPENAI_API_KEY (etc.) available to the whole app.
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=ROOT / ".env", override=False)
except ImportError:
    pass  # dotenv is optional; env vars set in the shell still work

DATA_DIR = ROOT / "data"
POLICY_DIR = DATA_DIR / "policies"
STRUCTURED_DIR = DATA_DIR / "structured"
MASTERS_DIR = Path(os.getenv("MASTERS_DIR", DATA_DIR / "masters"))
SAMPLES_DIR = DATA_DIR / "sample_claims"
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", ROOT / "uploads"))
RULES_PATH = ROOT / "config" / "rules.yaml"


class Settings:
    def __init__(self) -> None:
        self.root = ROOT
        self.policy_dir = POLICY_DIR
        self.structured_dir = STRUCTURED_DIR
        self.samples_dir = SAMPLES_DIR
        self.uploads_dir = UPLOADS_DIR
        self.rules_path = RULES_PATH
        self.master_policy = POLICY_DIR / "master_policy.md"
        self.policies_db = STRUCTURED_DIR / "policies.csv"
        self.claims_history_db = STRUCTURED_DIR / "claims_history.csv"
        # editable system-of-record master files (change these to bring your own data)
        self.masters_dir = MASTERS_DIR
        self.employee_master = MASTERS_DIR / "employee_master.csv"
        self.dealer_master = MASTERS_DIR / "dealer_master.csv"
        self.machine_master = MASTERS_DIR / "machine_master.csv"
        self.parts_master = MASTERS_DIR / "parts_master.csv"
        self.transit_master = MASTERS_DIR / "transit_master.csv"
        self.nepi_rates = MASTERS_DIR / "nepi_rates.csv"
        self.llm_model = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
        self.top_k = int(os.getenv("RETRIEVER_TOP_K", "4"))
        self.uploads_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def load_rules() -> Dict[str, Any]:
    """Load the declarative policy rules (per claim type)."""
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

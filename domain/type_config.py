"""
domain.type_config
===================
Central lookups for everything that varies *by claim type*. Agents call these
instead of hardcoding per-type behaviour, so the pipeline is driven by config:

  * supported_types()        -> the claim types the system knows about (from rules.yaml)
  * get_type_config(ctype)   -> that type's rule block (limits, deductible, exclusions…)
  * extraction_schema_for()  -> base fields + that type's extra fields (the per-type schema)

Add a claim type by adding it to rules.yaml (limits/rules) and, if it needs
extra extracted fields, to TYPE_EXTRACTION_FIELDS in domain.prompts.templates.
No agent code changes.
"""
from __future__ import annotations

from typing import Any, Dict, List

from config.settings import load_rules
from domain.prompts.templates import BASE_EXTRACTION_SCHEMA, TYPE_EXTRACTION_FIELDS


def supported_types() -> List[str]:
    return list(load_rules().get("claim_types", {}).keys())


def get_type_config(ctype: str | None) -> Dict[str, Any]:
    if not ctype:
        return {}
    return load_rules().get("claim_types", {}).get(ctype, {})


def extraction_schema_for(ctype: str | None) -> Dict[str, str]:
    """Merged extraction schema: shared base fields + this type's extra fields."""
    schema: Dict[str, str] = dict(BASE_EXTRACTION_SCHEMA)
    schema.update(TYPE_EXTRACTION_FIELDS.get(ctype or "", {}))   # code defaults
    schema.update(get_type_config(ctype).get("extraction_schema") or {})  # config overrides
    return schema

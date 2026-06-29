"""
domain.agents.extraction_agent
===========================
Step 2. Turns the raw claim text into a structured `ExtractedClaim` using the
reusable `extractor` tool. Normalises claim_type and numeric amount.

Reads  context: payload["claim_text"], payload["claim_type_guess"]
Writes context: payload["extracted"] (dict), payload["completeness"],
                payload["claim_type"]
"""
from __future__ import annotations

import re
from typing import Optional

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context
from domain.prompts.templates import EXTRACTION_INSTRUCTIONS
from domain.schemas.claim import ExtractedClaim
from domain.type_config import extraction_schema_for, supported_types


class ExtractionAgent(BaseAgent):
    """Step 2 · Extract structured fields from the claim text.

    Uses the reusable ``extractor`` tool (LLM, with an offline regex fallback) to
    build a typed ``ExtractedClaim``, normalising the claim type and numeric
    amount and scoring completeness.

    Reads  ``payload['claim_text']``, ``payload['claim_type_guess']``.
    Writes ``payload['extracted']``, ``payload['completeness']``, ``payload['claim_type']``.
    """

    name = "extraction"

    def act(self, context: Context) -> str:
        text = context.get("claim_text")
        if not text:
            raise ValueError("extraction requires payload['claim_text']")

        # Pick the schema for the detected type, so extraction adapts per type.
        guess = context.get("claim_type_guess")
        schema = extraction_schema_for(guess)

        res = self.tools.call(
            "extractor",
            text=text,
            schema=schema,
            instructions=EXTRACTION_INSTRUCTIONS,
        )
        if not res.ok:
            raise RuntimeError(f"extraction failed: {res.error}")

        fields = res.data["fields"]
        fields["claim_amount"] = self._to_number(fields.get("claim_amount"))
        ctype = self._normalise_type(fields.get("claim_type")) or guess
        if ctype in supported_types():
            fields["claim_type"] = ctype
        else:
            ctype = None

        base = {k: v for k, v in fields.items()
                if k in ExtractedClaim.model_fields and k != "extra"}
        extra = {k: v for k, v in fields.items()
                 if k not in ExtractedClaim.model_fields}

        # Robustness: if the confirmed type differs from the guess we used to
        # pick the schema, re-extract with the correct type's schema so its
        # type-specific fields are captured (matters when classification was off).
        if ctype and ctype != guess:
            schema2 = extraction_schema_for(ctype)
            if set(schema2) - set(schema):
                res2 = self.tools.call("extractor", text=text, schema=schema2,
                                       instructions=EXTRACTION_INSTRUCTIONS)
                if res2.ok:
                    f2 = res2.data["fields"]
                    f2["claim_amount"] = self._to_number(f2.get("claim_amount"))
                    base = {k: v for k, v in f2.items()
                            if k in ExtractedClaim.model_fields and k != "extra"}
                    extra = {k: v for k, v in f2.items()
                             if k not in ExtractedClaim.model_fields}
                    fields = f2
                    res = res2

        extracted = ExtractedClaim(**base)
        extracted.extra.update(extra)

        context.set("extracted", extracted.model_dump())
        context.set("claim_type", ctype)
        context.set("completeness", res.data["completeness"])

        return (
            f"type={ctype} amount={fields.get('claim_amount')} "
            f"fields={len(schema)} completeness={res.data['completeness']} "
            f"missing={res.data['missing']}"
        )

    @staticmethod
    def _to_number(value) -> Optional[float]:
        if value is None:
            return None
        m = re.search(r"-?\d[\d,]*\.?\d*", str(value))
        if not m:
            return None
        try:
            return float(m.group(0).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _normalise_type(value) -> Optional[str]:
        if not value:
            return None
        v = str(value).strip().lower()
        for t in supported_types():
            if t in v:
                return t
        return None

"""
core.tools.extractor
===================
Turn unstructured text into a structured dict given a target schema.

Uses the LLMClient when available; the LLMClient's offline fallback does
heuristic "Field: value" extraction so this still works without an API key.
Reusable for any extraction task — just pass a different schema.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.tools.base_tool import BaseTool
from core.tools.llm_client import LLMClient


class StructuredExtractorTool(BaseTool):
    name = "extractor"
    description = "Extract structured fields from text according to a schema."
    params = {
        "text": "source text to extract from",
        "schema": "dict of {field_name: description} to extract",
        "instructions": "optional extra guidance for the extractor",
    }

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        super().__init__()
        self.llm = llm or LLMClient()

    def _run(
        self,
        text: str,
        schema: Dict[str, str],
        instructions: str = "",
        **_: Any,
    ) -> Dict[str, Any]:
        prompt = (
            f"{instructions}\n\nDocument:\n'''\n{text}\n'''\n\n"
            "Extract the requested fields. Use null when a value is absent."
        )
        data = self.llm.extract_json(prompt, schema)
        filled = sum(1 for v in data.values() if v not in (None, "", "null"))
        return {
            "fields": data,
            "completeness": round(filled / max(len(schema), 1), 2),
            "missing": [k for k, v in data.items() if v in (None, "", "null")],
        }

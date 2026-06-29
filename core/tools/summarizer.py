"""
core.tools.summarizer
=====================
A reusable, domain-agnostic summarisation tool. Give it a headline and a flat
dict of label -> value facts; it returns concise human-readable prose. It uses
the LLM when one is configured and falls back to a deterministic template
offline, so it never crashes a run and needs no network to work.

Reusable across use cases: claims, invoices, KYC — anything that needs a short
natural-language summary of a structured outcome.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.tools.base_tool import BaseTool
from core.tools.llm_client import LLMClient


class SummarizerTool(BaseTool):
    name = "summarizer"
    description = "Summarise a structured outcome into concise human-readable prose."
    params = {
        "headline": "one-line headline for the summary",
        "facts": "dict of label -> value to summarise",
        "instructions": "optional style/voice guidance",
        "max_words": "approximate word budget (default 70)",
    }

    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        super().__init__()
        self.llm = llm or LLMClient()

    def _run(
        self,
        headline: str = "",
        facts: Optional[Dict[str, Any]] = None,
        instructions: str = "",
        max_words: int = 70,
        **_: Any,
    ) -> Dict[str, str]:
        facts = facts or {}
        clean = {k: v for k, v in facts.items() if v not in (None, "", [], {})}

        # Prefer the LLM when available for a fluent summary.
        if getattr(self.llm, "mode", "offline") != "offline":
            lines = "\n".join(f"- {k}: {v}" for k, v in clean.items())
            prompt = (
                f"{instructions}\n\n"
                f"Write a concise summary of at most {max_words} words.\n"
                f"Headline: {headline}\nFacts:\n{lines}\n\nSummary:"
            )
            try:
                text = (self.llm.complete(prompt) or "").strip()
                if text:
                    return {"summary": text}
            except Exception:  # noqa: BLE001 - fall back to template
                pass

        # Deterministic offline template.
        bits = "; ".join(f"{k}: {v}" for k, v in clean.items())
        summary = headline.strip()
        if bits:
            summary = f"{summary}. {bits}" if summary else bits
        if summary and not summary.endswith("."):
            summary += "."
        return {"summary": summary}

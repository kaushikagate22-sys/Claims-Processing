"""
domain.agents.intake_agent
========================
Step 1 of the claims pipeline.
Reads the uploaded file into text (via the reusable `document_loader` tool) and
makes a first-pass guess at the claim type using keyword hints. The definitive
type may be refined later by the ExtractionAgent.

Reads  context: payload["source_path"]  (path to uploaded claim)
Writes context: payload["claim_text"], payload["claim_type_guess"]
"""
from __future__ import annotations

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context
from domain.prompts.templates import CLAIM_TYPE_KEYWORDS


class IntakeAgent(BaseAgent):
    """Step 1 · Ingest the raw claim and make a first-pass type guess.

    Loads the uploaded document to plain text via the reusable ``document_loader``
    tool (or accepts directly-injected text), then guesses the claim type from
    keyword hints. The guess may be refined later by the ExtractionAgent.

    Reads  ``payload['source_path']`` or ``payload['claim_text']``.
    Writes ``payload['claim_text']``, ``payload['claim_type_guess']``.
    """

    name = "intake"

    def act(self, context: Context) -> str:
        path = context.get("source_path")
        text = context.get("claim_text")  # allow direct text injection (e.g. API paste)

        if not text:
            if not path:
                raise ValueError("intake requires payload['source_path'] or ['claim_text']")
            res = self.tools.call("document_loader", path=path)
            if not res.ok:
                raise RuntimeError(f"could not load document: {res.error}")
            text = res.data["text"]
            context.set("source_meta", {k: v for k, v in res.data.items() if k != "text"})

        context.set("claim_text", text)
        forced = context.get("forced_type")
        guess = forced if forced else self._classify(text)
        context.set("claim_type_guess", guess)
        return f"loaded {len(text)} chars; type guess = {guess}"

    def _classify(self, text: str) -> str:
        """LLM-first classification; keyword scoring as the offline fallback."""
        if getattr(self.llm, "mode", "offline") != "offline":
            try:
                t = self._classify_llm(text)
                if t:
                    return t
            except Exception:  # noqa: BLE001 - never let classification crash intake
                self.log.warning("LLM classify failed; using keyword fallback")
        return self._classify_keywords(text)

    def _classify_llm(self, text: str) -> str | None:
        from domain.prompts.templates import CLASSIFY_INSTRUCTIONS
        from domain.type_config import supported_types

        types = supported_types() or list(CLAIM_TYPE_KEYWORDS.keys())
        allowed = ", ".join(types)
        prompt = (
            f"{CLASSIFY_INSTRUCTIONS}\nAllowed types: {allowed}.\n\n"
            f"Claim:\n{text[:2000]}"
        )
        data = self.llm.extract_json(prompt, {"claim_type": f"one of: {allowed}, unknown"})
        t = str(data.get("claim_type", "")).strip().lower()
        return t if t in types else None

    @staticmethod
    def _classify_keywords(text: str) -> str:
        low = text.lower()
        scores = {
            ctype: sum(low.count(kw) for kw in kws)
            for ctype, kws in CLAIM_TYPE_KEYWORDS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "unknown"

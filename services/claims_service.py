"""
services.claims_service
====================
The glue between the (pure, DB-unaware) claims pipeline and persistence.

Keeping this separate means:
  * `domain/` stays free of any database concern (still fully reusable),
  * `db/` stays free of any pipeline concern,
  * the API just calls this service.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from core.schemas.base import Context
from db.database import session_scope
from db.repository import get_claim, list_claims, save_claim_report
from domain.agents.claims_orchestrator import ClaimsPipeline


# friendly, ordered descriptions for the live pipeline view
AGENT_INFO = {
    "intake": "Reads the document and identifies the claim type",
    "extraction": "Pulls out the structured claim fields",
    "policy": "Retrieves the matching policy section and limits",
    "validation": "Cross-checks against the system of record",
    "visual": "Compares submitted photos to the claim",
    "adjudication": "Applies the rules and decides",
    "summarizer": "Writes the audit summary of the decision",
    "notification": "Notifies the right stakeholder",
}


def _agent_tone(agent: str, ctx: Context, status_ok: bool) -> str:
    """Map an agent's outcome to a control-room colour: green / amber / red."""
    if not status_ok:
        return "red"
    p = ctx.payload
    if agent == "intake":
        return "green" if p.get("claim_type_guess") not in (None, "unknown") else "amber"
    if agent == "extraction":
        c = p.get("completeness") or 0
        return "green" if c >= 0.8 else ("amber" if c >= 0.4 else "red")
    if agent == "policy":
        return "green" if p.get("policy_config") else "amber"
    if agent == "validation":
        v = p.get("validation") or {}
        if not v.get("performed"):
            return "amber"
        if v.get("policy_exists") is False:
            return "red"
        if v.get("not_duplicate") is False or v.get("within_policy_period") is False:
            return "red"
        if v.get("name_match") is False or v.get("product_matches") is False:
            return "amber"
        return "green"
    if agent == "visual":
        v = p.get("visual_validation") or {}
        if not v.get("photos_provided") or not v.get("assessed"):
            return "green"
        return "green" if v.get("consistent") else "amber"
    if agent == "summarizer":
        return "green" if p.get("summary") else "amber"
    if agent == "notification":
        return "green" if (p.get("notification") or {}).get("status") in ("queued", "sent") else "amber"
    if agent == "adjudication":
        d = (p.get("adjudication") or {}).get("decision")
        key = getattr(d, "value", str(d))
        return {
            "APPROVED": "green",
            "HOLD": "amber",
            "ESCALATE": "amber",
            "REJECTED": "red",
        }.get(key, "amber")
    return "green"


class ClaimsService:
    def __init__(self) -> None:
        self.pipeline = ClaimsPipeline()

    def process_and_save(
        self,
        source_path: Optional[str] = None,
        claim_text: Optional[str] = None,
        source_filename: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        report = self.pipeline.process(source_path=source_path, claim_text=claim_text, image_paths=image_paths)
        report_dict = report.model_dump(mode="json")
        filename, raw_text = self._meta(source_path, claim_text, source_filename)
        with session_scope() as session:
            claim = save_claim_report(session, report_dict, filename, raw_text)
            return claim.to_detail()

    # --- live streaming ---------------------------------------------------
    def stream_process(
        self,
        source_path: Optional[str] = None,
        claim_text: Optional[str] = None,
        source_filename: Optional[str] = None,
        image_paths: Optional[List[str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Run the pipeline agent-by-agent, yielding a real event per step."""
        ctx = Context()
        if source_path:
            ctx.set("source_path", source_path)
        if claim_text:
            ctx.set("claim_text", claim_text)
        images = list(image_paths or [])
        if source_path:
            from core.tools.document_loader import extract_pdf_images
            images += extract_pdf_images(source_path)
        if images:
            ctx.set("image_paths", images)

        agents = self.pipeline.orchestrator.agents
        yield {
            "type": "run",
            "run_id": ctx.run_id,
            "agents": [{"name": a.name, "info": AGENT_INFO.get(a.name, "")} for a in agents],
        }

        for i, agent in enumerate(agents):
            yield {"type": "agent_start", "index": i, "agent": agent.name}
            agent.run(ctx)
            tr = ctx.trace[-1]
            ok = tr.status.value == "ok"
            yield {
                "type": "agent_done",
                "index": i,
                "agent": agent.name,
                "ok": ok,
                "tone": _agent_tone(agent.name, ctx, ok),
                "summary": tr.summary or tr.error or "",
                "duration_ms": round(tr.duration_ms, 1),
            }

        report = ctx.get("report")
        if isinstance(report, dict):
            if ctx.get("summary") is not None:
                report["summary"] = ctx.get("summary")
            if ctx.get("notification") is not None:
                report["notification"] = ctx.get("notification")
            if ctx.get("visual_validation") is not None:
                report["visual_validation"] = ctx.get("visual_validation")
            report["trace"] = [tr.model_dump() for tr in ctx.trace]
        from domain.schemas.claim import (  # noqa: E402
            Adjudication, ClaimDecisionReport, Decision, ExtractedClaim,
        )
        if report is None:
            report = ClaimDecisionReport(
                run_id=ctx.run_id,
                extracted=ExtractedClaim(**ctx.get("extracted", {})),
                adjudication=Adjudication(decision=Decision.REVIEW, reasons=ctx.errors or ["incomplete"]),
            ).model_dump(mode="json")
        else:
            # re-validate through the model so enums serialise to clean strings
            report = ClaimDecisionReport(**report).model_dump(mode="json")

        filename, raw_text = self._meta(source_path, claim_text, source_filename)
        with session_scope() as session:
            claim = save_claim_report(session, report, filename, raw_text)
            detail = claim.to_detail()
        yield {"type": "done", "claim": detail}

    def list(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with session_scope() as session:
            return [c.to_summary() for c in list_claims(session, limit, offset)]

    def get(self, claim_id: int) -> Optional[Dict[str, Any]]:
        with session_scope() as session:
            claim = get_claim(session, claim_id)
            return claim.to_detail() if claim else None

    def stats(self) -> Dict[str, Any]:
        from db.repository import stats as _stats
        with session_scope() as session:
            return _stats(session)

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _meta(source_path, claim_text, source_filename):
        filename = source_filename or (Path(source_path).name if source_path else None)
        raw_text = claim_text
        if raw_text is None and source_path:
            try:
                raw_text = Path(source_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                raw_text = None
        return filename, raw_text

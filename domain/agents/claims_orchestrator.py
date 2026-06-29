"""
domain.agents.claims_orchestrator
==============================
The claims-specific assembly of the generic Orchestrator. This is the single
entry point most callers use:

    from domain.agents.claims_orchestrator import ClaimsPipeline
    report = ClaimsPipeline().process(source_path="data/sample_claims/claim_auto_01.txt")

Because it only *composes* reusable pieces, building a different workflow (say,
invoice approval) means writing new agents and a new 5-line pipeline like this —
the core, tools, registry and orchestrator are untouched.
"""
from __future__ import annotations

from typing import Optional

from core.agents.orchestrator import Orchestrator
from core.schemas.base import Context
from core.tools.llm_client import LLMClient
from core.tools.registry import ToolRegistry
from domain.agents.adjudication_agent import AdjudicationAgent
from domain.agents.extraction_agent import ExtractionAgent
from domain.agents.intake_agent import IntakeAgent
from domain.agents.policy_agent import PolicyAgent
from domain.agents.validation_agent import ValidationAgent
from domain.agents.visual_validation_agent import VisualValidationAgent
from domain.agents.summarizer_agent import SummarizerAgent
from domain.agents.notification_agent import NotificationAgent
from domain.schemas.claim import ClaimDecisionReport


class ClaimsPipeline:
    def __init__(self, llm: Optional[LLMClient] = None) -> None:
        self.llm = llm or LLMClient()
        # one shared registry of reusable tools, injected into every agent
        self.tools = ToolRegistry.default(llm=self.llm)
        # add a retriever explicitly (default() registers the others)
        from core.tools.retriever import KeywordRetrieverTool

        if not self.tools.has("retriever"):
            self.tools.register(KeywordRetrieverTool())

        self.orchestrator = Orchestrator(
            agents=[
                IntakeAgent(tools=self.tools, llm=self.llm),
                ExtractionAgent(tools=self.tools, llm=self.llm),
                PolicyAgent(tools=self.tools, llm=self.llm),
                ValidationAgent(tools=self.tools, llm=self.llm),
                VisualValidationAgent(tools=self.tools, llm=self.llm),
                AdjudicationAgent(tools=self.tools, llm=self.llm),
                SummarizerAgent(tools=self.tools, llm=self.llm),
                NotificationAgent(tools=self.tools, llm=self.llm),
            ],
            fail_fast=False,
        )

    def process(
        self,
        source_path: Optional[str] = None,
        claim_text: Optional[str] = None,
        image_paths: Optional[list] = None,
    ) -> ClaimDecisionReport:
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
        ctx = self.orchestrator.run(ctx)

        report = ctx.get("report")
        if isinstance(report, dict):
            if ctx.get("summary") is not None:
                report["summary"] = ctx.get("summary")
            if ctx.get("notification") is not None:
                report["notification"] = ctx.get("notification")
            if ctx.get("visual_validation") is not None:
                report["visual_validation"] = ctx.get("visual_validation")
            # refresh the trace so it reflects the full run (all agents)
            report["trace"] = [tr.model_dump() for tr in ctx.trace]
        if report is None:
            # pipeline failed before adjudication; surface a minimal report
            from domain.schemas.claim import Adjudication, Decision, ExtractedClaim

            report = ClaimDecisionReport(
                run_id=ctx.run_id,
                extracted=ExtractedClaim(**ctx.get("extracted", {})),
                adjudication=Adjudication(
                    decision=Decision.ESCALATE,
                    reasons=ctx.errors or ["pipeline incomplete"],
                ),
                trace=[t.model_dump() for t in ctx.trace],
            ).model_dump()
        return ClaimDecisionReport(**report)

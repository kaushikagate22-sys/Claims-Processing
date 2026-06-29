"""
core.agents.base_agent
====================
An Agent is a unit of reasoning/work that reads from and writes to the shared
`Context`. Agents own no transport or persistence concerns — they just compose
tools and (optionally) an LLM. That makes them trivially reusable and testable.

Subclasses implement `act(context)`; the base wraps it with timing, logging and
uniform error capture so a single failing agent degrades gracefully instead of
crashing the run.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from core.schemas.base import AgentResult, Context, Status, Timer
from core.tools.llm_client import LLMClient
from core.tools.registry import ToolRegistry
from core.utils.logger import get_logger


class BaseAgent(ABC):
    #: unique agent name (used in traces)
    name: str = "base_agent"

    def __init__(
        self,
        tools: Optional[ToolRegistry] = None,
        llm: Optional[LLMClient] = None,
    ) -> None:
        self.llm = llm or LLMClient()
        self.tools = tools or ToolRegistry.default(llm=self.llm)
        self.log = get_logger(f"agent.{self.name}")

    @abstractmethod
    def act(self, context: Context) -> str:
        """Do the work; mutate context.payload; return a short summary string."""

    def run(self, context: Context) -> Context:
        summary, error = "", None
        with Timer() as t:
            try:
                summary = self.act(context)
            except Exception as exc:  # noqa: BLE001
                self.log.exception("agent failed")
                error = str(exc)
        # t.ms is available only after the with-block exits
        status = Status.ERROR if error else Status.OK
        result = AgentResult(
            agent=self.name, status=status, summary=summary, error=error, duration_ms=t.ms
        )
        context.record(result)
        self.log.info("%s done in %.1fms — %s", self.name, t.ms, result.summary or result.error)
        return context

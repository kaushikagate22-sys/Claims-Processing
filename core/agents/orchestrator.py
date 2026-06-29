"""
core.agents.orchestrator
======================
A generic, reusable pipeline runner. Give it an ordered list of agents and it
threads a single `Context` through them, with optional fail-fast behaviour and
a conditional `should_continue` hook.

This is domain-agnostic: the *same* Orchestrator powers the claims flow, an
invoice-approval flow, a KYC flow, etc. Only the agent list changes.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from core.agents.base_agent import BaseAgent
from core.schemas.base import Context
from core.utils.logger import get_logger

log = get_logger("orchestrator")

# Predicate: given context, return True to keep going to the next agent.
ContinuePredicate = Callable[[Context], bool]


class Orchestrator:
    def __init__(
        self,
        agents: List[BaseAgent],
        fail_fast: bool = False,
        should_continue: Optional[ContinuePredicate] = None,
    ) -> None:
        self.agents = agents
        self.fail_fast = fail_fast
        self.should_continue = should_continue

    def run(self, context: Optional[Context] = None) -> Context:
        ctx = context or Context()
        log.info("pipeline start run_id=%s agents=%s", ctx.run_id, [a.name for a in self.agents])
        for agent in self.agents:
            agent.run(ctx)
            if self.fail_fast and ctx.errors:
                log.warning("fail-fast: stopping after %s", agent.name)
                break
            if self.should_continue and not self.should_continue(ctx):
                log.info("halt: predicate stopped pipeline after %s", agent.name)
                break
        log.info("pipeline done run_id=%s errors=%d", ctx.run_id, len(ctx.errors))
        return ctx

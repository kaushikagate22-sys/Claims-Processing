"""
core.schemas.base
=================
Shared, framework-level data contracts used by every agent and tool.

These are intentionally domain-agnostic. Anything claims-specific lives in
`domain/schemas`. Keeping this layer generic is what lets the same agents,
tools and orchestrator be reused for *any* document -> extract -> decide
workflow (KYC, invoice approval, loan underwriting, etc.).
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Generic execution status for a tool or agent step."""

    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class ToolResult(BaseModel):
    """Uniform envelope returned by every tool's `run()`."""

    tool: str
    status: Status = Status.OK
    data: Any = None
    error: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == Status.OK


class AgentResult(BaseModel):
    """What an agent reports after it runs."""

    agent: str
    status: Status = Status.OK
    summary: str = ""
    error: Optional[str] = None
    duration_ms: float = 0.0


class Context(BaseModel):
    """
    The shared "blackboard" passed down a pipeline.

    Agents read what they need from `payload`, write their output back into it,
    and append a trace entry. Because it's a plain dict-backed object, agents
    stay decoupled: they communicate only through well-known keys, never by
    importing each other.
    """

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    payload: Dict[str, Any] = Field(default_factory=dict)
    trace: List[AgentResult] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # --- convenience accessors -------------------------------------------
    def set(self, key: str, value: Any) -> "Context":
        self.payload[key] = value
        return self

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)

    def record(self, result: AgentResult) -> None:
        self.trace.append(result)
        if result.error:
            self.errors.append(f"{result.agent}: {result.error}")

    @property
    def failed(self) -> bool:
        return len(self.errors) > 0


class Timer:
    """Tiny context-manager stopwatch (milliseconds)."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.ms = (time.perf_counter() - self._start) * 1000

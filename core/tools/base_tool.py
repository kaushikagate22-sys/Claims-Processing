"""
core.tools.base_tool
====================
Every reusable capability in the platform is a `Tool`. A tool is a small,
single-responsibility unit with a stable signature, so it can be:

  * called directly in code            -> tool.run(**kwargs)
  * called by name through the registry-> registry.call("document_loader", path=...)
  * handed to an LLM as a callable     -> tool.spec() returns an LLM-friendly schema

This uniformity is what makes the 60-70% "reusable" claim real: a new use case
just composes existing tools instead of rewriting plumbing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from core.schemas.base import Status, ToolResult
from core.utils.logger import get_logger


class BaseTool(ABC):
    #: unique, snake_case identifier used by the registry
    name: str = "base_tool"
    #: human/LLM readable description of what the tool does
    description: str = "Abstract base tool."
    #: lightweight description of expected kwargs (name -> description)
    params: Dict[str, str] = {}

    def __init__(self) -> None:
        self.log = get_logger(f"tool.{self.name}")

    @abstractmethod
    def _run(self, **kwargs: Any) -> Any:
        """Subclasses implement the real work and return raw data."""

    def run(self, **kwargs: Any) -> ToolResult:
        """Public entry point: wraps `_run` in a uniform result + error guard."""
        try:
            data = self._run(**kwargs)
            return ToolResult(tool=self.name, status=Status.OK, data=data)
        except Exception as exc:  # noqa: BLE001 - tools must never crash a pipeline
            self.log.exception("tool failed")
            return ToolResult(tool=self.name, status=Status.ERROR, error=str(exc))

    def spec(self) -> Dict[str, Any]:
        """LLM-friendly schema (useful for tool-calling / function-calling)."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.params,
        }

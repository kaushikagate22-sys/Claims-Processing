"""
core.tools.registry
==================
A central registry so any tool can be discovered and invoked **by name**.

    registry = ToolRegistry.default()        # auto-loads built-in tools
    result = registry.call("retriever", query="...", documents=[...])

This decouples agents from concrete tool classes. Swap an implementation
(e.g. KeywordRetriever -> EmbeddingRetriever) in one place and every caller
benefits. New use cases register their own tools the same way.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.schemas.base import Status, ToolResult
from core.tools.base_tool import BaseTool
from core.utils.logger import get_logger

log = get_logger("registry")


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    # --- registration -----------------------------------------------------
    def register(self, tool: BaseTool, *, overwrite: bool = False) -> BaseTool:
        if tool.name in self._tools and not overwrite:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool
        log.debug("registered tool: %s", tool.name)
        return tool

    # --- lookup -----------------------------------------------------------
    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"No tool named '{name}'. Available: {self.list()}")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list(self) -> List[str]:
        return sorted(self._tools)

    def specs(self) -> List[Dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]

    # --- invocation -------------------------------------------------------
    def call(self, name: str, **kwargs: Any) -> ToolResult:
        if not self.has(name):
            return ToolResult(
                tool=name, status=Status.ERROR, error=f"unknown tool '{name}'"
            )
        return self.get(name).run(**kwargs)

    # --- factory ----------------------------------------------------------
    @classmethod
    def default(cls, llm: Optional[Any] = None) -> "ToolRegistry":
        """Build a registry pre-loaded with the built-in reusable tools."""
        from core.tools.document_loader import DocumentLoaderTool
        from core.tools.extractor import StructuredExtractorTool
        from core.tools.llm_client import LLMClient
        from core.tools.record_store import RecordStoreTool
        from core.tools.retriever import KeywordRetrieverTool
        from core.tools.rules_engine import RulesEngineTool
        from core.tools.summarizer import SummarizerTool
        from core.tools.notifier import NotifierTool
        from core.tools.master_data import MasterDataTool
        from core.tools.vision import VisionTool

        llm = llm or LLMClient()
        reg = cls()
        reg.register(DocumentLoaderTool())
        reg.register(KeywordRetrieverTool())
        reg.register(RulesEngineTool())
        reg.register(RecordStoreTool())
        reg.register(StructuredExtractorTool(llm=llm))
        reg.register(SummarizerTool(llm=llm))
        reg.register(NotifierTool())
        reg.register(MasterDataTool())
        reg.register(VisionTool(llm=llm))
        return reg

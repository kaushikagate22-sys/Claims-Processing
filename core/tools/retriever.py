"""
core.tools.retriever
===================
Retrieval-Augmented Generation (RAG) building block.

`KeywordRetrieverTool` is a dependency-free TF-style retriever: it chunks a
document, scores chunks by token overlap with the query, and returns the top-k.
Good enough to pull the right policy section offline.

Swap in an embedding-backed retriever later by implementing the same `_run`
contract and registering it under the same name — no agent changes needed.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from core.tools.base_tool import BaseTool

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


def chunk_text(text: str, max_chars: int = 700, overlap: int = 80) -> List[str]:
    """Split on blank lines / headings, then pack into ~max_chars windows."""
    blocks = re.split(r"\n\s*\n", text.strip())
    chunks: List[str] = []
    buf = ""
    for block in blocks:
        if len(buf) + len(block) + 2 <= max_chars:
            buf = f"{buf}\n\n{block}".strip()
        else:
            if buf:
                chunks.append(buf)
            if len(block) <= max_chars:
                buf = block
            else:
                for i in range(0, len(block), max_chars - overlap):
                    chunks.append(block[i : i + max_chars])
                buf = ""
    if buf:
        chunks.append(buf)
    return [c for c in chunks if c.strip()]


class KeywordRetrieverTool(BaseTool):
    name = "retriever"
    description = "Retrieve the most relevant chunks of a document for a query."
    params = {
        "query": "the search query",
        "text": "the full source document text (alternative to `chunks`)",
        "chunks": "pre-chunked list of strings (alternative to `text`)",
        "top_k": "number of chunks to return (default 4)",
        "section_filter": "optional substring; only chunks containing it are scored",
    }

    def _run(
        self,
        query: str,
        text: Optional[str] = None,
        chunks: Optional[List[str]] = None,
        top_k: int = 4,
        section_filter: Optional[str] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        if chunks is None:
            if text is None:
                raise ValueError("Provide either `text` or `chunks`")
            chunks = chunk_text(text)

        candidates = chunks
        if section_filter:
            sf = section_filter.lower()
            filtered = [c for c in chunks if sf in c.lower()]
            candidates = filtered or chunks  # fall back if filter is too strict

        scored = self._score(query, candidates)
        top = scored[:top_k]
        return {
            "query": query,
            "results": [{"text": c, "score": round(s, 4)} for s, c in top],
            "context": "\n\n---\n\n".join(c for _, c in top),
            "n_chunks": len(candidates),
        }

    @staticmethod
    def _score(query: str, chunks: List[str]) -> List:
        q_tokens = Counter(_tokenize(query))
        # idf-ish weighting so common words count less
        df: Counter = Counter()
        chunk_tokens = []
        for c in chunks:
            toks = Counter(_tokenize(c))
            chunk_tokens.append(toks)
            for t in toks:
                df[t] += 1
        n = len(chunks) or 1
        scored = []
        for c, toks in zip(chunks, chunk_tokens):
            score = 0.0
            for t, qf in q_tokens.items():
                if t in toks:
                    idf = math.log((n + 1) / (df[t] + 0.5))
                    score += qf * toks[t] * idf
            scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

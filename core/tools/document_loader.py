"""
core.tools.document_loader
========================
Load a file (or raw bytes) into plain text. Supports txt/md natively and
pdf/docx when the optional libs are installed (lazy import, never required).

Reusable anywhere you need "file -> text": claims, invoices, contracts, KYC.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from core.tools.base_tool import BaseTool


class DocumentLoaderTool(BaseTool):
    name = "document_loader"
    description = "Load a document from a path and return its text content."
    params = {"path": "absolute or relative path to the file to load"}

    SUPPORTED = {".txt", ".md", ".pdf", ".docx"}

    def _run(self, path: str, **_: Any) -> Dict[str, Any]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        ext = p.suffix.lower()
        if ext in {".txt", ".md"}:
            text = p.read_text(encoding="utf-8", errors="ignore")
        elif ext == ".pdf":
            text = self._load_pdf(p)
        elif ext == ".docx":
            text = self._load_docx(p)
        else:
            raise ValueError(f"Unsupported file type '{ext}'. Supported: {self.SUPPORTED}")
        return {
            "text": text,
            "filename": p.name,
            "ext": ext,
            "chars": len(text),
            "size_bytes": os.path.getsize(p),
        }

    @staticmethod
    def _load_pdf(p: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as e:  # pragma: no cover
            raise ImportError("pip install pypdf to read PDFs") from e
        reader = PdfReader(str(p))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    @staticmethod
    def _load_docx(p: Path) -> str:
        try:
            import docx  # python-docx
        except ImportError as e:  # pragma: no cover
            raise ImportError("pip install python-docx to read .docx") from e
        d = docx.Document(str(p))
        return "\n".join(par.text for par in d.paragraphs)


def extract_pdf_images(path) -> list:
    """Return raw bytes of images embedded in a PDF (best-effort, never raises).
    Used so a claim PDF that contains photos feeds them to visual validation."""
    from pathlib import Path as _P
    p = _P(str(path))
    if p.suffix.lower() != ".pdf" or not p.exists():
        return []
    out = []
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        for page in reader.pages:
            try:
                for image in page.images:
                    data = getattr(image, "data", None)
                    if data:
                        out.append(data)
            except Exception:  # noqa: BLE001 - some pages have no images / odd encodings
                continue
    except Exception:  # noqa: BLE001
        return out
    return out

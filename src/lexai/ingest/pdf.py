"""PDF text extraction for moot problem inputs.

Wraps pypdf.PdfReader. Pages are joined with blank lines so downstream
paragraph-boundary chunking has stable separators.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def extract_pdf_text(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")
    reader = PdfReader(str(p))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)

"""Word-window chunking for case text.

Produces fixed-size overlapping chunks suitable for embedding. Token
counting is approximated as whitespace-split word count — adequate for
voyage-law-2 (max 32K tokens per doc, we chunk to 500-word windows).
Each chunk carries the source case's metadata so Pinecone queries can
return citation-ready results without a second lookup.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CHUNK_SIZE = 500
OVERLAP = 50


class CaseMetadata(BaseModel):
    case_slug: str
    case_title: str
    citation: str
    court: str
    year: int
    area_of_law: str


class Chunk(BaseModel):
    chunk_id: str
    case_slug: str
    chunk_index: int
    text: str
    case_title: str
    citation: str
    court: str
    year: int
    area_of_law: str = Field(default="")


def chunk_case(
    text: str,
    meta: CaseMetadata,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[Chunk]:
    words = text.split()
    if not words:
        return []

    stride = chunk_size - overlap
    if stride <= 0:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[Chunk] = []
    start = 0
    index = 0
    while start < len(words):
        window = words[start : start + chunk_size]
        chunks.append(
            Chunk(
                chunk_id=f"{meta.case_slug}::{index}",
                case_slug=meta.case_slug,
                chunk_index=index,
                text=" ".join(window),
                case_title=meta.case_title,
                citation=meta.citation,
                court=meta.court,
                year=meta.year,
                area_of_law=meta.area_of_law,
            )
        )
        if start + chunk_size >= len(words):
            break
        start += stride
        index += 1
    return chunks

"""Pinecone vectorstore: upsert + query with chunk metadata.

Each vector's Pinecone metadata carries the full Chunk (citation, court,
year, chunk text) so a query hit is citation-ready without a second DB
lookup. Upserts are batched at 100/vector per Pinecone's recommended
limit — exceeding it yields flaky 413s in practice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable

from pinecone import Pinecone

from lexai.ingest.chunk import Chunk

UPSERT_BATCH = 100


@dataclass(frozen=True)
class Match:
    chunk_id: str
    score: float
    case_slug: str
    case_title: str
    citation: str
    court: str
    year: int
    area_of_law: str
    chunk_index: int
    text: str


def get_index(index_name: str | None = None):
    name = index_name or os.environ["PINECONE_INDEX"]
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    return pc.Index(name)


def _chunk_to_vector_record(chunk: Chunk, embedding: list[float]) -> dict[str, Any]:
    return {
        "id": chunk.chunk_id,
        "values": embedding,
        "metadata": {
            "case_slug": chunk.case_slug,
            "chunk_index": chunk.chunk_index,
            "case_title": chunk.case_title,
            "citation": chunk.citation,
            "court": chunk.court,
            "year": chunk.year,
            "area_of_law": chunk.area_of_law,
            "text": chunk.text,
        },
    }


def upsert_chunks(index, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    if len(chunks) != len(vectors):
        raise ValueError(
            f"chunks ({len(chunks)}) and vectors ({len(vectors)}) length mismatch"
        )
    if not chunks:
        return

    records = [
        _chunk_to_vector_record(chunk, vec) for chunk, vec in zip(chunks, vectors)
    ]
    for i in range(0, len(records), UPSERT_BATCH):
        batch = records[i : i + UPSERT_BATCH]
        index.upsert(vectors=batch)


def query(index, *, vector: list[float], top_k: int = 15) -> list[Match]:
    resp = index.query(vector=vector, top_k=top_k, include_metadata=True)
    matches_raw: Iterable[dict[str, Any]] = resp.get("matches", []) if isinstance(resp, dict) else getattr(resp, "matches", [])
    results: list[Match] = []
    for m in matches_raw:
        md = m["metadata"] if isinstance(m, dict) else m.metadata
        mid = m["id"] if isinstance(m, dict) else m.id
        score = m["score"] if isinstance(m, dict) else m.score
        results.append(
            Match(
                chunk_id=mid,
                score=float(score),
                case_slug=md["case_slug"],
                case_title=md["case_title"],
                citation=md["citation"],
                court=md["court"],
                year=int(md["year"]),
                area_of_law=md.get("area_of_law", ""),
                chunk_index=int(md["chunk_index"]),
                text=md["text"],
            )
        )
    return results

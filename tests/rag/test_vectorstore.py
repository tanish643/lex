from unittest.mock import MagicMock

import pytest

from lexai.ingest.chunk import Chunk
from lexai.rag.vectorstore import Match, query, upsert_chunks


def _chunk(i: int, slug: str = "test-slug") -> Chunk:
    return Chunk(
        chunk_id=f"{slug}::{i}",
        case_slug=slug,
        chunk_index=i,
        text=f"chunk {i} text body",
        case_title="Test v Tester",
        citation="AIR 2026 SC 1",
        court="Supreme Court of India",
        year=2026,
        area_of_law="constitutional",
    )


def test_upsert_chunks_batches_and_sends_metadata(monkeypatch):
    sent: list[list[dict]] = []

    fake_index = MagicMock()
    fake_index.upsert = lambda vectors: sent.append(list(vectors))

    chunks = [_chunk(i) for i in range(3)]
    vectors = [[float(i)] * 4 for i in range(3)]

    upsert_chunks(fake_index, chunks, vectors)

    assert len(sent) == 1  # single batch
    assert len(sent[0]) == 3
    first = sent[0][0]
    assert first["id"] == "test-slug::0"
    assert first["values"] == [0.0, 0.0, 0.0, 0.0]
    meta = first["metadata"]
    assert meta["case_slug"] == "test-slug"
    assert meta["citation"] == "AIR 2026 SC 1"
    assert meta["court"] == "Supreme Court of India"
    assert meta["year"] == 2026
    assert meta["area_of_law"] == "constitutional"
    assert meta["chunk_index"] == 0
    assert meta["text"] == "chunk 0 text body"


def test_upsert_chunks_splits_large_input(monkeypatch):
    # Pinecone recommends batches of <=100 vectors
    sent_batch_sizes: list[int] = []
    fake_index = MagicMock()
    fake_index.upsert = lambda vectors: sent_batch_sizes.append(len(list(vectors)))

    chunks = [_chunk(i) for i in range(250)]
    vectors = [[0.0] * 4 for _ in range(250)]
    upsert_chunks(fake_index, chunks, vectors)

    assert sum(sent_batch_sizes) == 250
    assert max(sent_batch_sizes) <= 100


def test_upsert_chunks_raises_on_length_mismatch():
    fake_index = MagicMock()
    with pytest.raises(ValueError):
        upsert_chunks(fake_index, [_chunk(0)], [[0.0], [0.0]])


def test_query_returns_matches():
    fake_index = MagicMock()
    fake_index.query.return_value = {
        "matches": [
            {
                "id": "test-slug::0",
                "score": 0.87,
                "metadata": {
                    "case_slug": "test-slug",
                    "case_title": "Test v Tester",
                    "citation": "AIR 2026 SC 1",
                    "text": "chunk body",
                    "court": "Supreme Court of India",
                    "year": 2026,
                    "area_of_law": "constitutional",
                    "chunk_index": 0,
                },
            }
        ]
    }

    results = query(fake_index, vector=[0.0] * 4, top_k=5)
    assert len(results) == 1
    m = results[0]
    assert isinstance(m, Match)
    assert m.chunk_id == "test-slug::0"
    assert m.score == 0.87
    assert m.case_slug == "test-slug"
    assert m.citation == "AIR 2026 SC 1"
    fake_index.query.assert_called_once_with(
        vector=[0.0] * 4, top_k=5, include_metadata=True
    )

"""Embed + upsert every scraped case file into Pinecone.

Resumable: reads data/ingested.json (gitignored) as the marker of which
case slugs have completed. Run repeatedly; safe to Ctrl-C mid-batch
since marker is only updated after a successful upsert for the whole
case.

Voyage free tier is 3 RPM; the embed wrapper retries with backoff, so
ingest is slow (~3-5 min for 11 cases) but reliable.

Usage:
    uv run python scripts/ingest_corpus.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from lexai.ingest.chunk import CaseMetadata, chunk_case
from lexai.rag.embed import embed_texts
from lexai.rag.vectorstore import get_index, upsert_chunks

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "seed_cases_v1.csv"
CASES_DIR = ROOT / "data" / "cases"
MARKER_PATH = ROOT / "data" / "ingested.json"

# Phase 1 free-tier guard: skip cases that produce too many chunks,
# they'd eat our entire Voyage TPM budget. Re-run with --include-large
# (TODO) once we're on a paid tier or during Task 16 hardening.
MAX_CHUNKS_PER_CASE = 160


def _slugify(value: str) -> str:
    import re

    lowered = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "unknown"


def _load_marker() -> set[str]:
    if MARKER_PATH.exists():
        return set(json.loads(MARKER_PATH.read_text(encoding="utf-8")))
    return set()


def _save_marker(ingested: set[str]) -> None:
    MARKER_PATH.write_text(json.dumps(sorted(ingested), indent=2), encoding="utf-8")


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} missing", file=sys.stderr)
        return 1

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    ingested = _load_marker()
    index = get_index()

    stats = {"done": 0, "skipped": 0, "missing_file": 0, "chunks_upserted": 0}

    for i, row in enumerate(rows, start=1):
        citation = row["citation"].strip()
        slug = _slugify(citation)
        case_path = CASES_DIR / f"{slug}.txt"

        if slug in ingested:
            print(f"[{i}/{len(rows)}] SKIP (already ingested): {slug}")
            stats["skipped"] += 1
            continue

        if not case_path.exists():
            print(f"[{i}/{len(rows)}] MISSING (no scraped file): {slug}")
            stats["missing_file"] += 1
            continue

        text = case_path.read_text(encoding="utf-8")
        meta = CaseMetadata(
            case_slug=slug,
            case_title=row["case_title"].strip(),
            citation=citation,
            court=row["court"].strip(),
            year=int(row["year"]),
            area_of_law=row["area_of_law"].strip(),
        )
        chunks = chunk_case(text, meta)
        if not chunks:
            print(f"[{i}/{len(rows)}] EMPTY: {slug} produced no chunks")
            continue

        if len(chunks) > MAX_CHUNKS_PER_CASE:
            print(
                f"[{i}/{len(rows)}] SKIP (>{MAX_CHUNKS_PER_CASE} chunks, free-tier guard): "
                f"{slug} has {len(chunks)} chunks"
            )
            stats["skipped"] += 1
            continue

        print(f"[{i}/{len(rows)}] embedding {len(chunks)} chunks for {slug} ...")
        vectors = embed_texts([c.text for c in chunks], input_type="document")
        upsert_chunks(index, chunks, vectors)

        ingested.add(slug)
        _save_marker(ingested)
        stats["done"] += 1
        stats["chunks_upserted"] += len(chunks)
        print(f"[{i}/{len(rows)}] OK: upserted {len(chunks)} vectors for {slug}")

    print()
    print(f"Completed:       {stats['done']}")
    print(f"Skipped:         {stats['skipped']}")
    print(f"Missing file:    {stats['missing_file']}")
    print(f"Total vectors:   {stats['chunks_upserted']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

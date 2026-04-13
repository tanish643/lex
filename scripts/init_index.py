"""Idempotent Pinecone index bootstrap.

Creates a serverless index named $PINECONE_INDEX (default 'lex-cases-v1')
sized for voyage-law-2 (1024 dims, cosine). Region aws/us-east-1 — the
free Starter plan doesn't offer ap-south-1 (Mumbai) which the plan
originally targeted, so we accept the ~200ms extra latency for $0 cost.

Usage:
    uv run python scripts/init_index.py
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

from lexai.rag.embed import VOYAGE_DIM

load_dotenv()


def main() -> int:
    api_key = os.environ.get("PINECONE_API_KEY")
    index_name = os.environ.get("PINECONE_INDEX", "lex-cases-v1")
    if not api_key:
        print("ERROR: PINECONE_API_KEY missing", file=sys.stderr)
        return 1

    pc = Pinecone(api_key=api_key)
    existing = {ix["name"] for ix in pc.list_indexes()}

    if index_name in existing:
        print(f"Index '{index_name}' already exists. Skipping create.")
        return 0

    print(f"Creating serverless index '{index_name}' (dim={VOYAGE_DIM}, cosine, aws/us-east-1)...")
    pc.create_index(
        name=index_name,
        dimension=VOYAGE_DIM,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1"),
    )

    # poll until ready (usually < 30s)
    for _ in range(60):
        desc = pc.describe_index(index_name)
        if desc.get("status", {}).get("ready"):
            print(f"Index ready. Host: {desc['host']}")
            return 0
        time.sleep(2)

    print(f"Index '{index_name}' did not become ready within 120s", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

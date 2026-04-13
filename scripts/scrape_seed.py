"""Scrape Indian Kanoon judgment text for each seed case row.

Reads data/seed_cases_v1.csv, fetches each row's indian_kanoon_url,
extracts judgment text via lexai.ingest.scraper.extract_case_text,
and writes data/cases/{slug}.txt. Idempotent: skips files already
on disk. Rate-limited to 2s between requests per the Phase 1 plan.

Usage:
    uv run python scripts/scrape_seed.py
"""

from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path

import httpx

from lexai.ingest.scraper import fetch_case

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "seed_cases_v1.csv"
OUT_DIR = ROOT / "data" / "cases"
DELAY_SECONDS = 2.0
USER_AGENT = "LexAI-seed-scrape/0.1 (research; contact: tanish@example.com)"


def slugify(value: str) -> str:
    """Stable slug from a citation string, e.g. 'AIR 1978 SC 597' -> 'air-1978-sc-597'."""
    lowered = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return cleaned or "unknown"


def main() -> int:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    skipped_no_url = 0
    skipped_existing = 0
    succeeded = 0
    failed: list[tuple[str, str]] = []

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for i, row in enumerate(rows, start=1):
            url = row.get("indian_kanoon_url", "").strip()
            citation = row.get("citation", "").strip()
            title = row.get("case_title", "").strip()

            if not url:
                print(f"[{i}/{len(rows)}] SKIP (no url): {title}")
                skipped_no_url += 1
                continue

            slug = slugify(citation)
            out_path = OUT_DIR / f"{slug}.txt"

            if out_path.exists():
                print(f"[{i}/{len(rows)}] SKIP (exists): {slug}.txt")
                skipped_existing += 1
                continue

            try:
                text = fetch_case(url, client)
            except Exception as exc:
                print(f"[{i}/{len(rows)}] FAIL: {title} -> {exc}", file=sys.stderr)
                failed.append((title, str(exc)))
                time.sleep(DELAY_SECONDS)
                continue

            out_path.write_text(text, encoding="utf-8")
            print(f"[{i}/{len(rows)}] OK:   {slug}.txt ({len(text):,} chars)")
            succeeded += 1
            time.sleep(DELAY_SECONDS)

    print()
    print(f"Succeeded:         {succeeded}")
    print(f"Skipped (exists):  {skipped_existing}")
    print(f"Skipped (no url):  {skipped_no_url}")
    print(f"Failed:            {len(failed)}")
    for title, exc in failed:
        print(f"  - {title}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

# `data/` — corpus inputs

## `seed_cases_v1.csv`

100-case landmark Indian judgments corpus. **Currently 12 anchor rows seeded — needs ~88 more before Task 4 (scrape).**

### Schema

| Column | Notes |
|---|---|
| `case_title` | Full case name as commonly cited |
| `citation` | Primary citation (AIR / SCC / SCC OnLine) |
| `court` | Full court name (e.g. "Supreme Court of India", "Bombay High Court") |
| `year` | Year of judgment |
| `area_of_law` | One of: `constitutional`, `criminal`, `contract`, `commercial`, `tax`, `ipr`, `family` |
| `indian_kanoon_url` | Full URL like `https://indiankanoon.org/doc/{id}/` — **leave blank for me to fill, will be populated during Task 4 prep** |

### Target distribution (per Phase 1 plan, Task 2)

- ~40 constitutional (Art 14 / 19 / 21 / 32 landmarks)
- ~30 criminal (IPC, NDPS, CrPC landmarks)
- ~30 contract & commercial (Indian Contract Act essentials, consumer law)

### How to fill in URLs

1. Open https://indiankanoon.org/
2. Search the case title in quotes (e.g. `"Maneka Gandhi v Union of India"`)
3. Click the correct judgment (verify court + year match the row)
4. Copy the URL — it'll look like `https://indiankanoon.org/doc/1766147/`
5. Paste into the `indian_kanoon_url` column

### Curation guidance

Get a law-student friend to review the list before scraping. Drop any row you're unsure about — quality over quantity. The corpus is regenerable; we can always re-scrape with `seed_cases_v2.csv` later (Task 15 expands to 1,000 cases).

## `cases/` (gitignored)

Output of `scripts/scrape_seed.py` — one `.txt` per case keyed by slug.

## `index/` (gitignored)

Local marker files for resumable Pinecone ingestion.

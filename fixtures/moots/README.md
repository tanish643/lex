# `fixtures/moots/` — moot problem PDFs for testing

PDFs in this folder are **gitignored** (large binaries + potential NALSAR/Jessup distribution terms). They must be present locally for tests in `tests/ingest/test_pdf.py` and the e2e pipeline notebook to run.

## Expected fixtures

| File | Source | Used by |
|---|---|---|
| `sample.pdf` | Any public moot problem (currently: NALSAR-CCI Anti-Trust 2026) | Tasks 5, 9, 14 tests |

To re-provision on a fresh clone: download a moot problem PDF and save it as `sample.pdf` here.

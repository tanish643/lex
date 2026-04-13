# LexAI Phase 1 (De-risk) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prove the moot-court RAG pipeline produces a memorial with real, grounded citations — end-to-end in a Python CLI, without any web/UI/DB.

**Architecture:** Python 3.12 + uv. PDF ingest → issue extraction (Claude) → case retrieval (Voyage embeddings + Pinecone) → LLM re-ranking → IRAC argument generation → citation validation → DOCX memorial assembly. No database; outputs are files. Seed corpus of 100 cases Week 1, scaling to 1,000 Week 2.

**Tech Stack:** Python 3.12, uv, anthropic SDK, voyageai SDK, pinecone-client, pypdf, python-docx, httpx, beautifulsoup4, tenacity, pydantic, pytest.

**Scope boundary:** This plan covers Phase 1 only (Weeks 1–2). Phases 2 and 3 (web app, billing, etc.) will be planned after the Phase 1 success gate passes.

**Success gate for Phase 1:** On a 10-problem evaluation set, the pipeline scores ≥3/5 (law-student graded) on each of {issue extraction accuracy, case relevance, citation grounding, argument quality} AND produces zero hallucinated citations (every citation in output verifiable against Pinecone metadata).

---

## Prerequisites (do before Task 1)

- Accounts with API keys: **Anthropic Console**, **Voyage AI**, **Pinecone**.
- Copy keys into a `.env` file at repo root (template created in Task 1).
- `uv` installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`).
- 3 past moot problems as PDFs placed in `fixtures/moots/` (NLSIU, Jessup, or NALSAR archives — all public).
- A friend in law school on standby to grade outputs (Tasks 14, 21).

---

## Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `src/lexai/__init__.py`, `tests/__init__.py`

**Step 1:** Initialize uv project.

```bash
cd c:/Users/Tanish/Lex
uv init --package --name lexai --python 3.12
```

**Step 2:** Add dependencies.

```bash
uv add anthropic voyageai pinecone-client pypdf python-docx httpx beautifulsoup4 tenacity pydantic python-dotenv
uv add --dev pytest pytest-asyncio ruff
```

**Step 3:** Create `.env.example`:

```
ANTHROPIC_API_KEY=
VOYAGE_API_KEY=
PINECONE_API_KEY=
PINECONE_INDEX=lex-cases-v1
```

**Step 4:** Create `.gitignore`:

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
data/cases/
data/index/
outputs/
.ipynb_checkpoints/
*.egg-info/
```

**Step 5:** Create local `.env` by copying `.env.example` and filling in real keys. Verify not tracked.

**Step 6:** Commit.

```bash
git add pyproject.toml uv.lock .gitignore .env.example src/ tests/
git commit -m "chore: scaffold lexai package with uv"
```

---

## Task 2: Curate 100-case seed list

**Files:**
- Create: `data/seed_cases_v1.csv`

**Step 1:** Create `data/seed_cases_v1.csv` with columns: `case_title, citation, court, year, area_of_law, indian_kanoon_url`.

**Step 2:** Populate with 100 landmark cases — approximate breakdown:
- ~40 constitutional (Art 14/19/21/32 landmarks: Maneka Gandhi, Kesavananda Bharati, Puttaswamy, Navtej Johar, Shayara Bano, Indra Sawhney, Olga Tellis, M.C. Mehta v Union of India, Vishaka, etc.)
- ~30 criminal (Bachan Singh, Arnesh Kumar, D.K. Basu, Rajesh Sharma, NDPS landmarks, IPC homicide and rape leading cases)
- ~30 contract & commercial (Indian Contract Act essentials, Mohori Bibee, Satyabrata Ghose, Associated Cinemas, consumer protection leading cases)

**Step 3:** Get a law-student friend to review and swap out anything non-essential. Do not solo-curate.

**Step 4:** Commit.

```bash
git add data/seed_cases_v1.csv
git commit -m "data: curated 100-case seed list"
```

---

## Task 3: Indian Kanoon scraper

**Files:**
- Create: `src/lexai/ingest/scraper.py`
- Test: `tests/ingest/test_scraper.py`

**Step 1: Write failing test.**

```python
# tests/ingest/test_scraper.py
from lexai.ingest.scraper import extract_case_text

def test_extract_case_text_from_html():
    html = """
    <div class="judgments"><p>The appeal is dismissed.</p><p>Costs of Rs 10,000.</p></div>
    """
    result = extract_case_text(html)
    assert "appeal is dismissed" in result
    assert "10,000" in result
    assert "<p>" not in result
```

**Step 2:** Run test.

```bash
uv run pytest tests/ingest/test_scraper.py -v
```
Expected: FAIL — module not found.

**Step 3: Implement.**

```python
# src/lexai/ingest/scraper.py
import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

def extract_case_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="judgments") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    return "\n\n".join(t for t in paragraphs if t)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def fetch_case(url: str, client: httpx.Client) -> str:
    resp = client.get(url, timeout=30)
    resp.raise_for_status()
    return extract_case_text(resp.text)
```

**Step 4:** Verify test passes. Commit.

```bash
git add src/lexai/ingest/ tests/ingest/
git commit -m "feat(ingest): indian kanoon scraper with retry"
```

---

## Task 4: Run seed scrape

**Files:**
- Create: `scripts/scrape_seed.py`, `data/cases/*.txt` (output, gitignored)

**Step 1:** Write script that reads `data/seed_cases_v1.csv`, fetches each URL with 2s delay between requests, saves text to `data/cases/{slug}.txt` where slug is derived from citation. Skip if file already exists (idempotent).

**Step 2:** Run: `uv run python scripts/scrape_seed.py`. Expect ~5 minutes for 100 cases at 2s/request.

**Step 3:** Manually inspect 5 random `.txt` outputs — verify content looks clean, not navigation chrome.

**Step 4:** Commit the script (cases are gitignored).

```bash
git add scripts/scrape_seed.py
git commit -m "scripts: seed corpus scraper"
```

---

## Task 5: PDF text extraction

**Files:**
- Create: `src/lexai/ingest/pdf.py`
- Test: `tests/ingest/test_pdf.py`

**Step 1: Write failing test** using a fixture PDF at `fixtures/moots/sample.pdf`.

```python
from lexai.ingest.pdf import extract_pdf_text

def test_extract_pdf_text():
    text = extract_pdf_text("fixtures/moots/sample.pdf")
    assert len(text) > 500
    assert "\n" in text
```

**Step 2:** Run — expect FAIL.

**Step 3: Implement** using `pypdf.PdfReader`, concatenate page texts with `\n\n` separators.

**Step 4:** Run test — expect PASS. Commit.

---

## Task 6: Chunking utility

**Files:**
- Create: `src/lexai/ingest/chunk.py`
- Test: `tests/ingest/test_chunk.py`

**Step 1: Write failing tests** covering:
- A short text (< 500 tokens) returns one chunk.
- A long text returns multiple chunks with 50-token overlap.
- Paragraph boundaries are preserved where possible.
- Each chunk carries metadata (`chunk_index`, `source_case_slug`).

**Step 2:** Run — expect FAIL.

**Step 3: Implement** `chunk_case(text: str, case_meta: CaseMetadata) -> list[Chunk]`. Use whitespace tokenization (word count) as a 1-token ≈ 1-word proxy for simplicity; `chunk_size=500`, `overlap=50`. `Chunk` is a pydantic model: `{chunk_id, case_slug, chunk_index, text, case_title, citation, court, year, area_of_law}`.

**Step 4:** Run — expect PASS. Commit.

---

## Task 7: Voyage embeddings wrapper

**Files:**
- Create: `src/lexai/rag/embed.py`
- Test: `tests/rag/test_embed.py`

**Step 1: Write test** (this one hits the real API — it's a contract test, OK to be slow and gated):

```python
import pytest
from lexai.rag.embed import embed_texts

@pytest.mark.integration
def test_embed_returns_expected_dim():
    vectors = embed_texts(["hello world"], input_type="document")
    assert len(vectors) == 1
    assert len(vectors[0]) == 1024  # voyage-law-2 dim
```

**Step 2:** Run — expect FAIL.

**Step 3: Implement** using `voyageai.Client`. Model: `voyage-law-2`. Support `input_type` parameter (`"document"` for indexing, `"query"` for search — critical for asymmetric embeddings). Batch up to 128 texts per call.

**Step 4:** Run integration test (`pytest -m integration`) — expect PASS. Commit.

---

## Task 8: Pinecone setup + upsert

**Files:**
- Create: `src/lexai/rag/vectorstore.py`, `scripts/init_index.py`, `scripts/ingest_corpus.py`
- Test: `tests/rag/test_vectorstore.py`

**Step 1:** Create `init_index.py` — creates serverless index `lex-cases-v1` with dim=1024, metric=cosine, cloud=aws, region=ap-south-1 (Mumbai). Idempotent.

**Step 2:** Run: `uv run python scripts/init_index.py`. Verify in Pinecone console.

**Step 3: Write failing test** for `upsert_chunks(chunks)` — use a mock Pinecone client via monkeypatch.

**Step 4: Implement** `vectorstore.py` with `upsert_chunks`, `query(vector, top_k)`. Each vector's metadata carries the chunk's case fields.

**Step 5:** Write `scripts/ingest_corpus.py` — iterate `data/cases/*.txt`, chunk, embed in batches of 128, upsert to Pinecone. Progress bar (`tqdm`). Resumable: skip case slugs already present in a local `data/ingested.json` marker file.

**Step 6:** Run: `uv run python scripts/ingest_corpus.py`. Expect ~10 min for 100 cases.

**Step 7:** Commit.

```bash
git add src/lexai/rag/ scripts/init_index.py scripts/ingest_corpus.py tests/rag/
git commit -m "feat(rag): pinecone vectorstore + corpus ingestion"
```

---

## Task 9: Issue extraction prompt

**Files:**
- Create: `src/lexai/pipeline/issues.py`, `src/lexai/prompts/issues.py`
- Test: `tests/pipeline/test_issues.py`

**Step 1: Write failing test** on a fixture moot problem:

```python
def test_extract_issues_returns_structured_list():
    text = Path("fixtures/moots/sample.pdf").read_text(...)  # or use extract_pdf_text
    issues = extract_issues(text)
    assert len(issues) >= 2
    for issue in issues:
        assert issue.issue_title
        assert issue.area_of_law
        assert isinstance(issue.relevant_statutes, list)
```

**Step 2:** Run — expect FAIL.

**Step 3: Implement.** Prompt (in `prompts/issues.py` as a constant):

```
You are a senior Indian advocate analyzing a moot court problem.
Identify every distinct legal issue that the memorial must argue.
For each issue, return: issue_title, area_of_law, relevant_statutes (list),
relevant_articles (list), brief description (2-3 sentences).

Return ONLY valid JSON matching the schema. No prose, no markdown fences.
```

Use Claude Sonnet 4.6 via `anthropic.Anthropic().messages.create()`. Force JSON with a prefill: `messages=[...,{"role":"assistant","content":"["}]` or use tool-use for structured output. Parse into pydantic `Issue` models.

**Step 4:** Run — expect PASS. Commit.

---

## Task 10: Retrieval + re-ranking

**Files:**
- Create: `src/lexai/pipeline/research.py`, `src/lexai/prompts/rerank.py`
- Test: `tests/pipeline/test_research.py`

**Step 1: Write failing test** — given an `Issue`, returns 5 re-ranked cases.

**Step 2:** Implement `research_for_issue(issue) -> list[RankedCase]`:
1. Embed `f"{issue.issue_title}. {issue.description}"` with `input_type="query"`.
2. Pinecone query top_k=15.
3. Group chunks by `case_slug`, taking the best-scoring chunk per case (dedupe).
4. Send top 15 unique cases to Claude Haiku 4.5 with re-ranking prompt: "From the following cases, select the 5 most relevant to this issue. For each, explain in one sentence why. Return JSON."

**Step 3:** Run — expect PASS. Commit.

---

## Task 11: Argument generation

**Files:**
- Create: `src/lexai/pipeline/arguments.py`, `src/lexai/prompts/arguments.py`
- Test: `tests/pipeline/test_arguments.py`

**Step 1: Write failing test** — given issues + selected cases, returns Petitioner and Respondent arguments per issue in IRAC.

**Step 2: Implement.** Prompt (critical — this is where citation grounding lives):

```
You are a senior advocate drafting moot memorial arguments for the
Supreme Court of India. Use formal legal language. Structure each
argument using IRAC (Issue, Rule, Application, Conclusion).

You MAY cite ONLY the following cases — do not invent or reference any
other case. If you need a principle that none of these cases support,
state it without citation.

[CASES WITH CITATIONS]

For each issue, return JSON with petitioner_arguments and
respondent_arguments, each an array of IRAC blocks.
```

Use Claude Sonnet 4.6. Process one issue at a time (do not batch all issues into one call — keeps each call focused and respects token limits).

**Step 3:** Run — expect PASS. Commit.

---

## Task 12: Citation validator

**Files:**
- Create: `src/lexai/pipeline/validate.py`
- Test: `tests/pipeline/test_validate.py`

**Step 1: Write failing tests** covering:
- Valid citation passes.
- Citation referencing a case not in the provided case list → `HallucinationError`.
- Malformed citation → flagged.

**Step 2: Implement** `validate_citations(arguments, allowed_cases) -> ValidationReport`. Regex patterns for common Indian citations: `AIR \d{4} SC \d+`, `\(\d{4}\) \d+ SCC \d+`, `\d{4} SCC OnLine SC \d+`, plus fuzzy case-name matching against `allowed_cases`. Every extracted citation must match an entry in `allowed_cases`; otherwise it's a hallucination.

**Step 3:** Run — expect PASS. Commit.

This is the single most important quality gate of the entire pipeline.

---

## Task 13: DOCX memorial assembly

**Files:**
- Create: `src/lexai/pipeline/memorial.py`
- Test: `tests/pipeline/test_memorial.py`

**Step 1: Write failing test** — given issues + arguments + case list, produces a `.docx` file with expected sections: Cover Page, Index of Authorities, Statement of Jurisdiction, Statement of Facts, Issues Raised, Summary of Arguments, Arguments Advanced, Prayer.

**Step 2: Implement** using `python-docx`. Use a template with styles pre-defined (Heading 1/2/3, Body, Citation). Table of Authorities auto-generated from cited cases.

**Step 3:** Run — expect PASS. Open generated DOCX in Word, eyeball the formatting. Commit.

---

## Task 14: End-to-end pipeline run (notebook)

**Files:**
- Create: `notebooks/01_e2e_pipeline.ipynb`, `outputs/memorial_v1.docx`

**Step 1:** Notebook cells executing, in order:
1. Load `fixtures/moots/nlsiu_2024.pdf` → `extract_pdf_text`.
2. `extract_issues(text)` — print issues, sanity-check.
3. For each issue: `research_for_issue(issue)` — print top 5 cases.
4. For each issue: `generate_arguments(issue, cases)` — print IRAC blocks.
5. `validate_citations(all_arguments, all_cases)` — MUST pass with zero hallucinations.
6. `build_memorial(issues, arguments, cases)` → `outputs/memorial_v1.docx`.

**Step 2:** Open the DOCX. Read it critically.

**Step 3:** Send to law-student reviewer. Grade 1–5 on: issue extraction, case relevance, citation grounding, argument quality.

**Step 4:** **SUCCESS GATE CHECKPOINT.** If all scores ≥3 and zero hallucinations → proceed to Task 15. If not → iterate on prompts, re-run. Do not proceed to Week 2 until this passes. The whole product hinges on this output being usable.

**Step 5:** Commit notebook (without sensitive data).

---

## Task 15: Expand curation to 1,000 cases

Same as Task 2 but larger. Save as `data/seed_cases_v2.csv`. Use published "Top 100 Landmark Judgments" lists (EBC, Bar & Bench, SCC compendiums) as starting points. Law-student review mandatory.

**Commit:**
```bash
git add data/seed_cases_v2.csv
git commit -m "data: 1000-case curated corpus"
```

---

## Task 16: Harden ingestion pipeline

**Files:**
- Modify: `scripts/scrape_seed.py`, `scripts/ingest_corpus.py`

**Step 1:** Rewrite scraper: rate-limit (max 0.5 req/s), resumable via a JSON manifest, parallelizable at max 3 concurrent workers. Log failures per URL for manual retry.

**Step 2:** Make ingestion re-entrant: if script is killed midway, it resumes from last committed vector batch.

**Step 3:** Run full scrape (~1 hour) then full ingest (~30 min).

**Step 4:** Commit.

---

## Task 17: Evaluation harness

**Files:**
- Create: `evals/problems/*.pdf` (10 past moots), `evals/grade.py`, `evals/rubric.md`, `evals/results_YYYY-MM-DD.csv`

**Step 1:** Collect 10 past moot problems (varied: constitutional, criminal, contract, IPR, tax).

**Step 2:** `evals/rubric.md` defines grading scale 1–5 on each of: issue extraction, case relevance, citation grounding, argument quality. Plus hard fail: any hallucinated citation → overall fail regardless of other scores.

**Step 3:** `evals/grade.py` runs the pipeline on all 10, generates DOCXs to `evals/outputs/`, emits a CSV row per problem with auto-computable metrics (citation validity, # issues found, avg case rerank score). Human scores added manually by reviewer.

**Step 4:** Run: `uv run python -m evals.grade`. Get reviewer to fill human columns.

**Step 5:** Commit script + rubric + anonymized results.

---

## Task 18: CLI deliverable

**Files:**
- Create: `src/lexai/cli.py`
- Modify: `pyproject.toml` (entrypoint)

**Step 1: Write test** — invoking CLI with `--problem path/to.pdf --out path/to.docx` produces a valid DOCX.

**Step 2: Implement** with `argparse` or `click`. Single command: `lexai pipeline run --problem X.pdf --out memorial.docx`. Streams progress to stderr.

**Step 3:** Register entrypoint in `pyproject.toml`:

```toml
[project.scripts]
lexai = "lexai.cli:main"
```

**Step 4:** Verify: `uv run lexai pipeline run --problem fixtures/moots/sample.pdf --out /tmp/out.docx` works.

**Step 5:** Commit.

---

## Task 19: Phase 1 success gate review

**Files:**
- Create: `docs/phase1-results.md`

**Step 1:** Run CLI on all 10 eval problems. Collect reviewer scores.

**Step 2:** Write `phase1-results.md`: per-problem scores, aggregate stats, sample outputs, observed failure modes, decision.

**Step 3: Decision checkpoint.**
- **GO:** All 10 problems pass gate (≥3/5 each axis, zero hallucinations). Phase 2 planning begins — invoke writing-plans again for the web app plan.
- **NO-GO:** Scores below threshold or hallucinations present. Do not proceed. Iterate on prompts (Tasks 9–12), expand corpus, or reconsider approach. Re-run eval.

**Step 4:** Commit.

```bash
git add docs/phase1-results.md
git commit -m "docs: phase 1 eval results and go/no-go decision"
```

---

## Post-Phase 1

If gate passes, re-invoke the brainstorming → writing-plans flow to produce the Phase 2 implementation plan (FastAPI backend, Supabase schema, Next.js scaffold). Do NOT start Phase 2 until the gate passes. The design doc at `docs/plans/2026-04-13-lexai-design.md` is the reference.

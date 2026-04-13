# LexAI

AI-powered legal research and drafting platform for Indian law students and practising lawyers.

**Status:** Phase 1 (de-risk) — proving the moot-court RAG pipeline in a Python CLI before building the web app.

See [docs/plans/2026-04-13-lexai-master-plan.md](docs/plans/2026-04-13-lexai-master-plan.md) for the plain-English overview, [docs/plans/2026-04-13-lexai-design.md](docs/plans/2026-04-13-lexai-design.md) for architecture, and [docs/plans/2026-04-13-lexai-phase1-derisk.md](docs/plans/2026-04-13-lexai-phase1-derisk.md) for the current implementation plan.

## Setup

1. Install [uv](https://docs.astral.sh/uv/): `pip install uv`
2. `cp .env.example .env` and fill in keys (Gemini, Voyage AI, Pinecone — all free tiers)
3. `uv sync`
4. `uv run pytest`

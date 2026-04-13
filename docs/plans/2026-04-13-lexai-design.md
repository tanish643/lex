# LexAI — Design Document

**Date:** 2026-04-13
**Author:** Tanish (solo builder)
**Status:** Approved — ready for implementation planning
**Source brief:** LexAI Technical Product Brief v1.0

---

## 1. Product Thesis

LexAI is an AI-powered legal research and drafting platform for Indian law students and practicing lawyers. The flagship differentiator is the **Moot Court Module**: an end-to-end pipeline that ingests a moot problem PDF and produces a grounded, well-cited memorial draft. Three secondary modules (Legal Research, Document Drafting, Exam Prep) round out the offering, but the moot workflow is the wedge.

The product only matters if one question is answered yes: *does the moot court RAG pipeline produce a memorial good enough that a law student will pay ₹299/mo for it?* Everything downstream (auth, billing, templates, mobile) is commodity. The build plan is designed around proving this question as early and cheaply as possible.

## 2. Build Strategy — Risk-First Vertical Slice

Traditional layer-by-layer construction (auth → DB → API → AI last) delays the existential question to week 5. For a solo builder, that is unacceptable risk. The plan is instead a risk-first vertical slice:

1. **De-risk (Weeks 1–2)** — Prove the moot pipeline works in a Python notebook. No UI, no DB, no auth.
2. **Build (Weeks 3–7)** — Wrap the proven pipeline in a FastAPI backend and Next.js frontend, with Supabase for DB/auth/storage and Razorpay for billing.
3. **Round out (Weeks 8–10)** — Legal Research module (reuses pipeline), 3 drafting templates, polish, staging deploy.

Realistic solo timeline is **12–16 weeks**, not the 8–10 in the original brief.

## 3. Phase 1 — De-risk (Weeks 1–2)

### Week 1 — RAG Spike

Jupyter notebook. Goal: end-to-end pipeline on one real past moot problem, producing a memorial with grounded citations.

- **Seed corpus:** 100 landmark cases, curated. ~40 constitutional (Art 14/19/21), ~30 criminal (IPC, NDPS), ~30 contract/commercial. Sourced from Indian Kanoon.
- **Chunking:** 500-token chunks, 50-token overlap, paragraph-preserving. Metadata: `case_title, citation, court, year, bench, chunk_index, source_url`.
- **Embeddings:** Voyage AI `voyage-law-2` (legal-domain). Fallback: OpenAI `text-embedding-3-large`.
- **Vector store:** Pinecone serverless, index `lex-cases-v1`.
- **Three prompts:**
  - Issue extraction — moot problem → JSON of `{issue, area_of_law, statutes, articles}`
  - Case re-ranking — top-15 retrieved → LLM picks top-5 with reasoning
  - Argument draft — issues + selected cases → IRAC-structured petitioner & respondent args, citations strictly from provided list
- **Citation validator:** regex-extract every citation in generated output; verify each against Pinecone metadata. Fail loudly on any hallucinated citation.
- **Memorial assembly:** `python-docx` stitches sections into DOCX.
- **Success gate:** a law student reviewing the output says "I'd use this as a starting point and edit." If not, iterate on the spike — do not proceed.

### Week 2 — Scale and harden

- Expand curation to 1,000 cases (with law-student help).
- Rewrite ingestion as resumable, idempotent, rate-limited script (not notebook).
- Evaluation harness: 10 past moot problems graded 1–5 on issue extraction, case relevance, citation grounding, argument quality. Becomes regression test.
- **Deliverable:** `python -m lexai.pipeline run --problem path/to/moot.pdf` CLI that outputs memorial DOCX.

## 4. Phase 2 — Build (Weeks 3–7)

### Week 3 — Backend skeleton
- FastAPI + uv. Supabase project (Postgres + Auth + Storage).
- Schema: `users, moot_projects, saved_cases, documents, usage_counters, subscriptions, memorial_versions`.
- arq (Redis-backed queue) wrapping pipeline as four async jobs: `analyse_issues`, `research_cases`, `generate_arguments`, `generate_memorial`.

### Week 4 — Streaming + file handling
- SSE for memorial-generation progress (one-way; sufficient, simpler than WebSockets).
- PDF upload → Supabase Storage → `pypdf` extract → enqueue `analyse_issues`.
- DOCX via `python-docx`; PDF via headless LibreOffice conversion. (Not Puppeteer.)

### Week 5 — Frontend scaffold + core moot flow
- Next.js 14 App Router + TS + shadcn/ui + Tailwind.
- Screens: Auth (Supabase Auth UI) → Dashboard → New project → Project detail tabs (Issues · Research · Arguments · Memorial).
- Tanstack Query for server state; Supabase JS client for reads; FastAPI only for AI-triggering writes.

### Week 6 — Memorial editor
- **TipTap** (resolves Open Q #4).
- Single-user edit only; **real-time collab deferred** (resolves Open Q #5).
- Save on blur + explicit button. Version rows in `memorial_versions`.
- Export → `/memorial/:id/export?format=docx|pdf`.

### Week 7 — Auth enforcement + billing
- Razorpay Subscriptions (recurring, not one-time).
- `usage_counters` with monthly reset.
- `check_quota(user, action)` middleware on every AI endpoint → 402 if exceeded.
- Plan gates enforced server-side per brief §8.
- Razorpay webhook: update `subscription_plan` and `subscription_expires_at` on `subscription.activated|charged|cancelled`.

## 5. Phase 3 — Round out (Weeks 8–10)

### Week 8 — Legal Research module
Reuses 95% of the moot pipeline. Same embed → retrieve → re-rank, but output is synthesised answer + case cards. ~2 days of work. Saved cases CRUD.

### Week 9 — Drafting module (minimal)
Three templates only: legal notice, bail application, NDA. Each = JSON schema + prompt template. Form auto-generated from schema (react-hook-form + zod). Claude generates draft → TipTap → export. **Clause library deferred.**

### Week 10 — Polish + staging deploy
Empty states, loading skeletons, error boundaries, LLM-failure retry. Deploy: Vercel (FE), Railway (BE + arq worker + Redis), Pinecone serverless, Supabase cloud. Sentry + PostHog from user-zero.

## 6. Explicitly Deferred (post-MVP)

Mobile app · exam prep module · clause library · full drafting template set (beyond 3) · team collaboration · real-time memorial editing · Hindi/regional languages · institution licensing · API access.

## 7. Final Tech Stack

| Layer | Pick | Delta from brief |
|---|---|---|
| Frontend | Next.js 14 App Router + TS + shadcn/ui + Tailwind | — |
| Backend | FastAPI (Python) | was Node/Express option — Python chosen to unify with RAG |
| LLM | Claude Sonnet 4.6 + Claude Haiku 4.5 (cheap sub-tasks) | specific model picks |
| Embeddings | Voyage `voyage-law-2` | was OpenAI Ada |
| Vector DB | Pinecone serverless | — |
| DB + Auth + Storage | Supabase (single vendor) | was Postgres + Auth0 + S3 separately |
| Job queue | arq + Redis | was BullMQ (Node) |
| Editor | TipTap | resolves Open Q #4 |
| Payments | Razorpay Subscriptions | — |
| Deploy | Vercel (FE) + Railway (BE/worker/Redis) | — |
| Observability | Sentry + PostHog | added — not in brief |

## 8. Open Questions — Resolved

1. **Legal DB source** → hybrid: 1,000-case seed via Indian Kanoon scrape; licensed backup plan by Month 3.
2. **In-house vs managed RAG** → in-house; LlamaIndex as library is fine, but retrieval logic stays owned (citation quality is the product).
3. **Month-1 volume** → assume 50 beta users × 2 problems = 100 generations; queue sized for 5 concurrent jobs.
4. **Editor** → TipTap.
5. **Real-time collab** → deferred.

## 9. Top Risks (ranked)

1. **Citation hallucination** — mitigated by post-generation regex validator against Pinecone metadata; fail loudly.
2. **Issue extraction misses key legal angle** — mitigated by always showing extracted issues to user before research runs; never autopilot.
3. **Memorial quality ceiling** — position as *research accelerator / first draft*, not tournament-winner replacement.
4. **Indian Kanoon scrape fragility / ToS** — need licensed backup plan by Month 3.
5. **Solo burnout** — 12–16 week timeline, not 10.

## 10. Success Criteria

- **Phase 1 gate:** law-student reviewer rates the notebook-generated memorial ≥3/5 on each of {issue extraction, case relevance, citation grounding, argument quality}. Pipeline passes citation validator with zero hallucinations on 10-problem test set.
- **Phase 2 gate:** end-to-end flow works in staging — upload PDF, see issues, approve research, generate memorial, edit, export — for a fresh user account.
- **Phase 3 gate:** 5 paying law-student users complete a moot project end-to-end and renew their subscription after month 1.

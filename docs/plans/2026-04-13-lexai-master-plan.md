# LexAI — Master Plan (A to Z)

**For:** Tanish (solo founder + builder)
**Written:** 2026-04-13
**Companion docs:** `2026-04-13-lexai-design.md` (design), `2026-04-13-lexai-phase1-derisk.md` (Phase 1 tasks)

This is the plain-English version. Read this end-to-end. The other two docs are reference material you dip into when you need detail.

---

## Part 1 — What You're Actually Building

**Elevator pitch:** LexAI is a website that takes a law student's moot court problem (PDF) and, in under a minute, spits out a full first-draft memorial — with real Indian case citations, arguments for both sides, and downloadable as Word/PDF.

**Who pays you:**
1. **Law students** (₹299/mo) — mainly NLUs, during moot season.
2. **Practicing lawyers** (₹999/mo) — solo and small firm, for research and drafting.

**Why LexAI wins:** Nobody in India has built a moot-court-specific AI workflow. ChatGPT hallucinates Indian case citations. SCC Online is expensive and has no AI layer. You're the only product doing this end-to-end for the Indian jurisdiction.

**Why you might fail:** The AI has to produce memorials good enough that a smart law student is willing to pay. If the output is garbage, price doesn't matter. **Everything in this plan is designed around proving that one thing first, before investing in anything else.**

---

## Part 2 — The Strategy in One Sentence

**Prove the AI works before building the app.**

Most founders build the app first (login, dashboard, database, payments) and plug in the AI last. That's stupid for you, because if the AI doesn't work, you've wasted 5 weeks. Instead, you spend Weeks 1–2 with just a Python notebook — no website, no database, no login — and you generate memorials to see if they're good.

Only when a real law student looks at a generated memorial and says "yeah, I'd use this as my starting point" do you build the website around it.

This is called a **risk-first vertical slice**. It's the most important decision in this plan.

---

## Part 3 — The Whole Journey (Week by Week)

Realistic timeline: **12–16 weeks**, not 10. Plan for life to happen.

### Weeks 1–2 — Prove the AI Works (The Spike)

You're writing Python in a notebook. No website yet.

**Week 1 — The tiny experiment**
- Gather 100 landmark Indian cases (constitution, criminal, contract). Get a law-student friend to help pick them.
- Scrape each case's text from Indian Kanoon.
- Chop each case into 500-word chunks. Turn each chunk into a math vector using Voyage AI's legal embeddings model. Dump the vectors into Pinecone (a database built for finding similar vectors).
- Take one real past moot problem (NLSIU or Jessup — publicly available).
- Run it through three AI calls:
  1. **Claude reads the problem** and lists the legal issues (e.g., "Article 21 violation," "Section 302 IPC applicability").
  2. For each issue, **search Pinecone** for the 15 most relevant case chunks, then **Claude picks the best 5**.
  3. **Claude writes arguments** for both sides — petitioner and respondent — citing only those 5 cases.
- Stitch it all into a Word doc.
- **Look at the output.** Send it to a law student. Ask: "Would you use this?"

If they say yes → continue. If they say no → iterate on the prompts and the case list for another week. Do not touch a website until the answer is yes.

**Week 2 — Make it real**
- Expand to 1,000 cases. Same process, more careful curation.
- Write a proper script (not a notebook) that can re-run ingestion end-to-end.
- Test the pipeline on 10 different past moot problems. Grade each output on a 1–5 scale.
- Build a command-line tool: `lexai pipeline run --problem X.pdf --out memorial.docx`. This is your "proof".

**End-of-Phase gate:** 10 problems, all graded ≥3/5, zero fake citations. Only then do you proceed.

### Weeks 3–7 — Build the Actual Product

Now you wrap the working pipeline in a real app.

**Week 3 — Backend plumbing**
- Create a FastAPI backend (Python, because your AI code is already Python — one language, less context switching).
- Set up Supabase. One signup, and you get a Postgres database, user login, and file storage all in one place. Saves you from configuring three things.
- Design the database: users, projects, saved cases, documents, usage counters, subscriptions.
- Add a job queue (arq + Redis) — because generating a memorial takes 30-60 seconds, you can't make the user's browser hang. Queue it, stream progress.

**Week 4 — File handling and streaming**
- PDF upload → extract text → kick off issue-extraction job.
- Live progress updates so the user sees "Analyzing issues… researching cases… drafting petitioner arguments…" in real time. Uses Server-Sent Events (SSE), simpler than WebSockets.
- DOCX export working. PDF export via LibreOffice conversion.

**Week 5 — The frontend**
- Next.js + Tailwind + shadcn/ui (pre-built components, don't reinvent design).
- Five screens: login, dashboard (project list), new project (upload), project detail (tabs for Issues, Research, Arguments, Memorial), settings.
- Wire each screen to the backend.

**Week 6 — The memorial editor**
- Plug in TipTap (a rich text editor component). Load the AI-generated memorial into it. Let the user edit inline.
- Save every version to the database — students want undo history.
- Export button works from the editor.

**Week 7 — Login and payments**
- Supabase handles login (email/password + Google). Barely any code.
- Razorpay Subscriptions for recurring billing (UPI + cards).
- Usage limits: free users get 1 project, Student Pro gets unlimited. Every AI call checks this limit in the backend — never trust the frontend for limits.
- Razorpay webhook updates the user's plan when they pay.

**End-of-Phase gate:** A fresh user can sign up, upload a moot problem, get a memorial, edit it, export it, pay ₹299, and do it all on the live staging site.

### Weeks 8–10 — Round Out and Ship

**Week 8 — Legal research module**
- Same pipeline you built in Weeks 1–2, new UI. User types "what is the law on anticipatory bail in NDPS cases?" → gets a synthesized answer + case cards.
- Should take 2 days because 95% of the code already exists.
- Saved cases library — simple CRUD.

**Week 9 — Document drafting (minimal)**
- Three templates only: legal notice, bail application, NDA.
- User fills a form → Claude generates a draft → TipTap → export.
- Full template library (20+) is explicitly a post-launch feature.

**Week 10 — Polish and launch**
- Loading states, empty states, error screens. Every button that can fail gets a retry.
- Deploy: Vercel (frontend), Railway (backend + job worker + Redis), Pinecone (vectors), Supabase (database).
- Install Sentry (so you see errors in production) and PostHog (so you see what users do).
- Invite 5–10 law-student friends. Beta launch.

### Weeks 11–12 — Buffer (plan for it)

Solo dev + real life = things slip. These weeks exist. Use them for whatever broke, for the polish you skipped, for the user feedback that came in during beta.

---

## Part 4 — What It Costs

### Money

| Item | Cost |
|---|---|
| Anthropic API (Claude) | ~$0.10–0.30 per memorial. Maybe $30/mo dev + $100–500/mo once users come. |
| Voyage embeddings | ~$5 one-time for 1,000 cases. Cheap. |
| Pinecone serverless | Free tier covers 1,000 cases easily. Maybe $0–20/mo. |
| Supabase | Free tier covers you to ~500 users. Then $25/mo. |
| Railway | ~$5–10/mo at start. |
| Vercel | Free (hobby plan). |
| Razorpay | 2% of transactions. Zero when idle. |
| Domain | ₹800/year. |
| **Total at zero users** | **~$0–20/mo** |
| **Total at 100 paying users** | **~₹15–25k/mo** ($200-300), revenue ~₹30k, margin thin but positive |

You don't need investment to reach 100 paying users. You do need a credit card and ₹5–10k/mo in runway.

### Time

~30 hrs/week × 14 weeks = ~420 hours. If you work 20 hrs/week, double it to 28 weeks. Be honest with yourself about your real availability.

---

## Part 5 — The Five Things That Can Kill This Project

1. **Fake citations.** The AI makes up case names that sound real. You have one defense: a validator script that checks every citation in the output against your Pinecone database. If a citation isn't in the database, the pipeline throws an error. Non-negotiable.

2. **Shallow issue extraction.** The AI misses a key legal angle in a tricky moot problem. Defense: always show the extracted issues to the user BEFORE running research. Let them add or remove issues. Never autopilot the whole pipeline — keep the human in the loop.

3. **"Decent but not winning" memorials.** Your output may be good, not great. That's fine. Position it as a "research accelerator and first draft," not as a replacement for the student's own work. The messaging matters.

4. **Indian Kanoon scraping.** Their Terms of Service are grey. It's fine for MVP but by Month 3 you should have a licensed backup plan (talk to Manupatra / SCC Online about startup licensing, even if you can't afford it yet — know your options).

5. **Solo burnout.** You are one person. Every week, ask: am I ahead of schedule, on schedule, or behind? If behind 2 weeks in a row, something in your plan is wrong — the scope, the timeline, or your hours. Re-plan, don't push through.

---

## Part 6 — Decisions You Own (Not Me)

These are things nobody can decide for you:

1. **The 100-case seed list.** I can suggest categories, but the actual cases matter. Get a law-student friend to curate. Spend a real day on this.
2. **The pricing.** ₹299 / ₹999 is what your brief says. Validate by asking 10 law students what they'd pay. The answer might be ₹199, or ₹499.
3. **The beta users.** Who are your first 10? Reach out to them in Week 8, not Week 10, so they're warm when staging is live.
4. **The moot problem you test on.** Pick one that you personally understand the law for — so you can judge whether the AI output is good or not.
5. **When to bring in a designer.** The shadcn/ui defaults are fine for beta but not for paid users. Budget ₹20–40k for a freelance designer around Week 9 if you can.

---

## Part 7 — What "Done" Looks Like

**End of Week 2 — "The AI works."** One command produces a memorial that a law student will actually use.

**End of Week 7 — "The product works."** A stranger can sign up, pay, and generate a memorial without you helping them.

**End of Week 10 — "Shipped."** 5–10 beta users have used the product. You have analytics. You have a waitlist. You know what's broken.

**Month 4–6 — "Traction."** 50–100 paying users. Revenue ₹15–30k/mo. You're learning which module is actually loved.

**Month 6+ — "Scale."** Now, and only now, do you start thinking about mobile apps, exam prep, full template libraries, Hindi, institution sales. Everything deferred in this plan gets its own plan.

---

## Part 8 — Your Immediate Next 48 Hours

Forget the 10-week plan. Do these seven things first:

1. Sign up for Anthropic Console, Voyage AI, Pinecone. Put keys somewhere safe.
2. Download 3 past moot problem PDFs (NLSIU, Jessup, NALSAR — all public).
3. Message one law-student friend: "I'm building something — will you help me curate 100 cases and review AI outputs? 2–3 hours of your time spread over 2 weeks."
4. Install `uv` on your machine. Clone the empty repo at `c:/Users/Tanish/Lex`.
5. Execute Task 1 of the Phase 1 plan (project scaffold). ~30 minutes.
6. Execute Task 2 of the Phase 1 plan (start curating the case list). ~2 hours.
7. Go to bed.

Then Week 1 begins.

---

## Part 9 — How You and I Work Together

I'm your pair. I'll:
- Write code task-by-task from the Phase 1 plan with you in the loop.
- Review every output with you before moving on.
- Push back when you want to skip steps I think are important (especially the success gate at end of Week 2).
- Tell you honestly if a week's work isn't meeting the quality bar.

You'll:
- Make the non-code decisions (case list, which moot to test on, pricing, when to ship).
- Be the law-domain check on output quality — I can't judge whether a legal argument is sound, only whether it's well-formed.
- Keep API keys and money stuff; I never touch those.
- Tell me when to slow down, change direction, or re-plan.

When you're ready to start coding: say "execute Task 1" and we begin.

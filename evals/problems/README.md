# `evals/problems/` — moot problem PDFs for evaluation

Drop 10 past moot problem PDFs here. PDFs are **gitignored** (large + distribution terms).

The Phase 1 success gate requires the pipeline to pass all 10 (citation grounding + ≥3/5 on each axis). Vary the areas of law so one overfit-to-corpus win doesn't hide a general weakness:

- 3 constitutional (rights, federalism, reservations)
- 3 competition / commercial (antitrust, contract, commercial disputes)
- 2 criminal (IPC landmarks, NDPS, CrPC procedure)
- 2 other (IPR, tax, family — whichever publicly-available moots are handy)

Public moot archives with past problems:
- NLSIU Bangalore — regional and international rounds
- NALSAR Hyderabad — thematic moots (CCI, KKV, tax)
- NLIU Bhopal, NUJS Kolkata, NLU Delhi — annual moots
- Jessup, Vis, Manfred Lachs — international

After dropping PDFs, run:
    uv run python -m evals.grade

Results go to `evals/results_YYYY-MM-DD.csv`. Forward that CSV to the law-student reviewer with `evals/rubric.md`.

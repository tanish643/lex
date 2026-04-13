# LexAI Phase 1 Evaluation Rubric

**Purpose:** Determine whether the RAG pipeline produces memorials good enough to pass the Phase 1 success gate before committing to Phase 2 (web app build).

## Scoring

Each memorial is scored on four axes, **1 to 5**, by a law-student reviewer:

| Axis | 1 (fail) | 3 (gate) | 5 (excellent) |
|---|---|---|---|
| **Issue extraction** | Missed ≥50% of key legal issues; irrelevant issues included | Caught all CAT-L issues; may have missed a secondary issue | Caught every issue CAT-L identified plus at least one legitimate additional angle |
| **Case relevance** | Cases cited have no genuine connection to the issue | Most cases are on-point for the issue; one or two are weak analogies | Every cited case directly supports the proposition it's attached to; the strongest available precedents were surfaced |
| **Citation grounding** | Any fabricated citation → automatic overall failure | All citations verifiable and from the provided corpus | All citations verified AND applied in a way that would survive a bench question |
| **Argument quality** | Arguments are surface-level; IRAC structure is sloppy; no counter-arguments anticipated | Arguments follow IRAC cleanly; cover the core proposition; a law student would use this as a starting draft | Arguments are persuasive, handle likely judicial objections, and could plausibly be delivered in oral rounds with minor edits |

## Hard fail

**Any hallucinated citation triggers automatic failure regardless of other scores.** This is non-negotiable. Hallucinated citations in a moot memorial are unrecoverable in front of a judge.

The automated validator (`lexai/pipeline/validate.py`) catches these before human review, but the reviewer should also spot-check: pick 3 citations at random and verify they exist and say what the memorial claims they say.

## Gate thresholds

Phase 1 passes only if:

- **10 of 10** evaluation problems pass citation validation with zero hallucinations.
- **≥3/5 average** on each of the four axes across the 10 problems.
- **At least 7 of 10** individual problems score ≥3/5 on every axis.

A single outlier problem is acceptable (maybe the corpus is weak in that area). Systematic weakness is not.

## What a passing memorial looks like

A law student, reading the AI-generated memorial, says: "Yes, I'd use this as the starting point for my own memorial and edit it." They would NOT say "this is good enough to submit as-is" — we are not building a tournament-winner replacement. We are building a research accelerator.

## Reviewer protocol

1. Read the moot problem PDF first. Note what you think the issues are before looking at the memorial.
2. Open the generated memorial DOCX.
3. Score axes 1 and 4 based on the memorial alone.
4. Pick 3 citations at random. Open Indian Kanoon, verify each exists and check whether the memorial's characterisation of its holding is accurate. Score axis 3.
5. For each cited case, judge whether a better precedent likely exists in Indian law for the proposition. Score axis 2.
6. Record scores in `evals/results_YYYY-MM-DD.csv`.

Do not look at the AI's issue extraction before forming your own opinion (step 1). Anchoring bias will inflate the issue-extraction score.

"""Eval harness — run the pipeline on every problem in evals/problems/.

Produces:
  - evals/outputs/{problem_stem}.docx  — generated memorial
  - evals/results_{YYYY-MM-DD}.csv    — one row per problem with
      auto-computable metrics (citations used, hallucinations detected,
      issue count, avg rerank score) plus empty columns the human
      reviewer fills in (issue_extraction, case_relevance,
      citation_grounding, argument_quality — each 1-5 per rubric.md).

Usage:
    uv run python -m evals.grade
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from lexai.pipeline.orchestrator import run_pipeline
from lexai.pipeline.validate import HallucinationError

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROBLEMS_DIR = ROOT / "evals" / "problems"
OUTPUTS_DIR = ROOT / "evals" / "outputs"
RESULTS_PATH = ROOT / "evals" / f"results_{date.today().isoformat()}.csv"

CSV_FIELDS = [
    "problem",
    "status",
    "issues_found",
    "citations_used",
    "hallucinations_auto",
    "avg_cases_per_issue",
    # human columns — filled in by reviewer following rubric.md
    "issue_extraction_1to5",
    "case_relevance_1to5",
    "citation_grounding_1to5",
    "argument_quality_1to5",
    "reviewer_notes",
    "memorial_path",
]


def main() -> int:
    PROBLEMS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    problems = sorted(PROBLEMS_DIR.glob("*.pdf"))
    if not problems:
        print(f"ERROR: no PDFs in {PROBLEMS_DIR}", file=sys.stderr)
        print("Drop 10 past moot problem PDFs into that folder and re-run.")
        return 1

    rows: list[dict] = []
    for problem in problems:
        out = OUTPUTS_DIR / f"{problem.stem}.docx"
        print(f"\n=== {problem.name} ===")

        row = {k: "" for k in CSV_FIELDS}
        row["problem"] = problem.name
        row["memorial_path"] = str(out)

        try:
            result = run_pipeline(
                problem,
                out,
                moot_title=f"Evaluation: {problem.stem}",
                strict_citations=True,
            )
        except HallucinationError as e:
            row["status"] = "HALLUCINATED"
            row["reviewer_notes"] = str(e)[:200]
            rows.append(row)
            continue
        except Exception as e:  # noqa: BLE001
            row["status"] = f"ERROR:{type(e).__name__}"
            row["reviewer_notes"] = str(e)[:200]
            rows.append(row)
            continue

        row["status"] = "OK"
        row["issues_found"] = len(result.issues)
        row["citations_used"] = result.total_citations_used
        row["hallucinations_auto"] = result.total_hallucinations
        total_cases = sum(len(cs) for cs in result.cases_per_issue)
        row["avg_cases_per_issue"] = (
            f"{total_cases / len(result.issues):.2f}" if result.issues else "0"
        )
        rows.append(row)

    with RESULTS_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} result rows to {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""LexAI CLI — `lexai pipeline run --problem X.pdf --out memorial.docx`.

The deliverable for Phase 1 Task 18. Streams progress to stderr so
stdout stays clean for any future scripting use. Exit codes:
  0  - memorial generated, all citations verified
  1  - hallucinated citation detected (strict mode)
  2  - pipeline error (missing PDF, API failure, etc.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from lexai.pipeline.orchestrator import run_pipeline
from lexai.pipeline.validate import HallucinationError


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _cmd_pipeline_run(args: argparse.Namespace) -> int:
    problem = Path(args.problem).resolve()
    out = Path(args.out).resolve()
    if not problem.exists():
        print(f"ERROR: problem PDF not found: {problem}", file=sys.stderr)
        return 2

    try:
        result = run_pipeline(
            problem,
            out,
            moot_title=args.title,
            tribunal=args.tribunal,
            case_number=args.case_number,
            strict_citations=not args.allow_hallucinations,
            progress=_progress,
        )
    except HallucinationError as e:
        print(f"\nFAILED (hallucinated citation): {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"\nFAILED (pipeline error): {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    _progress("")
    _progress(
        f"DONE. {len(result.issues)} issues, "
        f"{result.total_citations_used} citations used, "
        f"{result.total_hallucinations} hallucinations."
    )
    print(str(result.memorial_path))  # stdout: just the path, scriptable
    return 0


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="lexai")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pipeline = sub.add_parser("pipeline", help="run the memorial pipeline")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_cmd", required=True)

    run = pipeline_sub.add_parser("run", help="produce a memorial from a moot PDF")
    run.add_argument("--problem", required=True, help="path to moot problem PDF")
    run.add_argument("--out", required=True, help="output DOCX path")
    run.add_argument(
        "--title", default="LexAI Generated Memorial", help="moot title on cover"
    )
    run.add_argument(
        "--tribunal",
        default="Competition Appellate Tribunal",
        help="tribunal name on cover",
    )
    run.add_argument(
        "--case-number", default="Appeal No. __ of ____", help="case number on cover"
    )
    run.add_argument(
        "--allow-hallucinations",
        action="store_true",
        help="do not fail on hallucinated citations (for debugging only)",
    )
    run.set_defaults(func=_cmd_pipeline_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

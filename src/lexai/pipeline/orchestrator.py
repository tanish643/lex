"""End-to-end pipeline orchestrator.

run_pipeline(problem_pdf) -> memorial DOCX.

Flow:
  1. Extract PDF text.
  2. Extract issues (Gemini).
  3. For each issue: retrieve + rerank (Voyage + Pinecone + Gemini).
  4. For each issue: generate arguments (Gemini), strict citation validate.
  5. Assemble DOCX memorial.

The strict citation validator is non-negotiable — the pipeline raises
HallucinationError if any argument cites a case not in its research
set. The CLI catches this and fails with a non-zero exit code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from lexai.ingest.pdf import extract_pdf_text
from lexai.pipeline.arguments import IssueArguments, generate_arguments
from lexai.pipeline.issues import Issue, extract_issues
from lexai.pipeline.memorial import MemorialInput, build_memorial
from lexai.pipeline.research import RankedCase, research_for_issue
from lexai.pipeline.validate import (
    HallucinationError,
    ValidationReport,
    validate_arguments,
)
from lexai.rag.vectorstore import get_index


@dataclass
class PipelineResult:
    memorial_path: Path
    issues: list[Issue]
    arguments_per_issue: list[IssueArguments]
    cases_per_issue: list[list[RankedCase]]
    validation_reports: list[ValidationReport] = field(default_factory=list)

    @property
    def total_citations_used(self) -> int:
        return sum(len(r.used_citations) for r in self.validation_reports)

    @property
    def total_hallucinations(self) -> int:
        return sum(len(r.hallucinated) for r in self.validation_reports)


def run_pipeline(
    problem_pdf: Path,
    out_path: Path,
    *,
    moot_title: str = "LexAI Generated Memorial",
    tribunal: str = "Competition Appellate Tribunal",
    case_number: str = "Appeal No. __ of ____",
    strict_citations: bool = True,
    progress: Callable[[str], None] = print,
) -> PipelineResult:
    progress(f"[1/5] Extracting text from {problem_pdf.name} ...")
    moot_text = extract_pdf_text(problem_pdf)
    progress(f"       {len(moot_text):,} chars extracted")

    progress("[2/5] Extracting legal issues with Gemini ...")
    issues = extract_issues(moot_text)
    progress(f"       {len(issues)} issues found")
    for i, issue in enumerate(issues, start=1):
        progress(f"         {i}. [{issue.area_of_law}] {issue.issue_title}")

    index = get_index()

    progress("[3/5] Researching cases for each issue ...")
    cases_per_issue: list[list[RankedCase]] = []
    for i, issue in enumerate(issues, start=1):
        progress(f"       ({i}/{len(issues)}) {issue.issue_title[:70]}")
        ranked = research_for_issue(issue, index=index)
        progress(f"         -> {len(ranked)} cases selected")
        for c in ranked:
            progress(f"            - {c.citation} | {c.case_title[:60]}")
        cases_per_issue.append(ranked)

    progress("[4/5] Generating IRAC arguments per issue ...")
    arguments_per_issue: list[IssueArguments] = []
    validation_reports: list[ValidationReport] = []
    for i, (issue, cases) in enumerate(zip(issues, cases_per_issue), start=1):
        if not cases:
            progress(
                f"       ({i}/{len(issues)}) SKIPPED — no cases for issue "
                f"{issue.issue_title[:60]}"
            )
            arguments_per_issue.append(
                IssueArguments(petitioner_arguments=[], respondent_arguments=[])
            )
            validation_reports.append(
                ValidationReport(ok=True, allowed_count=0)
            )
            continue

        progress(f"       ({i}/{len(issues)}) drafting IRAC...")
        args = generate_arguments(issue, cases)
        report = validate_arguments(args, cases, strict=False)
        progress(f"         -> {report.summary()}")
        if strict_citations and not report.ok:
            raise HallucinationError(
                f"Issue {i}: {issue.issue_title}\n{report.summary()}"
            )
        arguments_per_issue.append(args)
        validation_reports.append(report)

    progress(f"[5/5] Assembling memorial -> {out_path} ...")
    mem_input = MemorialInput(
        moot_title=moot_title,
        tribunal=tribunal,
        case_number=case_number,
        issues=issues,
        arguments_per_issue=arguments_per_issue,
        cases_per_issue=cases_per_issue,
    )
    build_memorial(mem_input, out_path)
    progress(f"       DOCX written: {out_path.stat().st_size:,} bytes")

    return PipelineResult(
        memorial_path=out_path,
        issues=issues,
        arguments_per_issue=arguments_per_issue,
        cases_per_issue=cases_per_issue,
        validation_reports=validation_reports,
    )

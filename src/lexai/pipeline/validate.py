"""Citation validator — THE quality gate for Phase 1.

Extracts every Indian citation pattern from the generated arguments and
verifies each against the allowed case list. A single hallucinated
citation FAILS the whole pipeline — hallucinated citations in a moot
memorial are unrecoverable in front of a judge and a lethal product
flaw.

Citation formats recognised (non-exhaustive but covers 95% of SC/HC
reporting practice):
  - AIR {year} SC {num}              e.g. AIR 1978 SC 597
  - ({year}) {vol} SCC {num}         e.g. (2017) 8 SCC 47
  - {year} SCC OnLine {court} {num}  e.g. 2016 SCC OnLine Del 1951
  - {year} SCC OnLine {body}          e.g. 2023 SCC OnLine NCLAT
  - ({year}) ILR {vol} {pp} {num}    e.g. (1903) ILR 30 Cal 539

Matching is whitespace- and case-tolerant; LLMs sometimes emit odd
spacing. Strict structural comparison would false-positive too often.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lexai.pipeline.arguments import IssueArguments
from lexai.pipeline.research import RankedCase


class HallucinationError(RuntimeError):
    """Raised when strict=True and any citation is unverifiable."""


@dataclass
class ValidationReport:
    ok: bool
    used_citations: list[str] = field(default_factory=list)
    hallucinated: list[str] = field(default_factory=list)
    allowed_count: int = 0

    def summary(self) -> str:
        if self.ok:
            return (
                f"PASSED: {len(self.used_citations)} citations used, "
                f"all verified against {self.allowed_count} allowed cases"
            )
        return (
            f"FAILED: {len(self.hallucinated)} hallucinated citation(s) — "
            f"{self.hallucinated}"
        )


# Citation extraction patterns. Each compiles to a regex that yields a
# canonical string form of the matched citation.
_PATTERNS = [
    # AIR 1978 SC 597
    re.compile(r"\bAIR\s+(\d{4})\s+([A-Za-z]{2,5})\s+(\d+)\b"),
    # (2017) 8 SCC 47  — also (2017) 10 SCC 1
    re.compile(r"\((\d{4})\)\s*(\d+)\s*SCC\s+(\d+)\b"),
    # 2016 SCC OnLine Del 1951
    re.compile(
        r"\b(\d{4})\s*SCC\s*OnLine\s+([A-Za-z]+)\s+(\d+)\b", re.IGNORECASE
    ),
    # 2023 SCC OnLine NCLAT  (no number suffix — tribunal orders)
    re.compile(r"\b(\d{4})\s*SCC\s*OnLine\s+(NCLAT|CompAT)\b", re.IGNORECASE),
    # (1903) ILR 30 Cal 539
    re.compile(r"\((\d{4})\)\s*ILR\s+(\d+)\s+([A-Za-z]+)\s+(\d+)\b"),
]


def extract_citations(text: str) -> list[str]:
    """Return citations found, de-duplicated, in their surface form."""
    found: list[str] = []
    seen: set[str] = set()
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            surface = m.group(0)
            key = normalize_citation(surface)
            if key in seen:
                continue
            seen.add(key)
            found.append(surface)
    return found


def normalize_citation(citation: str) -> str:
    """Canonical key for equality testing."""
    return re.sub(r"\s+", " ", citation.strip()).lower()


def _collect_text(args: IssueArguments) -> str:
    parts: list[str] = []
    for block in args.petitioner_arguments + args.respondent_arguments:
        parts.extend([block.issue, block.rule, block.application, block.conclusion])
    return "\n\n".join(parts)


def validate_arguments(
    args: IssueArguments,
    allowed_cases: list[RankedCase],
    *,
    strict: bool = False,
) -> ValidationReport:
    allowed_keys = {normalize_citation(c.citation) for c in allowed_cases}

    text = _collect_text(args)
    citations = extract_citations(text)

    used: list[str] = []
    hallucinated: list[str] = []
    for cite in citations:
        if normalize_citation(cite) in allowed_keys:
            used.append(cite)
        else:
            hallucinated.append(cite)

    report = ValidationReport(
        ok=not hallucinated,
        used_citations=used,
        hallucinated=hallucinated,
        allowed_count=len(allowed_cases),
    )
    if strict and hallucinated:
        raise HallucinationError(report.summary())
    return report

"""IRAC argument generation, grounded to a provided case list.

Given one Issue and the 5 re-ranked cases for it, produce one IRAC block
from each of petitioner and respondent perspectives. The output's
citations are constrained to the provided cases — Task 12's validator
checks this after the fact and fails the pipeline on any violation.

One issue at a time. Batching all issues into one call tempts the model
to mix up facts across issues, and also makes JSON parsing more fragile.
"""

from __future__ import annotations

import json
import os
import re
from typing import Callable

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from lexai.pipeline.issues import Issue
from lexai.pipeline.research import RankedCase
from lexai.prompts.arguments import ARGUMENT_GENERATION_SYSTEM

MODEL = "gemini-flash-lite-latest"
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class IRACBlock(BaseModel):
    issue: str
    rule: str
    application: str
    conclusion: str


class IssueArguments(BaseModel):
    petitioner_arguments: list[IRACBlock]
    respondent_arguments: list[IRACBlock]


def parse_arguments_json(raw: str) -> IssueArguments:
    cleaned = _FENCE_RE.sub("", raw).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found: {raw[:200]!r}")
    payload = cleaned[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if "petitioner_arguments" not in data or "respondent_arguments" not in data:
        raise ValueError("Missing petitioner_arguments or respondent_arguments key")
    return IssueArguments.model_validate(data)


def _format_cases_for_prompt(cases: list[RankedCase]) -> str:
    lines = ["ALLOWED CITATIONS (cite ONLY these):\n"]
    for c in cases:
        lines.append(
            f"- [{c.citation}] {c.case_title} ({c.year}, {c.court}). "
            f"Relevance: {c.reasoning}\n"
            f"  Key passage: {c.best_chunk_text[:600]}"
        )
    return "\n\n".join(lines)


@retry(
    wait=wait_exponential(multiplier=5, min=10, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _call_gemini(issue: Issue, cases: list[RankedCase]) -> IssueArguments:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    user_content = (
        f"ISSUE: {issue.issue_title}\n"
        f"AREA: {issue.area_of_law}\n"
        f"STATUTES: {', '.join(issue.relevant_statutes) or 'n/a'}\n"
        f"ARTICLES: {', '.join(issue.relevant_articles) or 'n/a'}\n"
        f"DESCRIPTION: {issue.description}\n\n"
        f"{_format_cases_for_prompt(cases)}"
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=ARGUMENT_GENERATION_SYSTEM,
            response_mime_type="application/json",
            temperature=0.4,
        ),
    )
    return parse_arguments_json(response.text or "")


def generate_arguments(
    issue: Issue,
    cases: list[RankedCase],
    *,
    llm: Callable[[Issue, list[RankedCase]], IssueArguments] = _call_gemini,
) -> IssueArguments:
    if not cases:
        raise ValueError(
            "Cannot generate arguments with zero supporting cases — "
            "either corpus is too small or retrieval returned nothing."
        )
    return llm(issue, cases)

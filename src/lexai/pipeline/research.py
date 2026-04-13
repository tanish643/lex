"""Retrieval + LLM re-ranking for a single issue.

Flow:
  1. Embed "issue_title + description" as a query vector.
  2. Pinecone top_k=15 on the chunk index.
  3. Dedupe by case_slug (best-scoring chunk per case) → 15 unique cases max.
  4. Send those 15 to Gemini with re-rank prompt → pick top 5.
  5. Drop any re-rank pick whose slug isn't in our candidates. Models
     occasionally hallucinate slugs, which would silently let
     fake-citation reasoning through to Task 11. This is the first
     defence of the citation-grounding invariant.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Callable

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from lexai.pipeline.issues import Issue
from lexai.prompts.rerank import RERANK_SYSTEM
from lexai.rag.embed import embed_texts
from lexai.rag.vectorstore import Match, query as pinecone_query

RERANK_MODEL = "gemini-flash-lite-latest"

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class RetrievedCase(BaseModel):
    case_slug: str
    case_title: str
    citation: str
    court: str
    year: int
    area_of_law: str
    best_score: float
    best_chunk_text: str


@dataclass(frozen=True)
class RankedCase:
    case_slug: str
    case_title: str
    citation: str
    court: str
    year: int
    area_of_law: str
    best_chunk_text: str
    reasoning: str


def deduplicate_by_case(matches: list[Match]) -> list[RetrievedCase]:
    """Collapse chunks to cases, keeping the highest-scoring chunk."""
    best: dict[str, Match] = {}
    for m in matches:
        prev = best.get(m.case_slug)
        if prev is None or m.score > prev.score:
            best[m.case_slug] = m

    cases = [
        RetrievedCase(
            case_slug=m.case_slug,
            case_title=m.case_title,
            citation=m.citation,
            court=m.court,
            year=m.year,
            area_of_law=m.area_of_law,
            best_score=m.score,
            best_chunk_text=m.text,
        )
        for m in best.values()
    ]
    cases.sort(key=lambda c: c.best_score, reverse=True)
    return cases


def parse_rerank_json(raw: str) -> list[dict]:
    cleaned = _FENCE_RE.sub("", raw).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON array found: {raw[:200]!r}")
    payload = cleaned[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
    if not isinstance(data, list):
        raise ValueError(f"Expected list, got {type(data).__name__}")
    return data


@retry(
    wait=wait_exponential(multiplier=5, min=10, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _call_rerank_llm(issue: Issue, candidates: list[RetrievedCase]) -> list[dict]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    case_block = "\n\n".join(
        f"[{c.case_slug}] {c.case_title} — {c.citation} ({c.year}, {c.court})\n"
        f"Best-matching passage:\n{c.best_chunk_text[:800]}"
        for c in candidates
    )
    user_content = (
        f"ISSUE: {issue.issue_title}\n"
        f"AREA: {issue.area_of_law}\n"
        f"DESCRIPTION: {issue.description}\n\n"
        f"CANDIDATES (15 retrieved cases):\n\n{case_block}"
    )
    response = client.models.generate_content(
        model=RERANK_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=RERANK_SYSTEM,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return parse_rerank_json(response.text or "")


def research_for_issue(
    issue: Issue,
    *,
    index,
    embed_fn: Callable = embed_texts,
    query_fn: Callable = pinecone_query,
    rerank_fn: Callable = _call_rerank_llm,
    top_k: int = 15,
) -> list[RankedCase]:
    query_text = f"{issue.issue_title}. {issue.description}"
    [vector] = embed_fn([query_text], input_type="query")
    raw_matches = query_fn(index, vector=vector, top_k=top_k)
    candidates = deduplicate_by_case(raw_matches)
    if not candidates:
        return []

    picks = rerank_fn(issue, candidates)

    by_slug = {c.case_slug: c for c in candidates}
    ranked: list[RankedCase] = []
    for p in picks:
        slug = p.get("case_slug", "")
        reasoning = p.get("reasoning", "")
        base = by_slug.get(slug)
        if base is None:
            # Defensive: LLM hallucinated a slug not in candidates. Drop
            # silently; citation validator at Task 12 is the hard gate.
            continue
        ranked.append(
            RankedCase(
                case_slug=base.case_slug,
                case_title=base.case_title,
                citation=base.citation,
                court=base.court,
                year=base.year,
                area_of_law=base.area_of_law,
                best_chunk_text=base.best_chunk_text,
                reasoning=reasoning,
            )
        )
    return ranked

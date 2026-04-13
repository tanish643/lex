"""Moot problem -> legal issues.

Sends the full moot text to Gemini with a system prompt that demands
JSON output. Parses robustly — models occasionally slip in a leading
'Here are the issues:' or wrap in ```json fences despite instructions,
so parse_issues_json tolerates both.

Model choice: gemini-2.0-flash. Fast, cheap, strong enough for issue
extraction. Upgrade to gemini-2.5-pro if Task 14 scores <3/5 on
issue extraction quality.
"""

from __future__ import annotations

import json
import os
import re

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from lexai.prompts.issues import ISSUE_EXTRACTION_SYSTEM

MODEL = "gemini-2.5-flash"


class Issue(BaseModel):
    issue_title: str
    area_of_law: str
    relevant_statutes: list[str] = Field(default_factory=list)
    relevant_articles: list[str] = Field(default_factory=list)
    description: str


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_issues_json(raw: str) -> list[Issue]:
    """Parse an LLM response to a list of Issue, tolerant of common noise."""
    cleaned = _FENCE_RE.sub("", raw).strip()

    # slice from the first '[' if there's leading prose
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON array found in response: {raw[:200]!r}")
    payload = cleaned[start : end + 1]

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in response: {e}") from e

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    return [Issue.model_validate(item) for item in data]


@retry(
    wait=wait_exponential(multiplier=5, min=10, max=60),
    stop=stop_after_attempt(4),
    reraise=True,
)
def extract_issues(moot_text: str) -> list[Issue]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=MODEL,
        contents=moot_text,
        config=types.GenerateContentConfig(
            system_instruction=ISSUE_EXTRACTION_SYSTEM,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return parse_issues_json(response.text or "")

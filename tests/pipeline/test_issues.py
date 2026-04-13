from pathlib import Path

import pytest

from lexai.ingest.pdf import extract_pdf_text
from lexai.pipeline.issues import Issue, extract_issues, parse_issues_json

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "moots" / "sample.pdf"


def test_parse_issues_json_valid():
    raw = """[
      {"issue_title": "Jurisdiction of CCL over patent-linked conduct",
       "area_of_law": "competition",
       "relevant_statutes": ["Competition Act 2002", "Patents Act 1970"],
       "relevant_articles": [],
       "description": "Whether CCL can adjudicate on conduct tied to patent rights."}
    ]"""
    issues = parse_issues_json(raw)
    assert len(issues) == 1
    assert issues[0].issue_title.startswith("Jurisdiction")
    assert issues[0].area_of_law == "competition"
    assert "Competition Act 2002" in issues[0].relevant_statutes


def test_parse_issues_json_strips_markdown_fences():
    raw = """```json
    [{"issue_title": "X", "area_of_law": "contract",
      "relevant_statutes": [], "relevant_articles": [],
      "description": "short"}]
    ```"""
    issues = parse_issues_json(raw)
    assert len(issues) == 1


def test_parse_issues_json_tolerates_leading_prose():
    raw = "Here are the issues:\n[{\"issue_title\": \"X\", \"area_of_law\": \"contract\", \"relevant_statutes\": [], \"relevant_articles\": [], \"description\": \"x\"}]"
    issues = parse_issues_json(raw)
    assert len(issues) == 1


def test_parse_issues_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_issues_json("this is not json")


@pytest.mark.integration
@pytest.mark.skipif(not FIXTURE.exists(), reason="sample.pdf missing")
def test_extract_issues_on_real_moot_returns_multiple():
    text = extract_pdf_text(FIXTURE)
    issues = extract_issues(text)
    # CAT-L identified 3 issues; Gemini should find at least 2
    assert len(issues) >= 2
    for issue in issues:
        assert isinstance(issue, Issue)
        assert issue.issue_title
        assert issue.area_of_law
        assert isinstance(issue.relevant_statutes, list)
        assert isinstance(issue.relevant_articles, list)
        assert issue.description

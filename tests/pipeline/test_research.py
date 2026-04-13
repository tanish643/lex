from unittest.mock import MagicMock

import pytest

from lexai.pipeline.issues import Issue
from lexai.pipeline.research import (
    RankedCase,
    RetrievedCase,
    deduplicate_by_case,
    parse_rerank_json,
    research_for_issue,
)
from lexai.rag.vectorstore import Match


def _match(slug: str, score: float, chunk_index: int = 0, text: str = "body") -> Match:
    return Match(
        chunk_id=f"{slug}::{chunk_index}",
        score=score,
        case_slug=slug,
        case_title=f"Title of {slug}",
        citation=f"cite-{slug}",
        court="SC",
        year=2020,
        area_of_law="competition",
        chunk_index=chunk_index,
        text=text,
    )


def test_deduplicate_by_case_keeps_best_scoring_chunk():
    matches = [
        _match("case-a", 0.9, chunk_index=0, text="a0"),
        _match("case-b", 0.85, chunk_index=0, text="b0"),
        _match("case-a", 0.95, chunk_index=1, text="a1"),  # higher score, later
        _match("case-c", 0.80, chunk_index=0, text="c0"),
        _match("case-a", 0.70, chunk_index=2, text="a2"),
    ]
    deduped = deduplicate_by_case(matches)
    assert len(deduped) == 3
    # case-a should hold the chunk_index=1 variant (best score)
    case_a = next(r for r in deduped if r.case_slug == "case-a")
    assert case_a.best_chunk_text == "a1"
    assert case_a.best_score == 0.95
    # order by score desc
    assert [r.case_slug for r in deduped] == ["case-a", "case-b", "case-c"]


def test_parse_rerank_json_valid():
    raw = """[
      {"case_slug": "2017-8-scc-47", "reasoning": "direct s3(3) precedent"},
      {"case_slug": "air-1978-sc-597", "reasoning": "natural justice baseline"}
    ]"""
    picks = parse_rerank_json(raw)
    assert len(picks) == 2
    assert picks[0]["case_slug"] == "2017-8-scc-47"


def test_parse_rerank_json_strips_fences():
    raw = "```json\n[{\"case_slug\":\"x\",\"reasoning\":\"y\"}]\n```"
    picks = parse_rerank_json(raw)
    assert picks[0]["case_slug"] == "x"


def test_parse_rerank_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_rerank_json("nope")


def test_research_for_issue_wires_pipeline():
    """End-to-end with all external IO mocked."""
    issue = Issue(
        issue_title="No-poach protocol as horizontal agreement",
        area_of_law="competition",
        relevant_statutes=["Competition Act 2002"],
        relevant_articles=[],
        description="Is the Protocol a per se violation under Section 3(3)?",
    )

    candidates = [
        _match("2017-8-scc-47", 0.91),
        _match("2017-5-scc-17", 0.88),
        _match("compat-2016", 0.82),
    ]

    fake_index = MagicMock()
    fake_embed = MagicMock(return_value=[[0.0] * 4])
    fake_query = MagicMock(return_value=candidates)
    fake_rerank = MagicMock(
        return_value=[
            {"case_slug": "2017-5-scc-17", "reasoning": "Coord Committee applies s3 to associations"},
            {"case_slug": "2017-8-scc-47", "reasoning": "Excel Crop Care sets s3(3) evidence bar"},
        ]
    )

    ranked = research_for_issue(
        issue,
        index=fake_index,
        embed_fn=fake_embed,
        query_fn=fake_query,
        rerank_fn=fake_rerank,
        top_k=15,
    )

    assert len(ranked) == 2
    assert all(isinstance(r, RankedCase) for r in ranked)
    assert ranked[0].case_slug == "2017-5-scc-17"
    assert ranked[0].reasoning.startswith("Coord Committee")
    # query text should be built from issue title + description
    qtext = fake_embed.call_args[0][0][0]
    assert "No-poach" in qtext or "horizontal" in qtext
    fake_embed.assert_called_once()


def test_research_for_issue_skips_rerank_picks_not_in_candidates():
    issue = Issue(
        issue_title="x",
        area_of_law="competition",
        relevant_statutes=[],
        relevant_articles=[],
        description="y",
    )
    candidates = [_match("real-case", 0.9)]

    ranked = research_for_issue(
        issue,
        index=MagicMock(),
        embed_fn=lambda t, input_type="query": [[0.0]],
        query_fn=lambda index, vector, top_k: candidates,
        rerank_fn=lambda *a, **k: [
            {"case_slug": "hallucinated-case", "reasoning": "bogus"},
            {"case_slug": "real-case", "reasoning": "real"},
        ],
    )
    assert len(ranked) == 1
    assert ranked[0].case_slug == "real-case"

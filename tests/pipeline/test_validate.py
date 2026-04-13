import pytest

from lexai.pipeline.arguments import IRACBlock, IssueArguments
from lexai.pipeline.research import RankedCase
from lexai.pipeline.validate import (
    HallucinationError,
    ValidationReport,
    extract_citations,
    normalize_citation,
    validate_arguments,
)


def _case(slug: str, citation: str, title: str = "") -> RankedCase:
    return RankedCase(
        case_slug=slug,
        case_title=title or f"Title {slug}",
        citation=citation,
        court="Supreme Court of India",
        year=2017,
        area_of_law="competition",
        best_chunk_text="",
        reasoning="",
    )


def test_extract_citations_catches_air_format():
    text = "See Maneka Gandhi v Union of India, AIR 1978 SC 597, for the proposition."
    cites = extract_citations(text)
    assert "AIR 1978 SC 597" in cites


def test_extract_citations_catches_scc_format():
    text = "In (2017) 8 SCC 47 the Court held ..."
    cites = extract_citations(text)
    assert "(2017) 8 SCC 47" in cites


def test_extract_citations_catches_scc_online():
    text = "2016 SCC OnLine Del 1951 remains authority."
    cites = extract_citations(text)
    # normalized representation
    assert any("SCC OnLine" in c for c in cites)


def test_extract_citations_finds_multiple():
    text = (
        "Per (2017) 5 SCC 17 and AIR 1978 SC 597 and again (2017) 8 SCC 47..."
    )
    cites = extract_citations(text)
    assert len(cites) >= 3


def test_extract_citations_ignores_year_only_phrases():
    text = "In 2017 the Commission observed..."
    cites = extract_citations(text)
    assert cites == []


def test_normalize_citation_lowercases_and_collapses_whitespace():
    assert normalize_citation(" AIR  1978  SC  597 ") == "air 1978 sc 597"
    assert normalize_citation("(2017) 8 SCC 47") == "(2017) 8 scc 47"


def test_validate_arguments_passes_with_grounded_cites():
    allowed = [
        _case("2017-5-scc-17", "(2017) 5 SCC 17"),
        _case("air-1978-sc-597", "AIR 1978 SC 597"),
    ]
    args = IssueArguments(
        petitioner_arguments=[
            IRACBlock(
                issue="x",
                rule="Section 3(3)",
                application="Per (2017) 5 SCC 17 trade associations are covered.",
                conclusion="Void.",
            )
        ],
        respondent_arguments=[
            IRACBlock(issue="y", rule="ancillary", application="AIR 1978 SC 597 teaches procedural fairness.", conclusion="Valid."),
        ],
    )
    report = validate_arguments(args, allowed)
    assert report.ok
    assert report.hallucinated == []
    assert sorted(report.used_citations) == sorted(["(2017) 5 SCC 17", "AIR 1978 SC 597"])


def test_validate_arguments_flags_hallucinated_citation():
    allowed = [_case("real", "(2017) 5 SCC 17")]
    args = IssueArguments(
        petitioner_arguments=[
            IRACBlock(
                issue="x",
                rule="y",
                application="See AIR 2099 SC 9999 for a controlling authority.",
                conclusion="c",
            )
        ],
        respondent_arguments=[
            IRACBlock(issue="a", rule="b", application="Per (2017) 5 SCC 17.", conclusion="d")
        ],
    )
    report = validate_arguments(args, allowed)
    assert not report.ok
    assert "AIR 2099 SC 9999" in report.hallucinated


def test_validate_arguments_strict_raises_on_hallucination():
    allowed = [_case("real", "(2017) 5 SCC 17")]
    args = IssueArguments(
        petitioner_arguments=[
            IRACBlock(issue="x", rule="y", application="Per AIR 9999 SC 1.", conclusion="c")
        ],
        respondent_arguments=[
            IRACBlock(issue="a", rule="b", application="Per (2017) 5 SCC 17.", conclusion="d")
        ],
    )
    with pytest.raises(HallucinationError):
        validate_arguments(args, allowed, strict=True)


def test_validate_arguments_is_punctuation_tolerant():
    # Real-world LLM output might write "(2017)8 SCC 47" or extra spaces
    allowed = [_case("x", "(2017) 8 SCC 47")]
    args = IssueArguments(
        petitioner_arguments=[
            IRACBlock(
                issue="x", rule="y", application="see (2017)  8  SCC  47", conclusion="c",
            )
        ],
        respondent_arguments=[
            IRACBlock(
                issue="a", rule="b", application="see (2017) 8 SCC 47 again", conclusion="d"
            )
        ],
    )
    report = validate_arguments(args, allowed)
    assert report.ok, f"Should tolerate whitespace variations, got hallucinated={report.hallucinated}"

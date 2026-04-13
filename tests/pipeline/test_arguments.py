import pytest

from lexai.pipeline.arguments import (
    IRACBlock,
    IssueArguments,
    generate_arguments,
    parse_arguments_json,
)
from lexai.pipeline.issues import Issue
from lexai.pipeline.research import RankedCase


def _issue() -> Issue:
    return Issue(
        issue_title="Whether the no-poach protocol is a per se violation under Section 3(3)",
        area_of_law="competition",
        relevant_statutes=["Competition Act 2002"],
        relevant_articles=[],
        description="The Protocol restricts hiring between AHC portfolio companies, raising whether this is market allocation.",
    )


def _cases() -> list[RankedCase]:
    return [
        RankedCase(
            case_slug="2017-5-scc-17",
            case_title="CCI v Coordination Committee of Artists",
            citation="(2017) 5 SCC 17",
            court="Supreme Court of India",
            year=2017,
            area_of_law="competition",
            best_chunk_text="holding trade associations are covered by Section 3",
            reasoning="Coord Committee extends Section 3 to associations of enterprises",
        ),
        RankedCase(
            case_slug="2017-8-scc-47",
            case_title="Excel Crop Care v CCI",
            citation="(2017) 8 SCC 47",
            court="Supreme Court of India",
            year=2017,
            area_of_law="competition",
            best_chunk_text="holding bid rigging requires meeting of minds",
            reasoning="Excel Crop Care confirms Section 3(3) evidence standard",
        ),
    ]


def test_parse_arguments_json_valid():
    raw = """{
      "petitioner_arguments": [
        {"issue": "No-poach is market allocation",
         "rule": "Section 3(3) Competition Act",
         "application": "Per (2017) 5 SCC 17, trade associations are Section 3 enterprises...",
         "conclusion": "Tribunal should hold the Protocol per se void."}
      ],
      "respondent_arguments": [
        {"issue": "Protocol is ancillary restraint",
         "rule": "Rule of reason doctrine",
         "application": "Protocol is narrow and proportionate...",
         "conclusion": "Tribunal should apply rule of reason."}
      ]
    }"""
    args = parse_arguments_json(raw)
    assert isinstance(args, IssueArguments)
    assert len(args.petitioner_arguments) == 1
    assert len(args.respondent_arguments) == 1
    assert isinstance(args.petitioner_arguments[0], IRACBlock)
    assert "per se void" in args.petitioner_arguments[0].conclusion


def test_parse_arguments_json_strips_fences():
    raw = """```json
    {"petitioner_arguments": [{"issue":"x","rule":"y","application":"z","conclusion":"w"}],
     "respondent_arguments": [{"issue":"x","rule":"y","application":"z","conclusion":"w"}]}
    ```"""
    args = parse_arguments_json(raw)
    assert len(args.petitioner_arguments) == 1


def test_parse_arguments_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_arguments_json("not json")


def test_parse_arguments_json_requires_both_sides():
    raw = """{"petitioner_arguments":[{"issue":"i","rule":"r","application":"a","conclusion":"c"}]}"""
    with pytest.raises(ValueError):
        parse_arguments_json(raw)


def test_generate_arguments_accepts_injected_llm():
    mock_llm = lambda issue, cases: IssueArguments(
        petitioner_arguments=[
            IRACBlock(issue="p-i", rule="p-r", application="per (2017) 5 SCC 17", conclusion="p-c")
        ],
        respondent_arguments=[
            IRACBlock(issue="r-i", rule="r-r", application="per (2017) 8 SCC 47", conclusion="r-c")
        ],
    )

    out = generate_arguments(_issue(), _cases(), llm=mock_llm)
    assert out.petitioner_arguments[0].issue == "p-i"
    assert "(2017) 5 SCC 17" in out.petitioner_arguments[0].application

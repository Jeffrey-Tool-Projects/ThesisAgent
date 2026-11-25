"""A summary as editable text: nothing is lost on the way there and back."""
from __future__ import annotations

from dataclasses import fields

import pytest

from thesisagents.core.models import Paper, PaperSummary, RqResult
from thesisagents.core.summary_text import (
    FIELDS,
    SECTIONS,
    covered_sections,
    summary_to_texts,
    texts_to_summary,
)

FULL = PaperSummary(
    language="zh-tw",
    motivation=("Repairs are slow.", "第二點"), contributions=("C1",), method=("M1",),
    results=("R1",), limitations=("L1",), takeaways=("T1",),
    pain_points=(("Cost", ("a", "b")), ("Empty heading", ())),
    research_question="How fast?",
    contributions_detailed=(("Ranker", "orders a|b patches"),),
    headline_metrics=(("Fixed", "40%", ""), ("Time", "3 s", "9 s")),
    technique_table=(("Beam", "search"),),
    literature_table=(("Author", "Year", "Gap"), ("X", "2020", "none")),
    method_sections=(("Search", ("s1",)),), evaluation_sections=(("Data", ("d1",)),),
    system_flow=("in", "out"), research_questions=(("RQ1", "Why?"),),
    rq_results=(RqResult("RQ1", "Why?", (("h",), ("1",)), ("x",)),),
    core_observation="It works.", future_work=("F1",),
    figures=(("cap", "p.png", ("b",)),), paper_tables=(("cap", (("h",),), ()),),
    raw_text_chars=5, model="m",
)


def test_every_field_survives_the_round_trip():
    assert texts_to_summary(FULL, summary_to_texts(FULL)) == FULL


def test_every_text_field_of_a_summary_can_be_edited():
    kept = {"language", "rq_results", "figures", "paper_tables", "raw_text_chars", "model"}
    assert {f.name for f in fields(PaperSummary)} - kept == {spec.name for spec in FIELDS}


def test_what_text_cannot_hold_is_carried_over():
    edited = texts_to_summary(FULL, dict.fromkeys(summary_to_texts(FULL), ""))
    assert (edited.rq_results, edited.figures, edited.paper_tables) == (
        FULL.rq_results, FULL.figures, FULL.paper_tables
    )
    assert edited.motivation == ()
    assert (edited.language, edited.model) == ("zh-tw", "m")


def test_a_summary_can_be_started_from_nothing():
    texts = summary_to_texts(None)
    assert set(texts.values()) == {""}
    texts["limitations"] = "  Only Java  \n\n second "
    summary = texts_to_summary(None, texts, language="ja")
    assert (summary.language, summary.limitations) == ("ja", ("Only Java", "second"))


@pytest.mark.parametrize(("name", "text", "expected"), [
    ("core_observation", "It\n works. \n", "It works."),
    ("pain_points", "a\n# Cost\nb\n##Speed\n", (("", ("a",)), ("Cost", ("b",)), ("Speed", ()))),
    ("technique_table", "Beam", (("Beam", ""),)),
    ("technique_table", "Beam | search | wide", (("Beam", "search | wide"),)),
    ("technique_table", "a\\|b | c", (("a|b", "c"),)),
    ("headline_metrics", "F1 | 0.9", (("F1", "0.9", ""),)),
    ("literature_table", "A | B\nx", (("A", "B"), ("x",))),
])
def test_line_formats(name, text, expected):
    assert getattr(texts_to_summary(None, {name: text}), name) == expected


def _paper(**kwargs) -> Paper:
    defaults = {
        "source": "a", "source_id": "1", "title": "T", "authors": (), "year": None,
        "venue": None, "abstract": "", "url": "",
    }
    return Paper(**{**defaults, **kwargs})


def test_coverage_names_what_is_missing():
    assert not any(covered_sections(_paper(), None).values())
    covered = covered_sections(_paper(abstract="x", doi="10.1/a"), FULL)
    assert list(covered) == list(SECTIONS)
    assert all(covered.values())
    only = PaperSummary(language="en", limitations=("L",))
    assert [s for s, ok in covered_sections(_paper(), only).items() if ok] == ["conclusion"]
    tables = PaperSummary(language="en", paper_tables=(("c", (), ()),))
    assert covered_sections(_paper(), tables)["experiment"]

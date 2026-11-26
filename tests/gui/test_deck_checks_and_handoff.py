"""Tests for the Deck page's template check and deck review (``progress.md``
#23) and the Enrich page's hand-off to an LLM agent (#27).

The template check and the review run on real files: a stock python-pptx
template and a deck exported in the test. No network is used (the export's
identifier check is switched off).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from pptx import Presentation

from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters import export_collection
from thesisagents.exporters.template import TemplateIssue, TemplateValidationReport
from thesisagents.gui import handoff
from thesisagents.gui.handoff import HandoffError, read_handoff, write_handoff
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.pages.enrich import EnrichPage


def _paper(idx: int) -> Paper:
    return Paper(
        source="arxiv", source_id=f"2401.{idx:05d}", title=f"Short paper {idx}",
        authors=("Ada Author",), year=2024, venue=None, abstract="An abstract.",
        url=f"https://example.org/{idx}", pdf_url=f"https://example.org/{idx}.pdf",
    )


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(Query("attention", ("arxiv",)), papers or (_paper(1), _paper(2)))


def _summary(text: str) -> PaperSummary:
    return PaperSummary(language="en", research_question=text)


# --- #27 hand-off file ----------------------------------------------------------


def _fill(path: Path, answers: dict[str, str]) -> None:
    """Play the agent: fill the summary of each paper whose key is in ``answers``."""
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document["papers"]:
        if entry["key"] in answers:
            answer = _summary(answers[entry["key"]])
            filled = replace(Paper.from_dict(entry["paper"]), summary=answer)
            entry["paper"] = filled.to_dict()
    path.write_text(json.dumps(document), encoding="utf-8")


def test_handoff_round_trip_attaches_summaries_by_key(tmp_path):
    collection = _collection()
    target = tmp_path / "handoff.json"
    assert write_handoff(collection, target, language="zh-tw") == 2
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["format"] == "thesisagents-agent-handoff"
    assert document["language"] == "zh-tw"
    assert "research_question" in document["summary_template"]
    assert document["papers"][0]["paper"]["pdf_url"].endswith("1.pdf")

    second = collection.papers[1]
    document["papers"].reverse()                       # an agent may reorder
    target.write_text(json.dumps(document), encoding="utf-8")
    _fill(target, {second.dedup_key(): "What limits attention?"})
    result = read_handoff(target, collection)
    assert result.imported == 1
    assert result.unmatched == 0
    assert result.collection.papers[0].summary is None
    assert result.collection.papers[1].summary.research_question == "What limits attention?"


def test_entries_for_other_papers_are_counted_not_imported(tmp_path):
    target = tmp_path / "handoff.json"
    write_handoff(_collection(_paper(7)), target, language="en")
    _fill(target, {_paper(7).dedup_key(): "x"})
    result = read_handoff(target, _collection(_paper(1)))
    assert (result.imported, result.unmatched) == (0, 1)


def test_an_existing_summary_is_kept_when_the_file_has_none(tmp_path):
    enriched = replace(_paper(1), summary=_summary("kept"))
    target = tmp_path / "handoff.json"
    write_handoff(_collection(enriched), target, language="en")
    document = json.loads(target.read_text(encoding="utf-8"))
    document["papers"][0]["paper"]["summary"] = None
    target.write_text(json.dumps(document), encoding="utf-8")
    result = read_handoff(target, _collection(enriched))
    assert result.collection.papers[0].summary.research_question == "kept"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("not json", "not a JSON file"),
        (json.dumps({"format": "something else"}), "not a ThesisAgents hand-off"),
        (json.dumps({"format": "thesisagents-agent-handoff", "version": 99}), "version 99"),
        (json.dumps({"format": "thesisagents-agent-handoff", "version": 1, "papers": [3]}),
         "needs a text `key`"),
        (json.dumps({"format": "thesisagents-agent-handoff", "version": 1, "papers": 5}),
         "must be a list"),
        (json.dumps({"format": "thesisagents-agent-handoff", "version": 1,
                     "papers": [{"key": ["a"], "paper": {}}]}), "needs a text `key`"),
        pytest.param(
            "[" * 200_000 + "]" * 200_000, "nested too deeply|not a JSON file", id="deeply-nested"
        ),
    ],
)
def test_bad_handoff_files_are_refused(tmp_path, content, message):
    target = tmp_path / "bad.json"
    target.write_text(content, encoding="utf-8")
    collection = _collection()
    with pytest.raises(HandoffError, match=message):
        read_handoff(target, collection)


@pytest.mark.parametrize("summary", [[1, 2], "abc"])
def test_a_summary_that_is_not_an_object_is_refused(tmp_path, summary):
    target = tmp_path / "handoff.json"
    collection = _collection()
    write_handoff(collection, target, language="en")
    document = json.loads(target.read_text(encoding="utf-8"))
    document["papers"][0]["paper"]["summary"] = summary
    target.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HandoffError, match="must be an object"):
        read_handoff(target, collection)


def test_a_paper_missing_required_fields_is_refused(tmp_path):
    target = tmp_path / "handoff.json"
    collection = _collection()
    write_handoff(collection, target, language="en")
    document = json.loads(target.read_text(encoding="utf-8"))
    paper = document["papers"][0]["paper"]
    paper["summary"] = {"language": "en", "research_question": "x"}
    del paper["title"]
    target.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(HandoffError, match="cannot be read"):
        read_handoff(target, collection)


def test_an_oversized_file_is_refused_before_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff, "MAX_HANDOFF_BYTES", 10)
    target = tmp_path / "big.json"
    write_handoff(_collection(), target, language="en")
    collection = _collection()
    with pytest.raises(HandoffError, match="larger than"):
        read_handoff(target, collection)


def test_enrich_page_exports_and_imports_for_an_agent(qtbot, tmp_path):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    assert not page._agent_export_button.isEnabled()  # noqa: SLF001
    collection = _collection()
    page.set_collection(collection)
    assert page._agent_export_button.isEnabled()  # noqa: SLF001
    target = tmp_path / "handoff.json"
    page.export_for_agent(str(target))
    assert "Wrote 2 papers" in page.status_text()
    _fill(target, {collection.papers[0].dedup_key(): "agent wrote this"})
    with qtbot.waitSignal(page.collection_ready) as signal:
        page.import_from_agent(str(target))
    assert signal.args[0].papers[0].summary.research_question == "agent wrote this"
    assert page.table_model().item(0, 2).text() == "ok"
    assert "Imported 1 summaries" in page.status_text()


def test_enrich_page_reports_a_bad_file(qtbot, tmp_path):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection())
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    page.import_from_agent(str(bad))
    assert page.status_text().startswith("Hand-off failed")


# --- #23 template check and deck review ----------------------------------------------


def _wait_report(page: DeckPage, qtbot) -> str:
    qtbot.waitUntil(lambda: page.last_report() is not None, timeout=10000)
    return page.last_report().text()


def test_check_template_needs_a_template(qtbot):
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page._on_check_template_clicked()  # noqa: SLF001
    assert "Choose a template" in page.status_text()


def test_check_template_reports_a_usable_template(qtbot, tmp_path):
    template = tmp_path / "stock.pptx"
    Presentation().save(template)
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_template_path(str(template))
    page._on_check_template_clicked()  # noqa: SLF001
    text = _wait_report(page, qtbot)
    assert text.startswith(f"Template {template}")
    assert page.status_text().startswith("Template check:")


def test_check_template_shows_every_problem(qtbot, monkeypatch):
    report = TemplateValidationReport(
        template="broken.pptx",
        errors=(TemplateIssue("layout-not-found", "layout 'Cover' is not in the template"),),
    )
    monkeypatch.setattr(
        "thesisagents.gui.pages.deck.validate_template", lambda *_a, **_k: report
    )
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_template_path("broken.pptx")
    page._on_check_template_clicked()  # noqa: SLF001
    text = _wait_report(page, qtbot)
    assert "NOT USABLE" in text
    assert "layout 'Cover' is not in the template" in text
    assert page.status_text() == "Template check: not usable, 1 problem(s). See the report."


def test_review_audits_an_exported_deck(qtbot, tmp_path):
    written = export_collection(
        _collection(_paper(1)),
        ExportOptions(
            formats=("pptx",), out_dir=str(tmp_path), filename_stem="deck",
            verify_identifiers=False,
        ),
    )
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.review_deck_file(str(written["pptx"]))
    text = _wait_report(page, qtbot)
    assert "deck review" in text
    assert "verdict:" in text
    assert page.status_text().startswith("Deck review:")


def test_review_of_a_non_deck_is_an_error_not_a_crash(qtbot, tmp_path):
    bogus = tmp_path / "not-a-deck.pptx"
    bogus.write_text("hello", encoding="utf-8")
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.review_deck_file(str(bogus))
    qtbot.waitUntil(lambda: page.status_text().startswith("Check failed"), timeout=10000)
    assert page._review_button.isEnabled()  # noqa: SLF001

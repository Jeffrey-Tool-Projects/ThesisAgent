"""Drive Deck export through a local program and inspect the written presentation."""

from __future__ import annotations

import sys
from dataclasses import replace

import pytest
from pptx import Presentation

from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.pages.settings import settings_store


def _papers() -> PaperCollection:
    papers = tuple(
        Paper(
            title=title, authors=(), year=None, venue=None, source="local",
            source_id=title, url="", abstract="Abstract only",
            raw={"extracted_text": "Measured result: " + result},
        )
        for title, result in (
            ("Selected trial", "The trial took 17 seconds."),
            ("Excluded trial", "The trial took 29 seconds."),
        )
    )
    return PaperCollection(Query("trials", ("local",)), papers)


def _set_program(page: DeckPage, command: str) -> None:
    settings_store().setValue("llm/base_url/cli", command)
    combo = page.cli_provider_combo()
    combo.setCurrentIndex(combo.findData("cli"))
    assert combo.currentData() == "cli"


def test_selected_search_result_reaches_the_written_cli_deck(qtbot, monkeypatch, tmp_path):
    async def search(_query, **_kwargs):
        return _papers()

    monkeypatch.setattr("thesisagents.gui.pages.search.run_search", search)
    program = tmp_path / "summarise paper.py"
    program.write_text(
        "import json, sys\n"
        "text = sys.stdin.read()\n"
        "result = next(s for s in text.splitlines() if s.startswith('Measured result:'))\n"
        "print(json.dumps({'core_observation': result}))\n",
        encoding="utf-8",
    )
    window = MainWindow("en")
    qtbot.addWidget(window)
    source = window.search_page()
    source.set_query_text("trials")
    with qtbot.waitSignal(source.collection_ready, timeout=5000):
        source._search_button.click()
    source.papers_model().set_checked(1, False)
    deck = window.deck_page()
    deck._out_dir_input.setText(str(tmp_path))
    _set_program(deck, f'"{sys.executable}" "{program}"')
    deck._export_button.click()
    qtbot.waitUntil(lambda: deck._export_button.isEnabled(), timeout=15000)
    assert "Wrote" in deck.status_text()
    path, = tmp_path.glob("*.pptx")
    slide_text = "\n".join(
        shape.text for slide in Presentation(path).slides for shape in slide.shapes
        if shape.has_text_frame
    )
    assert "Selected trial" in slide_text
    assert "17 seconds" in slide_text
    assert "Excluded trial" not in slide_text
    assert "29 seconds" not in slide_text
    assert list(tmp_path.glob("*.xlsx"))


@pytest.mark.parametrize("failure", ["missing", "signed_out"])
def test_cli_failure_is_visible_and_export_can_be_retried(qtbot, tmp_path, failure):
    page = DeckPage("en")
    qtbot.addWidget(page)
    page.set_collection(_papers())
    output = tmp_path / "out"
    page._out_dir_input.setText(str(output))
    command = "missing-test-deck-cli"
    expected = command
    if failure == "signed_out":
        script = tmp_path / "signed out.py"
        script.write_text("raise SystemExit('Not logged in. Run login first.')\n", encoding="utf-8")
        command = f'"{sys.executable}" "{script}"'
        expected = "requires sign-in"
    _set_program(page, command)
    page._export_button.click()
    qtbot.waitUntil(lambda: page._export_button.isEnabled(), timeout=10000)
    assert expected in page.status_text().lower()
    assert page.files_model().rowCount() == 0
    assert not list(output.glob("*"))

    page.format_checkbox("pptx").setChecked(False)
    page._export_button.click()
    qtbot.waitUntil(lambda: page._export_button.isEnabled(), timeout=10000)
    assert "Wrote" in page.status_text()
    assert list(output.glob("*.xlsx"))


def test_missing_full_text_names_the_paper_before_writing(qtbot, tmp_path):
    page = DeckPage("zh-tw")
    qtbot.addWidget(page)
    collection = _papers()
    paper = replace(collection.papers[0], raw={})
    page.set_collection(replace(collection, papers=(paper,)))
    output = tmp_path / "out"
    page._out_dir_input.setText(str(output))
    _set_program(page, f'"{sys.executable}"')
    page._export_button.click()
    qtbot.waitUntil(lambda: page._export_button.isEnabled(), timeout=5000)
    assert paper.title in page.status_text()
    assert "PDF" in page.status_text()
    assert not list(output.glob("*"))

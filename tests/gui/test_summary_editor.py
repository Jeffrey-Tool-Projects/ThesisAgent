"""Editing a paper's summary by hand, from the Enrich and the Library page."""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QMessageBox

from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.enrich import EnrichPage
from thesisagents.gui.pages.library import LibraryPage
from thesisagents.gui.widgets.summary_editor import SummaryEditor
from thesisagents.library import Library

PAPER = Paper(
    source="arxiv", source_id="1", title="Learned <b>Repair</b>", authors=("Ada",), year=2020,
    venue=None, abstract="An abstract.", url="https://example.org/1", doi="10.1/a",
    summary=PaperSummary(language="en", motivation=("Slow",), model="m"),
)


def _editor(qtbot, paper: Paper = PAPER) -> SummaryEditor:
    editor = SummaryEditor(paper, "en")
    qtbot.addWidget(editor)
    return editor


def test_the_form_shows_the_summary_and_what_is_missing(qtbot):
    editor = _editor(qtbot)
    assert editor.box("motivation").toPlainText() == "Slow"
    assert editor.missing_sections() == [
        "literature_review", "methodology", "experiment", "conclusion"
    ]
    assert "Methodology" in editor.coverage_text()
    for name in ("technique_table", "method", "results", "limitations"):
        editor.box(name).setPlainText("a | b")
    qtbot.waitUntil(lambda: "All seven" in editor.coverage_text(), timeout=2000)


def test_saving_hands_back_the_paper_with_its_summary(qtbot):
    editor = _editor(qtbot)
    saved = []
    editor.saved.connect(saved.append)
    editor.box("limitations").setPlainText("Only Java\nOne data set")
    editor.save_button().click()
    assert saved[0].summary.limitations == ("Only Java", "One data set")
    assert saved[0].summary.motivation == ("Slow",)
    assert saved[0].summary.model == "m"
    assert saved[0].title == PAPER.title


def test_an_emptied_summary_is_none(qtbot):
    editor = _editor(qtbot)
    saved = []
    editor.saved.connect(saved.append)
    editor.box("motivation").clear()
    editor.save_button().click()
    assert saved[0].summary is None


@pytest.mark.parametrize(("answer", "closed"), [
    (QMessageBox.StandardButton.No, False), (QMessageBox.StandardButton.Yes, True),
])
def test_closing_with_changes_asks(qtbot, monkeypatch, answer, closed):
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: asked.append(args) or answer)
    editor = _editor(qtbot)
    editor.show()
    editor.box("method").setPlainText("x")
    editor.reject()
    assert len(asked) == 1
    assert editor.isHidden() is closed


def test_closing_without_changes_does_not_ask(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: pytest.fail("asked"))
    editor = _editor(qtbot)
    editor.show()
    editor.reject()
    assert editor.isHidden()


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(query=Query("x", ("arxiv",)), papers=papers)


def test_the_enrich_page_edits_a_summary_without_a_model(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    page = window.enrich_page()
    other = replace(PAPER, source_id="2", doi="10.1/b", summary=None)
    page.set_collection(_collection(PAPER, other))
    assert not page._edit_button.isEnabled()  # noqa: SLF001
    page._table.selectRow(1)  # noqa: SLF001
    assert page._edit_button.isEnabled()  # noqa: SLF001
    page._edit_button.click()  # noqa: SLF001
    editor = page.summary_editor()
    editor.box("takeaways").setPlainText("Remember this")
    editor.save_button().click()
    papers = page.collection().papers
    assert papers[1].summary.takeaways == ("Remember this",)
    assert papers[0] is PAPER
    # The Deck page exports the edited paper.
    assert window.deck_page().collection().papers[1].summary.takeaways == ("Remember this",)


def test_nothing_is_edited_while_a_run_is_going(qtbot):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(PAPER))
    page._table.selectRow(0)  # noqa: SLF001
    page._running = True  # noqa: SLF001
    page._on_edit_summary()  # noqa: SLF001
    assert not hasattr(page, "_summary_editor")


def test_the_library_page_stores_an_edited_summary(qtbot, tmp_path):
    path = tmp_path / "l.db"
    rich = replace(PAPER, summary=PaperSummary(language="en", future_work=("Later",)))
    with Library(path) as library:
        library.add_papers([rich])
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path(str(path))

    def working(start):
        with qtbot.waitSignal(page.busy_changed, timeout=8000, check_params_cb=lambda b: not b):
            start()

    working(page._on_open_clicked)  # noqa: SLF001
    assert not page.action_button("summary").isEnabled()
    page.select_paper(0)
    page.action_button("summary").click()
    editor = page.summary_editor()
    editor.box("future_work").clear()
    editor.box("motivation").setPlainText("New")
    working(editor.save_button().click)
    with Library(path) as library:
        stored = library.entries()[0].paper.summary
    # An import keeps the richer summary. An edit is what the user decided.
    assert (stored.future_work, stored.motivation) == ((), ("New",))
    assert not stored.has_rich_fields()


def test_the_deck_page_exports_word_into_a_template(qtbot, tmp_path):
    from docx import Document

    template = tmp_path / "school.docx"
    Document().save(str(template))
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    deck = window.deck_page()
    deck.set_docx_template_path(str(template))
    options = deck._export_options(("docx", "tex"), str(tmp_path))  # noqa: SLF001
    assert options.docx_template == str(template)
    assert options.formats == ("docx", "tex")
    assert deck.format_checkbox("docx").text() == "Word draft"

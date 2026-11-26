"""Edits in the GUI reach what is on screen, and typed text is not lost."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.util import Inches
from PySide6.QtCore import QThreadPool

from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters import pptx_edit
from thesisagents.gui import credentials, update_check
from thesisagents.gui.credentials import SERVICE
from thesisagents.gui.handoff import read_handoff, write_handoff
from thesisagents.gui.pages.enrich import EnrichPage
from thesisagents.gui.pages.library import LibraryPage
from thesisagents.gui.pages.search import SearchPage
from thesisagents.gui.pages.settings import SettingsPage, settings_store
from thesisagents.gui.update_check import UpdateCheck
from thesisagents.gui.widgets.deck_editor import DeckEditor
from thesisagents.gui.widgets.library_tabs import SavedSearchesTab
from thesisagents.gui.widgets.notice_banner import NoticeBanner
from thesisagents.gui.widgets.paper_editor import PaperEditor
from thesisagents.intelligence import providers
from thesisagents.library import Library, SavedSearch
from thesisagents.utils.notices import CAPTCHA_CLEARED, CAPTCHA_WAITING, Notice


def _paper(source_id: str, title: str, **fields) -> Paper:
    defaults = {
        "source": "arxiv", "authors": ("Ada Lovelace",), "year": 2020, "venue": None,
        "abstract": "", "url": f"https://example.org/{source_id}",
    }
    defaults.update(fields)
    return Paper(source_id=source_id, title=title, **defaults)


ONE = _paper("1", "Graph attention networks", doi="10.1000/a")
TWO = _paper("2", "Protein folding at scale", doi="10.1000/b")


def _library(path: Path, *papers: Paper) -> Path:
    with Library(path) as library:
        library.add_papers(papers)
    return path


def _idle(qtbot, page, start) -> None:
    with qtbot.waitSignal(page.busy_changed, timeout=8000, check_params_cb=lambda b: not b):
        start()


@pytest.fixture
def page(qtbot, tmp_path):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path(str(_library(tmp_path / "a.db", ONE, TWO)))
    _idle(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    return page


def _select(page: LibraryPage, title: str) -> None:
    for row in range(page.papers_model().rowCount()):
        if page.papers_model().item(row, 0).text() == title:
            page.select_paper(row)
            return
    raise AssertionError(title)


# --- the library ------------------------------------------------------------------------


def test_an_edit_goes_to_the_library_on_screen(qtbot, page, tmp_path, monkeypatch):
    other = _library(tmp_path / "b.db", _paper("8", "Eight"), _paper("9", "Nine"))
    _select(page, ONE.title)
    # As when a library is typed on the Search page: named here, not opened.
    page.set_library_path(str(other))
    monkeypatch.setattr(page, "_confirmed", lambda _question: True)
    _idle(qtbot, page, page.action_button("delete").click)
    with Library(other) as library:
        assert len(library) == 2
    with Library(tmp_path / "a.db") as library:
        assert [e.paper.title for e in library.entries()] == [TWO.title]


def test_papers_that_share_a_key_are_told_apart(qtbot, tmp_path):
    # Two punctuation-only titles have one key and stay two papers.
    path = _library(tmp_path / "k.db", _paper("x", "...", url="https://e.org/x"))
    with Library(path) as library:
        library.add_papers([_paper("y", "!!!", url="https://e.org/y")])
        assert len({e.paper.dedup_key() for e in library.entries()}) == 1
        assert len(library) == 2
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path(str(path))
    _idle(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    for title in ("...", "!!!"):
        _select(page, title)
        assert [e.paper.title for e in page.selected_entries()] == [title]


def test_nothing_starts_a_second_read_while_one_runs(qtbot, page):
    page._set_working(True)  # noqa: SLF001
    assert not page.filter_combo("tag").isEnabled()
    page.set_library_path("somewhere else")
    page._on_open_clicked()  # noqa: SLF001
    QThreadPool.globalInstance().waitForDone(2000)
    assert page.snapshot().path != "somewhere else"
    page._set_working(False)  # noqa: SLF001
    assert page.filter_combo("tag").isEnabled()


def test_a_file_that_cannot_be_read_creates_no_library(qtbot, tmp_path):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path(str(tmp_path / "new.db"))
    _idle(qtbot, page, lambda: page.import_bibliography(str(tmp_path / "missing.bib")))
    assert "cannot read" in page.status_text()
    assert not (tmp_path / "new.db").exists()


@pytest.mark.parametrize(("vpn", "asked"), [(False, ("arxiv",)), (True, ("arxiv", "ieee"))])
def test_a_saved_search_respects_the_access_switch(qtbot, page, monkeypatch, vpn, asked):
    seen = []

    async def fake(query, **_kwargs):
        seen.append(query.sources)
        return PaperCollection(query=query, papers=())

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", fake)
    settings_store().setValue("access/vpn", vpn)
    with Library(page.snapshot().path) as library:
        library.save_search("both", Query("x", ("arxiv", "ieee")))
        library.save_search("only", Query("x", ("ieee",)))
    _idle(qtbot, page, lambda: page._on_run_saved("both"))  # noqa: SLF001
    qtbot.waitUntil(lambda: seen == [asked], timeout=3000)
    _idle(qtbot, page, lambda: page._on_run_saved("only"))  # noqa: SLF001
    assert (len(seen) == 2) is vpn
    # The saved search itself is not changed.
    with Library(page.snapshot().path) as library:
        assert library.saved_search("both").query.sources == ("arxiv", "ieee")


def test_selecting_another_row_does_not_unlock_a_running_search(qtbot):
    tab = SavedSearchesTab("en")
    qtbot.addWidget(tab)
    tab.show_searches([SavedSearch(n, Query(n, ("arxiv",)), "now") for n in ("a", "b")])
    tab.table().selectRow(0)
    assert tab.run_button().isEnabled()
    tab.set_busy(True)
    tab.table().selectRow(1)
    assert not tab.run_button().isEnabled()
    heard = []
    tab.save_requested.connect(heard.append)
    tab.name_input().setText("x")
    tab.name_input().returnPressed.emit()
    assert heard == []
    tab.set_busy(False)
    assert tab.run_button().isEnabled()


# --- the paper form ---------------------------------------------------------------------


def _editor(qtbot, tmp_path) -> tuple[PaperEditor, Path, list]:
    path = _library(tmp_path / "e.db", ONE)
    with Library(path) as library:
        paper_id = library.entries()[0].paper_id
        library.set_note(paper_id, "old note")
        library.add_tags([paper_id], ["kept", "gone"])
        library.screen([paper_id], "exclude", reason="no data", stage="full_text")
        entry = library.entries()[0]
    editor = PaperEditor("en")
    qtbot.addWidget(editor)
    editor.show_entries([entry])
    requests: list = []
    editor.requested.connect(requests.append)
    return editor, path, requests


def test_a_decision_takes_unsaved_text_along(qtbot, tmp_path):
    editor, path, requests = _editor(qtbot, tmp_path)
    editor.note_input().setPlainText("new note")
    editor.tags_input().setText("kept, added")
    editor.button("include").click()
    with Library(path) as library:
        requests[0].apply(library)
        entry = library.entries()[0]
    assert (entry.note, entry.tags) == ("new note", ("added", "kept"))
    assert entry.annotation().decision("title_abstract") == "include"


def test_a_decision_alone_changes_nothing_else(qtbot, tmp_path):
    editor, _path, requests = _editor(qtbot, tmp_path)
    editor.button("include").click()
    request = requests[0]
    assert (request.add_tags, request.remove_tags) == ((), ())
    assert (request.status, request.note) == (None, None)


def test_the_reason_shown_is_the_one_of_the_stage(qtbot, tmp_path):
    editor, _path, requests = _editor(qtbot, tmp_path)
    # The full-text reason is not recorded again for the title and abstract.
    assert editor.reason_input().text() == ""
    stage = editor.stage_combo()
    stage.setCurrentIndex(stage.findData("full_text"))
    assert editor.reason_input().text() == "no data"
    stage.setCurrentIndex(stage.findData("title_abstract"))
    editor.reason_input().setText("typed")
    stage.setCurrentIndex(stage.findData("full_text"))
    assert editor.reason_input().text() == "typed"


# --- the slide editor -------------------------------------------------------------------


@pytest.fixture
def deck(tmp_path) -> Path:
    path = tmp_path / "deck.pptx"
    prs = Presentation()
    for number in range(3):
        box = prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_textbox(
            0, 0, Inches(4), Inches(1)
        )
        box.name = "title"
        box.text_frame.text = f"Slide {number}"
    prs.save(path)
    return path


@pytest.fixture
def slides(qtbot, deck):
    editor = DeckEditor(str(deck), "en")
    qtbot.addWidget(editor)
    return editor


def _texts(path) -> list[str]:
    return [view.shapes[0].text for view in pptx_edit.inspect(path)]


def test_looking_at_a_slide_changes_nothing(slides, deck):
    for row in (1, 2, 0):
        slides.slide_list().setCurrentRow(row)
    assert not slides.button("save").isEnabled()
    assert not slides.button("undo").isEnabled()
    assert slides.save()
    assert _texts(deck) == ["Slide 0", "Slide 1", "Slide 2"]


def test_dragging_keeps_what_was_typed(slides, deck):
    slides.slide_list().setCurrentRow(0)
    slides.text_boxes()["title"].setPlainText("typed")
    model = slides.slide_list().model()
    parent = slides.slide_list().rootIndex()
    assert model.moveRow(parent, 0, parent, 3)
    assert slides.save()
    assert sorted(_texts(deck)) == ["Slide 1", "Slide 2", "typed"]
    assert _texts(deck)[2] == "typed"


def test_deleting_a_slide_drops_what_was_typed_on_it(slides, deck):
    slides.slide_list().setCurrentRow(2)
    slides.text_boxes()["title"].setPlainText("typed")
    slides.delete_slide()
    assert slides.status_text() == ""
    assert slides.save()
    assert _texts(deck) == ["Slide 0", "Slide 1"]


def test_undo_takes_typed_text_back_first(slides, deck):
    slides.delete_slide()
    slides.text_boxes()["title"].setPlainText("typed")
    slides.undo()
    assert slides.text_boxes()["title"].toPlainText() != "typed"
    assert slides.slide_list().count() == 2
    slides.undo()
    assert slides.slide_list().count() == 3


def test_a_text_that_cannot_be_written_is_not_reported_as_saved(slides, deck, monkeypatch):
    before = deck.read_bytes()
    slides.text_boxes()["title"].setPlainText("typed")

    def refuse(*_args, **_kwargs):
        raise ExportError("pptx_edit", "no")

    monkeypatch.setattr(pptx_edit, "update_slide", refuse)
    assert not slides.save()
    assert "no" in slides.status_text()
    assert deck.read_bytes() == before
    slides.add_slide()
    slides.move_slide(1)
    assert slides.slide_list().count() == 3
    assert slides.text_boxes()["title"].toPlainText() == "typed"


# --- enrichment -------------------------------------------------------------------------


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(Query("x", ("arxiv",)), papers)


@pytest.fixture
def enrich(qtbot):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    return page


def test_a_summary_goes_to_its_paper_when_the_list_changed(enrich):
    summary = PaperSummary(language="en", core_observation="mine")
    edited = _paper("1", ONE.title, doi=ONE.doi, summary=summary)
    enrich.set_collection(_collection(ONE, TWO))
    # A search ended while the editor for row 0 was open.
    enrich.set_collection(_collection(TWO, ONE))
    enrich._on_summary_edited(0, edited)  # noqa: SLF001
    assert [p.summary for p in enrich.collection().papers] == [None, summary]
    enrich.set_collection(_collection(TWO))
    enrich._on_summary_edited(0, edited)  # noqa: SLF001
    assert enrich.collection().papers == (TWO,)
    assert "no longer has this paper" in enrich.status_text()


def test_a_misspelt_provider_does_not_stop_the_window(qtbot, monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, "olama")
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(ONE))
    page._on_enrich_clicked()  # noqa: SLF001
    assert "olama" in page.status_text()
    assert not page.is_running()


def _summarised(qtbot, page, monkeypatch, paper, summary):
    read = []

    def summarise(_paper_, extracted, **_choice):
        read.append(extracted.text)
        return summary

    async def never(*_args, **_kwargs):
        raise AssertionError("a local PDF has nothing to download")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv(providers.PROVIDER_ENV, raising=False)
    monkeypatch.setattr("thesisagents.intelligence.pdf.fetch_and_extract", never)
    monkeypatch.setattr("thesisagents.intelligence.summarise.summarise_paper", summarise)
    page.set_collection(_collection(paper))
    _idle(qtbot, page, page._on_enrich_clicked)  # noqa: SLF001
    return read


def test_a_local_pdf_is_summarised_from_its_text(qtbot, enrich, monkeypatch):
    summary = PaperSummary(language="en", core_observation="found")
    paper = _paper("l", "Local", source="local", raw={"extracted_text": "body", "page_count": 2})
    assert _summarised(qtbot, enrich, monkeypatch, paper, summary) == ["body"]
    assert enrich.collection().papers[0].summary == summary


def test_an_empty_answer_replaces_no_summary(qtbot, enrich, monkeypatch):
    kept = PaperSummary(language="en", core_observation="kept")
    paper = _paper("l", "Local", raw={"extracted_text": "body"}, summary=kept)
    _summarised(qtbot, enrich, monkeypatch, paper, PaperSummary(language="en"))
    assert enrich.collection().papers[0].summary == kept
    assert "empty" in enrich.table_model().item(0, 2).text()


def test_a_handoff_file_saved_with_a_byte_order_mark_is_read(tmp_path):
    file = tmp_path / "handoff.json"
    write_handoff(_collection(ONE), file, language="en")
    document = json.loads(file.read_text(encoding="utf-8"))
    document["papers"][0]["paper"]["summary"] = {"language": "en", "limitations": ["x"]}
    file.write_text(json.dumps(document), encoding="utf-8-sig")
    assert read_handoff(file, _collection(ONE)).imported == 1


# --- settings, search form, notices -----------------------------------------------------


def test_a_locked_credential_store_loses_no_key(qtbot, credential_store, monkeypatch):
    names = ("api/ieee", "api/llm_openai")
    for name in names:
        credential_store.saved[SERVICE, name] = "secret"
    monkeypatch.setattr(credentials, "_get", lambda _key: None)
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert page.field_input("api/ieee").text() == ""
    monkeypatch.undo()
    page.trigger_save()
    assert [credential_store.saved.get((SERVICE, name)) for name in names] == ["secret"] * 2


def test_a_key_can_still_be_removed(qtbot, credential_store):
    credential_store.saved[SERVICE, "api/ieee"] = "secret"
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.field_input("api/ieee").setText("")
    page.trigger_save()
    assert (SERVICE, "api/ieee") not in credential_store.saved
    page.field_input("api/ieee").setText("again")
    page.trigger_save()
    page.field_input("api/ieee").setText("")
    page.trigger_save()
    assert (SERVICE, "api/ieee") not in credential_store.saved


def test_a_year_range_that_ends_before_it_starts_is_explained(qtbot):
    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_query_text("graphs")
    page._year_from_spin.setValue(2024)  # noqa: SLF001
    page._year_to_spin.setValue(2020)  # noqa: SLF001
    page._on_search_clicked()  # noqa: SLF001
    assert "year_from" in page.status_text()


def test_the_release_seen_is_remembered_without_network(qtbot, monkeypatch):
    async def offline(_current):
        return None

    monkeypatch.setattr(update_check, "newer_version", offline)
    settings_store().setValue("updates/seen", "0.2.0")
    check = UpdateCheck()
    assert check.start("0.1.0")
    QThreadPool.globalInstance().waitForDone(3000)
    qtbot.wait(20)
    heard = []
    check.found.connect(heard.append)
    check.start("0.1.0")
    assert heard == ["0.2.0"]


def test_one_captcha_solved_leaves_the_other_on_screen(qtbot):
    banner = NoticeBanner("en")
    qtbot.addWidget(banner)
    banner.show_notice(Notice(CAPTCHA_WAITING, site="a.example", seconds=60))
    banner.show_notice(Notice(CAPTCHA_WAITING, site="b.example", seconds=60))
    banner.show_notice(Notice(CAPTCHA_CLEARED, site="a.example"))
    assert "b.example" in banner.text()
    banner.show_notice(Notice(CAPTCHA_CLEARED, site="b.example"))
    assert "b.example" not in banner.text()

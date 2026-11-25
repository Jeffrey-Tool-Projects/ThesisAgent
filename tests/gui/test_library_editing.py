"""Editing a library in the GUI: the form, filters, graph, saved searches, review."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from thesisagents.core.diagnostics import PaperRelation, RelationKind
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.library import LibraryPage
from thesisagents.gui.widgets import citation_graph
from thesisagents.gui.widgets.citation_graph import CitationGraph, GraphNode
from thesisagents.gui.widgets.library_tabs import DuplicatesDialog
from thesisagents.gui.widgets.paper_editor import PaperEditor, split_tags
from thesisagents.library import Library


def _paper(source_id: str, title: str, **fields) -> Paper:
    defaults = {
        "source": "arxiv", "authors": ("Ada Lovelace",), "year": 2020, "venue": None,
        "abstract": "", "url": f"https://example.org/{source_id}",
    }
    defaults.update(fields)
    return Paper(source_id=source_id, title=title, **defaults)


OLD = _paper("1", "Graph attention networks", doi="10.1/a", year=2018, citation_count=9000)
NEW = _paper("2", "Sparse attention revisited", doi="10.1/b", year=2023)
LONE = _paper("3", "Protein folding at scale", doi="10.1/c", year=2021)


@pytest.fixture
def path(tmp_path: Path) -> Path:
    file = tmp_path / "thesis.db"
    with Library(file) as library:
        library.add_papers(
            [OLD, NEW, LONE],
            relations=[PaperRelation(
                OLD.dedup_key(), NEW.dedup_key(), RelationKind.CITED_BY, "openalex", 1
            )],
        )
    return file


@pytest.fixture
def page(qtbot, path):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path(str(path))
    _working(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    return page


def _working(qtbot, page: LibraryPage, start) -> None:
    """Run ``start`` and wait until the page is idle again."""
    with qtbot.waitSignal(page.busy_changed, timeout=8000, check_params_cb=lambda b: not b):
        start()


def _titles(page: LibraryPage) -> list[str]:
    model = page.papers_model()
    return [model.item(row, 0).text() for row in range(model.rowCount())]


def _select(page: LibraryPage, *titles: str) -> None:
    keys = {p.dedup_key() for p in (OLD, NEW, LONE) if p.title in titles}
    page._select_keys(keys)  # noqa: SLF001
    assert {e.paper.title for e in page.selected_entries()} == set(titles)


def _stored(path: Path, title: str):
    with Library(path) as library:
        return next(e for e in library.entries() if e.paper.title == title)


# --- the form ------------------------------------------------------------------------


@pytest.mark.parametrize(("text", "tags"), [
    ("a, b", ("a", "b")), ("第二章，待引用、重要", ("第二章", "待引用", "重要")), (" , ,", ()),
    ("a, a", ("a",)),
])
def test_tags_are_split_at_commas_of_every_kind(text, tags):
    assert split_tags(text) == tags


def test_saving_the_form_stores_tags_note_and_status(qtbot, page, path):
    _select(page, OLD.title)
    editor = page.editor()
    editor.tags_input().setText("chapter 2, key")
    editor.note_input().setPlainText("cite in 2.3")
    editor.status_combo().setCurrentIndex(editor.status_combo().findData("read"))
    _working(qtbot, page, editor.button("save").click)
    entry = _stored(path, OLD.title)
    assert (entry.tags, entry.note, entry.status) == (("chapter 2", "key"), "cite in 2.3", "read")
    # The row shows it and stays selected.
    assert [e.paper.title for e in page.selected_entries()] == [OLD.title]
    assert page.editor().tags_input().text() == "chapter 2, key"
    row = _titles(page).index(OLD.title)
    assert page.papers_model().item(row, 2).text() == "Read"
    assert page.papers_model().item(row, 3).text() == "chapter 2, key"
    # Removing a tag from the text removes it from the paper.
    editor.tags_input().setText("KEY")
    _working(qtbot, page, editor.button("save").click)
    assert _stored(path, OLD.title).tags == ("key",)


def test_several_papers_get_tags_added_and_keep_their_notes(qtbot, page, path):
    _select(page, OLD.title)
    page.editor().note_input().setPlainText("mine")
    page.editor().tags_input().setText("first")
    _working(qtbot, page, page.editor().button("save").click)
    _select(page, OLD.title, LONE.title)
    editor = page.editor()
    assert editor.note_input().isHidden()
    editor.tags_input().setText("both")
    _working(qtbot, page, editor.button("save").click)
    assert _stored(path, OLD.title).tags == ("both", "first")
    assert _stored(path, OLD.title).note == "mine"
    assert _stored(path, LONE.title).tags == ("both",)


def test_screening_decisions_are_recorded_and_taken_back(qtbot, page, path):
    _select(page, OLD.title)
    editor = page.editor()
    editor.reason_input().setText("off topic")
    _working(qtbot, page, editor.button("exclude").click)
    decision = _stored(path, OLD.title).screening[0]
    assert (decision.stage, decision.decision, decision.reason) == (
        "title_abstract", "exclude", "off topic"
    )
    row = _titles(page).index(OLD.title)
    assert page.papers_model().item(row, 4).text() == "Title and abstract: Exclude"
    assert "Records excluded: 1" in page.review_tab().text()
    assert "off topic: 1" in page.review_tab().text()
    _working(qtbot, page, page.editor().button("").click)
    assert _stored(path, OLD.title).screening == ()


def test_an_edit_the_library_refuses_is_explained(qtbot, page, path):
    _select(page, OLD.title)
    editor = page.editor()
    editor.stage_combo().setCurrentIndex(1)
    editor.reason_input().clear()
    _working(qtbot, page, editor.button("exclude").click)
    assert "needs a reason" in page.status_text()
    assert _stored(path, OLD.title).screening == ()
    assert editor.button("exclude").isEnabled()


def test_the_form_is_off_without_a_selection(qtbot):
    editor = PaperEditor("en")
    qtbot.addWidget(editor)
    asked = []
    editor.requested.connect(asked.append)
    assert not editor.isEnabled()
    editor._save()  # noqa: SLF001
    editor._decide("include")  # noqa: SLF001
    assert asked == []


def test_results_arrive_on_the_main_thread(qtbot, page):
    seen = []

    def done(_value):
        seen.append(threading.current_thread() is threading.main_thread())
        return "done"

    _working(qtbot, page, lambda: page.run_edit(lambda library: len(library), done))
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen == [True]
    assert page.status_text() == "done"


def test_no_worker_signal_is_connected_to_a_lambda():
    """Such a connection dies with the worker, and its result is lost now and
    then: four of these tests timed out before it was found."""
    import re

    root = Path(__file__).resolve().parents[2] / "thesisagents" / "gui"
    offenders = [
        f"{file.name}: {match.group(0)}"
        for file in root.rglob("*.py")
        for match in re.finditer(
            r"signals\.\w+\.connect\(\s*lambda", file.read_text(encoding="utf-8")
        )
    ]
    assert offenders == []


# --- filters -----------------------------------------------------------------------------


def test_filters_narrow_the_list_and_what_is_sent_on(qtbot, page, path):
    with Library(path) as library:
        ids = {e.paper.title: e.paper_id for e in library.entries()}
        library.add_tags([ids[OLD.title], ids[NEW.title]], ["keep"])
        library.set_reading_status([ids[NEW.title]], "read")
    _working(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    combo = page.filter_combo("tag")
    assert [combo.itemText(i) for i in range(combo.count())] == ["Any", "keep (2)"]
    combo.setCurrentIndex(1)
    _working(qtbot, page, lambda: combo.activated.emit(1))
    assert set(_titles(page)) == {OLD.title, NEW.title}
    assert combo.currentData() == "keep"
    status = page.filter_combo("status")
    status.setCurrentIndex(status.findData("read"))
    _working(qtbot, page, lambda: status.activated.emit(status.currentIndex()))
    assert _titles(page) == [NEW.title]
    sent = []
    page.collection_ready.connect(sent.append)
    page.action_button("send").click()
    assert [p.title for p in sent[0].papers] == [NEW.title]


def test_a_filter_whose_last_paper_left_stays_visible(qtbot, page, path):
    _select(page, OLD.title)
    page.editor().tags_input().setText("only")
    _working(qtbot, page, page.editor().button("save").click)
    combo = page.filter_combo("tag")
    combo.setCurrentIndex(combo.findData("only"))
    _working(qtbot, page, lambda: combo.activated.emit(combo.currentIndex()))
    _select(page, OLD.title)
    page.editor().tags_input().setText("")
    _working(qtbot, page, page.editor().button("save").click)
    assert _titles(page) == []
    assert combo.currentData() == "only"


# --- deleting, merging, importing ----------------------------------------------------------


@pytest.mark.parametrize("answer", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes])
def test_deleting_asks_first(qtbot, page, path, monkeypatch, answer):
    asked = []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: asked.append(box.text()) or answer
    )
    _select(page, OLD.title)
    if answer == QMessageBox.StandardButton.Yes:
        _working(qtbot, page, page.action_button("delete").click)
        assert OLD.title not in _titles(page)
        assert page.status_text() == "1 paper(s) deleted."
    else:
        page.action_button("delete").click()
        assert OLD.title in _titles(page)
    assert "cannot be undone" in asked[0]


def test_selected_papers_are_merged_after_asking(qtbot, page, path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda _box: QMessageBox.StandardButton.Yes)
    _select(page, OLD.title)
    assert not page.action_button("merge").isEnabled()
    _select(page, OLD.title, LONE.title)
    assert page.action_button("merge").isEnabled()
    _working(qtbot, page, page.action_button("merge").click)
    assert len(_titles(page)) == 2


def test_duplicates_are_offered_and_merged(qtbot, page, path):
    with Library(path) as library:
        library.add_papers([_paper("1b", "Graph Attention Networks.", doi="10.1/a2", year=2017)])
    _working(qtbot, page, page.action_button("duplicates").click)
    dialog = page.duplicates_dialog()
    assert len(dialog.boxes(0)) == 2
    _working(qtbot, page, dialog.merge_button(0).click)
    assert len(_titles(page)) == 3
    assert not dialog.merge_button(0).isEnabled()
    dialog.close()


def test_unticked_papers_are_not_merged(qtbot, page):
    entries = page.snapshot().entries[:2]
    dialog = DuplicatesDialog([entries], "en")
    qtbot.addWidget(dialog)
    asked = []
    dialog.merge_requested.connect(asked.append)
    dialog.boxes(0)[1].setChecked(False)
    dialog.merge_button(0).click()
    assert asked == []


def test_no_duplicates_says_so(qtbot, page):
    _working(qtbot, page, page.action_button("duplicates").click)
    assert page.status_text() == "No duplicates found."
    page.duplicates_dialog().close()


def test_a_bibliography_is_imported_into_a_new_library(qtbot, tmp_path):
    file = tmp_path / "zotero.bib"
    file.write_text(
        "@misc{a, title={One}, year={2001}}\n@misc{b, author={Nobody}}", encoding="utf-8"
    )
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.import_bibliography(str(file))
    assert "library" in page.status_text().lower()  # no path given yet
    page.set_library_path(str(tmp_path / "new.db"))
    _working(qtbot, page, lambda: page.import_bibliography(str(file)))
    assert page.status_text() == "1 added, 0 already there, 1 skipped."
    assert _titles(page) == ["One"]
    _working(qtbot, page, lambda: page.import_bibliography(str(tmp_path / "none.bib")))
    assert "cannot read" in page.status_text()


# --- saved searches ---------------------------------------------------------------------------


def test_the_search_form_is_saved_run_and_deleted(qtbot, path, monkeypatch):
    async def fake(query, **_kwargs):
        return PaperCollection(query=query, papers=(
            OLD, _paper("9", "Brand new", doi="10.1/new"),
        ))

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", fake)
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    page = window.library_page()
    page.set_library_path(str(path))
    _working(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    tab = page.saved_tab()
    tab.name_input().setText("mine")
    tab.save_button().click()
    assert "keyword" in page.status_text().lower() or page.status_text()
    assert tab.table().rowCount() == 0  # the search form is empty
    window.search_page().set_query_text("graph attention")
    tab.name_input().setText("mine")
    _working(qtbot, page, tab.save_button().click)
    assert tab.table().item(0, 1).text() == "graph attention"
    tab.table().selectRow(0)
    _working(qtbot, page, tab.run_button().click)
    qtbot.waitUntil(lambda: "1 new of 2" in page.status_text(), timeout=3000)
    assert [e.paper.title for e in page.selected_entries()] == ["Brand new"]
    assert tab.table().item(0, 3).text() == "1"
    tab.table().selectRow(0)
    _working(qtbot, page, tab.delete_button().click)
    assert tab.table().rowCount() == 0
    with Library(path) as library:
        assert len(library) == 4


def test_the_query_of_the_search_form(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    assert window.search_page().current_query() is None
    window.search_page().set_query_text("graphs")
    query = window.search_page().current_query()
    assert isinstance(query, Query)
    assert query.keywords == "graphs"


# --- citation graph -------------------------------------------------------------------------------


def test_the_graph_shows_linked_papers_and_follows_the_selection(qtbot, page):
    graph = page.graph()
    assert graph.node_keys() == {OLD.dedup_key(), NEW.dedup_key()}
    assert graph.edge_count() == 1
    _select(page, OLD.title)
    assert graph.selected() == OLD.dedup_key()
    graph.node_clicked.emit(NEW.dedup_key())
    assert [e.paper.title for e in page.selected_entries()] == [NEW.title]
    _select(page, LONE.title)
    assert graph.selected() == ""


def test_papers_stand_in_columns_by_year():
    nodes = [
        GraphNode("new", "N", 2023), GraphNode("old", "O", 1999), GraphNode("none", "X", None),
        GraphNode("old2", "P", 1999),
    ]
    places = citation_graph.layout(nodes, [("new", "old"), ("new", "gone"), ("old", "old")])
    assert places["none"][0] < places["old"][0] < places["new"][0]
    assert places["old"][0] == places["old2"][0]
    assert places["old"][1] != places["old2"][1]
    assert places == citation_graph.layout(list(reversed(nodes)), [("new", "old")])


def test_layout_of_nothing_and_of_many():
    assert citation_graph.layout([], []) == {}
    nodes = [GraphNode(str(i), f"T{i}", 2000 + i % 20) for i in range(600)]
    edges = [(str(i), str(i // 2)) for i in range(1, 600)]
    places = citation_graph.layout(nodes, edges)
    assert len(set(places.values())) == 600


@pytest.mark.parametrize(("citations", "expected"), [
    (None, 6.0), (0, 6.0), (-5, 6.0), (10**12, 18.0),
])
def test_node_sizes_are_bounded(citations, expected):
    assert citation_graph.radius(citations) == pytest.approx(expected)


def test_clicking_a_node_reports_it(qtbot):
    graph = CitationGraph()
    qtbot.addWidget(graph)
    graph.resize(400, 300)
    graph.show()
    qtbot.waitExposed(graph)
    graph.show_graph([GraphNode("a", "A", 2000), GraphNode("b", "B", 2010)], [("b", "a")])
    graph.fit()
    heard = []
    graph.node_clicked.connect(heard.append)
    at = graph.mapFromScene(graph.node_item("a").scenePos())
    from PySide6.QtCore import Qt

    qtbot.mouseClick(graph.viewport(), Qt.MouseButton.LeftButton, pos=at)
    assert heard == ["a"]
    assert graph.selected() == "a"


# --- review ------------------------------------------------------------------------------


def test_the_diagram_is_saved_in_the_interface_language(qtbot, path, tmp_path):
    page = LibraryPage(ui_language="zh-tw")
    qtbot.addWidget(page)
    page.save_diagram(str(tmp_path / "early.svg"))
    assert not (tmp_path / "early.svg").exists()
    page.set_library_path(str(path))
    _working(qtbot, page, page._on_open_clicked)  # noqa: SLF001
    page.save_diagram(str(tmp_path / "flow.svg"))
    assert "納入回顧的研究" in (tmp_path / "flow.svg").read_text(encoding="utf-8")
    page.save_diagram(str(tmp_path))
    assert page.status_text() != "已儲存。"

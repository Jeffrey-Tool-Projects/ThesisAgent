"""Tests for the Library page (``progress.md`` #20).

Every test builds a real library file under ``tmp_path`` with the
``Library`` API, so the page is checked against the same SQLite schema the
CLI and MCP write. No network is used.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thesisagents.core.diagnostics import PaperRelation, RelationKind
from thesisagents.core.export_validation import Verdict, VerificationStatus
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.library import LibraryPage, load_snapshot
from thesisagents.gui.pages.settings import settings_store
from thesisagents.library import Library

SEED = Paper(
    source="arxiv", source_id="1", title="Graph attention networks", authors=("Ada",),
    year=2018, venue=None, abstract="", url="https://example.org/gat", doi="10.1000/gat",
)
CITER = Paper(
    source="openalex", source_id="W2", title="Sparse <b>attention</b> revisited",
    authors=("Bo",), year=2023, venue=None, abstract="", url="https://example.org/sparse",
)
OTHER = Paper(
    source="arxiv", source_id="3", title="Protein folding at scale", authors=("Cy",),
    year=2021, venue=None, abstract="", url="https://example.org/fold",
)


@pytest.fixture
def library_file(tmp_path: Path) -> Path:
    """A library with two searches, one citation link and one DOI verdict."""
    path = tmp_path / "thesis.db"
    with Library(path) as library:
        library.add_papers(
            [SEED, CITER],
            keywords="graph attention",
            relations=[
                PaperRelation(
                    SEED.dedup_key(), CITER.dedup_key(), RelationKind.CITED_BY, "openalex", 1
                )
            ],
        )
        library.add_collection(
            PaperCollection(Query("protein folding", ("arxiv",)), (OTHER,))
        )
        library.record_verdict("doi", "10.1000/gat", Verdict(VerificationStatus.OK))
    return path


def _open(page: LibraryPage, qtbot, path: Path, query: str = "") -> None:
    page.set_library_path(str(path))
    page._query_input.setText(query)  # noqa: SLF001
    with qtbot.waitSignal(page.busy_changed, timeout=5000, check_params_cb=lambda b: not b):
        page._on_open_clicked()  # noqa: SLF001


def test_snapshot_reads_counts_runs_links_and_verdicts(library_file):
    snapshot = load_snapshot(str(library_file))
    assert snapshot.stats.papers == 3
    assert snapshot.stats.runs == 2
    assert len(snapshot.relations) == 1
    assert [v.status for v in snapshot.verdicts[SEED.dedup_key()]] == ["ok"]
    assert len(snapshot.collection.papers) == 3


def test_opening_fills_the_overview_and_both_tabs(qtbot, library_file):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    _open(page, qtbot, library_file)
    assert page.stat_text("papers") == "3"
    assert page.stat_text("runs") == "2"
    assert page.stat_text("relations") == "1"
    assert page.stat_text("years") == "2018 – 2023"
    assert "arxiv 2" in page.stat_text("sources")
    assert page.stat_text("checks") == "ok 1"
    assert page.papers_model().rowCount() == 3
    assert page.runs_model().rowCount() == 2
    assert "Showing 3 of 3 papers" in page.status_text()


def test_the_find_box_narrows_the_list(qtbot, library_file):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    _open(page, qtbot, library_file, query="protein")
    titles = [page.papers_model().item(r, 0).text() for r in range(page.papers_model().rowCount())]
    assert titles == [OTHER.title]


def test_selecting_a_paper_shows_its_links_and_checks(qtbot, library_file):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    _open(page, qtbot, library_file)
    model = page.papers_model()
    row = next(r for r in range(model.rowCount()) if model.item(r, 0).text() == SEED.title)
    page.select_paper(row)
    detail = page.detail_text()
    assert "Cited by (1 in the library)" in detail
    assert CITER.title in detail                  # shown as text, not rendered as bold
    assert "DOI 10.1000/gat: ok" in detail
    assert "Cites (0 in the library)" in detail


def test_a_missing_file_is_reported_and_not_created(qtbot, tmp_path):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    missing = tmp_path / "nope.db"
    _open(page, qtbot, missing)
    assert page.status_text().startswith("Could not open the library")
    assert not missing.exists()


def test_send_hands_the_listed_papers_on(qtbot, library_file):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    _open(page, qtbot, library_file, query="attention")
    with qtbot.waitSignal(page.collection_ready) as signal:
        page._on_send_clicked()  # noqa: SLF001
    assert {p.title for p in signal.args[0].papers} == {SEED.title, CITER.title}
    assert "2 papers sent" in page.status_text()


def test_the_window_wires_the_library_page(qtbot, library_file):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.search_page().set_library_path(str(library_file))
    library = window.library_page()
    assert library.library_path() == str(library_file)
    _open(library, qtbot, library_file)
    library._on_send_clicked()  # noqa: SLF001
    assert window.enrich_page().table_model().rowCount() == 3
    assert window.deck_page().collection() is not None
    assert window.nav_rail().button_tooltip(2) == "Enrich  ·  3"


def test_library_form_round_trips(qtbot):
    page = LibraryPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_library_path("C:/data/thesis.db")
    page._query_input.setText("graph")  # noqa: SLF001
    page.save_form(settings_store())
    again = LibraryPage(ui_language="en")
    qtbot.addWidget(again)
    again.restore_form(settings_store())
    assert again.library_path() == "C:/data/thesis.db"
    assert again._query_input.text() == "graph"  # noqa: SLF001

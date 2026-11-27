"""Tests for cancelling work, snowball bounds, the results table and saved forms.

Covers progress items #19 (cancel a running search / enrichment), #21
(snowball bounds in the GUI), #22 (sort, filter, tick a subset, row menu)
and #26 (form values remembered across starts). No test makes a network
call: the search, the snowball and the enrichment backends are replaced.
"""

from __future__ import annotations

import asyncio

import pytest
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtGui import QGuiApplication

from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.core.snowball import SnowballResult
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.models.papers_table_model import (
    SORT_ROLE,
    PaperFilterProxy,
    PapersTableModel,
)
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.pages.enrich import EnrichPage
from thesisagents.gui.pages.search import SearchPage
from thesisagents.gui.pages.settings import settings_store
from thesisagents.gui.widgets.paper_actions import paper_menu
from thesisagents.gui.widgets.snowball_bounds import SnowballBounds
from thesisagents.gui.workers import AsyncWorker

SEARCH = "thesisagents.gui.pages.search"


def _paper(idx: int, *, source: str = "arxiv", year: int | None = 2024, **fields) -> Paper:
    return Paper(
        source=source, source_id=str(idx), title=fields.pop("title", f"Paper {idx}"),
        authors=("Ada Author",), year=year, venue=None, abstract="",
        url=f"https://example.org/{idx}", **fields,
    )


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(Query("attention", ("arxiv",)), papers)


# --- #19 cancellable worker ---------------------------------------------------


def test_cancel_stops_a_waiting_coroutine(qtbot):
    async def slow() -> str:
        await asyncio.sleep(30)
        return "too late"

    worker = AsyncWorker(slow)
    finished: list[object] = []
    worker.signals.finished.connect(finished.append)
    with qtbot.waitSignal(worker.signals.cancelled, timeout=5000):
        QThreadPool.globalInstance().start(worker)
        qtbot.wait(100)
        worker.cancel()
    assert finished == []


def test_cancel_before_start_never_runs_the_work(qtbot):
    ran: list[bool] = []

    async def work() -> None:
        await asyncio.sleep(0)
        ran.append(True)

    worker = AsyncWorker(work)
    worker.cancel()
    with qtbot.waitSignal(worker.signals.cancelled, timeout=5000):
        QThreadPool.globalInstance().start(worker)
    assert ran == []


def test_an_uncancelled_worker_still_finishes(qtbot):
    async def quick() -> int:
        return 7

    worker = AsyncWorker(quick)
    with qtbot.waitSignal(worker.signals.finished, timeout=5000) as signal:
        QThreadPool.globalInstance().start(worker)
    assert signal.args == [7]


@pytest.fixture
def page(qtbot, monkeypatch):
    """A Search page whose search returns three papers (or blocks on demand)."""
    state = {"block": False}

    async def fake_run_search(query, **_kwargs):
        if state["block"]:
            await asyncio.sleep(30)
        return _collection(
            _paper(1, title="Graph attention networks", year=2018, citation_count=9),
            _paper(2, source="openalex", title="Transformers for vision", year=2021),
            _paper(3, title="Sparse attention", year=None, citation_count=40),
        )

    async def fake_shutdown():
        return None

    monkeypatch.setattr(f"{SEARCH}.run_search", fake_run_search)
    monkeypatch.setattr(f"{SEARCH}.shutdown_clients", fake_shutdown)
    widget = SearchPage(ui_language="en")
    qtbot.addWidget(widget)
    widget.set_query_text("attention")
    widget.state = state
    return widget


def _search(page: SearchPage, qtbot) -> None:
    page._on_search_clicked()  # noqa: SLF001
    qtbot.waitUntil(lambda: page.papers_model().rowCount() == 3, timeout=5000)


def test_cancelling_a_search_keeps_the_previous_results(page, qtbot):
    _search(page, qtbot)
    page.state["block"] = True
    page._on_search_clicked()  # noqa: SLF001
    assert page._cancel_button.isVisibleTo(page)  # noqa: SLF001
    qtbot.wait(100)
    with qtbot.waitSignal(page.busy_changed, timeout=5000) as signal:
        page._on_cancel_clicked()  # noqa: SLF001
    assert signal.args == [False]
    assert "cancelled" in page.status_text()
    assert page.papers_model().rowCount() == 3
    assert not page._cancel_button.isVisibleTo(page)  # noqa: SLF001
    assert page._search_button.isEnabled()  # noqa: SLF001


# --- #21 snowball bounds ------------------------------------------------------


def test_snowball_bounds_default_to_the_cli_values(page):
    assert page.snowball_bounds() == SnowballBounds(
        seeds=5, depth=1, max_per_seed=20, max_total=20, min_relevance=None,
    )


def test_the_search_passes_the_chosen_bounds_to_the_snowball(page, qtbot, monkeypatch):
    seen: dict[str, object] = {}

    async def fake_snowball(seeds, **kwargs):
        seen.update(kwargs, seeds=seeds)
        return SnowballResult(seeds=tuple(seeds), discovered=(), relations=())

    monkeypatch.setattr(f"{SEARCH}.snowball", fake_snowball)
    page.snowball_combo().setCurrentIndex(1)                       # references
    page.set_snowball_bounds(
        SnowballBounds(seeds=2, depth=2, max_per_seed=7, max_total=30, min_relevance=0.4)
    )
    _search(page, qtbot)
    assert len(seen["seeds"]) == 2
    assert (seen["depth"], seen["max_per_seed"], seen["max_total"]) == (2, 7, 30)
    assert seen["min_relevance"] == pytest.approx(0.4)


def test_the_advanced_section_is_collapsed_until_ticked(page):
    page.show()
    assert not page._snowball_advanced.isVisible()  # noqa: SLF001
    page._snowball_advanced_check.setChecked(True)  # noqa: SLF001
    assert page._snowball_advanced.isVisible()  # noqa: SLF001


# --- #22 results table --------------------------------------------------------


def test_every_paper_starts_ticked_and_unticking_narrows_what_is_sent_on(page, qtbot):
    _search(page, qtbot)
    model = page.papers_model()
    assert model.checked_count() == 3
    with qtbot.waitSignal(page.collection_ready) as signal:
        model.setData(model.index(1, 0), Qt.CheckState.Unchecked.value, Qt.CheckStateRole)
    sent = signal.args[0]
    assert [p.source_id for p in sent.papers] == ["1", "3"]
    assert [p.source_id for p in page.selected_collection().papers] == ["1", "3"]
    assert "2 of 3 ticked" in page._selection_label.text()  # noqa: SLF001


def test_the_filter_hides_rows_but_never_unticks_them(page, qtbot):
    _search(page, qtbot)
    page._filter_input.setText("attention")  # noqa: SLF001
    assert page._proxy.rowCount() == 2  # noqa: SLF001
    assert page.papers_model().checked_count() == 3
    page._tick_shown(False)  # noqa: SLF001  # only the two shown rows
    assert [p.source_id for p in page.selected_collection().papers] == ["2"]


def test_the_source_filter_lists_the_result_sources(page, qtbot):
    _search(page, qtbot)
    combo = page._filter_source  # noqa: SLF001
    assert [combo.itemData(i) for i in range(combo.count())] == [None, "arxiv", "openalex"]
    combo.setCurrentIndex(2)
    assert page._proxy.rowCount() == 1  # noqa: SLF001


def test_results_keep_their_ranked_order_until_a_header_is_clicked(page, qtbot):
    _search(page, qtbot)
    proxy = page._proxy  # noqa: SLF001
    assert [proxy.index(r, 0).data() for r in range(3)][0] == "Graph attention networks"
    page.table().sortByColumn(2, Qt.SortOrder.DescendingOrder)     # year
    years = [proxy.index(r, 2).data() for r in range(3)]
    assert years == [2021, 2018, "—"]                              # a missing year sorts last


def test_sort_keys_are_numbers_for_year_and_citations():
    model = PapersTableModel()
    model.set_collection(_collection(_paper(1, year=None, citation_count=None)))
    assert model.index(0, 2).data(SORT_ROLE) == -1
    assert model.index(0, 5).data(SORT_ROLE) == -1
    assert model.index(0, 0).data(SORT_ROLE) == "paper 1"


def test_title_column_is_checkable():
    model = PapersTableModel()
    model.set_collection(_collection(_paper(1)))
    assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsUserCheckable
    assert not model.flags(model.index(0, 1)) & Qt.ItemFlag.ItemIsUserCheckable


def test_filter_matches_every_word_across_fields():
    model = PapersTableModel()
    model.set_collection(_collection(_paper(1, doi="10.1/abc"), _paper(2)))
    proxy = PaperFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_text("ada 10.1/ABC")
    assert proxy.rowCount() == 1


def test_row_menu_copies_doi_and_bibtex_and_disables_missing_links(page, qtbot):
    paper = _paper(9, title="Attention", doi="10.1000/xyz", year=2020)
    menu = paper_menu(paper, "en", page)
    actions = {action.text(): action for action in menu.actions() if action.text()}
    assert not actions["Open PDF"].isEnabled()
    actions["Copy DOI"].trigger()
    assert QGuiApplication.clipboard().text() == "10.1000/xyz"
    actions["Copy BibTeX"].trigger()
    assert QGuiApplication.clipboard().text().startswith("@")
    assert paper.bibtex_key() in QGuiApplication.clipboard().text()


def test_the_export_writes_only_the_ticked_papers(page, qtbot, monkeypatch):
    _search(page, qtbot)
    page.papers_model().set_checked(0, False)
    written: dict[str, object] = {}

    def fake_export(collection, options, **_kwargs):
        written["ids"] = [p.source_id for p in collection.papers]
        return {}

    monkeypatch.setattr(f"{SEARCH}.export_collection", fake_export)
    monkeypatch.setattr(
        f"{SEARCH}.QFileDialog.getExistingDirectory", lambda *_a, **_k: "out"
    )
    page._on_export_clicked()  # noqa: SLF001
    qtbot.waitUntil(lambda: "ids" in written, timeout=5000)
    assert written["ids"] == ["2", "3"]


# --- #19 enrichment cancel and the held collection ------------------------------


def _summary(language, model) -> PaperSummary:
    return PaperSummary(language=language, model=model, raw_text_chars=1, core_observation="x")


@pytest.fixture
def slow_enrichment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    async def slow_fetch(_url, source="intelligence"):
        await asyncio.sleep(30)

    monkeypatch.setattr("thesisagents.intelligence.pdf.fetch_and_extract", slow_fetch)
    monkeypatch.setattr(
        "thesisagents.intelligence.summarise.summarise_with",
        lambda settings, paper, text, language, chars: _summary(language, settings.model),
    )


def _enrich_papers() -> PaperCollection:
    return _collection(
        _paper(1, pdf_url="https://example.org/1.pdf"),
        _paper(2, pdf_url="https://example.org/2.pdf"),
    )


def test_cancelling_enrichment_keeps_every_paper(qtbot, slow_enrichment):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_enrich_papers())
    page._on_enrich_clicked()  # noqa: SLF001
    qtbot.wait(100)
    with qtbot.waitSignal(page.collection_ready, timeout=5000) as signal:
        page._on_cancel_clicked()  # noqa: SLF001
    assert len(signal.args[0].papers) == 2
    assert "Stopped after 0 of 2" in page.status_text()
    assert page.table_model().item(1, 2).text() == "not run (stopped)"
    assert not page.is_running()


def test_a_collection_arriving_mid_run_is_applied_after_it(qtbot, slow_enrichment):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_enrich_papers())
    page._on_enrich_clicked()  # noqa: SLF001
    page.set_collection(_collection(_paper(5)))
    assert page.table_model().rowCount() == 2                     # held, not applied
    with qtbot.waitSignal(page.busy_changed, timeout=5000):
        page._on_cancel_clicked()  # noqa: SLF001
    assert page.table_model().rowCount() == 1                     # applied after the run


# --- #26 remembered forms -----------------------------------------------------


def test_search_form_round_trips(page, qtbot):
    page._sources_widget.set_selected(("arxiv", "dblp"))  # noqa: SLF001
    page._snowball_advanced_check.setChecked(True)  # noqa: SLF001
    page.set_snowball_bounds(SnowballBounds(seeds=3, max_total=40, min_relevance=0.25))
    page.snowball_combo().setCurrentIndex(2)
    page.set_library_path("C:/data/thesis.db")
    page.save_form(settings_store())

    again = SearchPage(ui_language="en")
    qtbot.addWidget(again)
    again.restore_form(settings_store())
    assert again._query_input.text() == "attention"  # noqa: SLF001
    assert again._sources_widget.selected() == ("arxiv", "dblp")  # noqa: SLF001
    assert again.snowball_combo().currentData() == "cited_by"
    assert again.snowball_bounds() == SnowballBounds(seeds=3, max_total=40, min_relevance=0.25)
    assert again._library_input.text() == "C:/data/thesis.db"  # noqa: SLF001


def test_restoring_an_empty_store_keeps_the_defaults(qtbot):
    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    before = page._sources_widget.selected()  # noqa: SLF001
    page.restore_form(settings_store())
    assert page._sources_widget.selected() == before  # noqa: SLF001
    assert page.snowball_bounds() == SnowballBounds()


def test_deck_form_round_trips_except_the_filename(qtbot):
    deck = DeckPage(ui_language="en")
    qtbot.addWidget(deck)
    deck.format_checkbox("md").setChecked(True)
    deck.format_checkbox("xlsx").setChecked(False)
    deck._filename_stem_input.setText("one-off")  # noqa: SLF001
    deck.verify_identifiers_checkbox().setChecked(False)
    deck.save_form(settings_store())

    again = DeckPage(ui_language="en")
    qtbot.addWidget(again)
    again.restore_form(settings_store())
    assert again.format_checkbox("md").isChecked()
    assert not again.format_checkbox("xlsx").isChecked()
    assert not again.verify_identifiers_checkbox().isChecked()
    assert again._filename_stem_input.text() == ""  # noqa: SLF001


def test_enrich_form_round_trips(qtbot):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    combo = page._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData("codex-cli"))
    page._model_input.setText("my-model")  # noqa: SLF001
    page._language_combo.setCurrentIndex(page._language_combo.findData("ja"))  # noqa: SLF001
    page.save_form(settings_store())
    again = EnrichPage(ui_language="en")
    qtbot.addWidget(again)
    again.restore_form(settings_store())
    assert again._provider_combo.currentData() == "codex-cli"  # noqa: SLF001
    assert again._model_input.text() == "my-model"  # noqa: SLF001
    assert again._language_combo.currentData() == "ja"  # noqa: SLF001


def test_closing_the_window_remembers_the_query(qtbot):
    first = MainWindow(ui_language="en")
    qtbot.addWidget(first)
    first.search_page().set_query_text("graph neural networks")
    first.close()
    second = MainWindow(ui_language="en")
    qtbot.addWidget(second)
    assert second.search_page()._query_input.text() == "graph neural networks"  # noqa: SLF001


# --- #29 local PDFs ------------------------------------------------------------


def test_local_pdfs_fill_the_results_and_copy_into_the_deck_folder(qtbot, tmp_path):
    pytest.importorskip("pypdf", reason="install thesisagents[intelligence]")
    from tests.test_local_pdf import _pdf

    pdf = _pdf(tmp_path / "chapter.pdf", "Graph Attention in Practice", "Abstract", "Text.")
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.deck_page()._out_dir_input.setText(str(tmp_path / "out"))  # noqa: SLF001
    page = window.search_page()
    with qtbot.waitSignal(page.collection_ready, timeout=10000) as signal:
        page.read_local_pdfs([str(pdf)])
    assert [p.source for p in signal.args[0].papers] == ["local"]
    assert page.papers_model().rowCount() == 1
    assert page.status_text().startswith("Read 1 local PDF(s).")
    assert list((tmp_path / "out" / "pdfs").glob("*.pdf"))
    assert window.enrich_page().table_model().rowCount() == 1
    assert page._local_button.isEnabled()  # noqa: SLF001


def test_an_unreadable_local_pdf_is_reported(qtbot, tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_output_dir_provider(lambda: str(tmp_path / "out"))
    page.read_local_pdfs([str(bad)])
    qtbot.waitUntil(lambda: "not a PDF" in page.status_text(), timeout=10000)
    assert page._search_button.isEnabled()  # noqa: SLF001

"""Tests for the PDF download stage with its access switch (``progress.md``
#24) and for switching the interface language without a restart (#25).

No PDF is downloaded: ``download_pdfs`` and the HTTP client shutdown are
replaced, the rest of the stage (the IEEE gate, the counts, the Deck page
wiring) runs for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.core.pdf_download import PdfDownloadResult
from thesisagents.gui import main_window as main_window_module
from thesisagents.gui import pdf_stage
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.pages.settings import SettingsPage, saved_vpn_access
from thesisagents.gui.pdf_stage import PdfStageReport, needs_institutional_access


def _paper(idx: int, *, source: str = "arxiv", pdf_url: str | None = None) -> Paper:
    return Paper(
        source=source, source_id=str(idx), title=f"Paper {idx}", authors=("Ada",),
        year=2024, venue=None, abstract="", url=f"https://example.org/{idx}",
        pdf_url=pdf_url or f"https://example.org/{idx}.pdf",
    )


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(Query("attention", ("arxiv",)), papers)


# --- #24 the access gate -------------------------------------------------------


@pytest.mark.parametrize(
    ("paper", "gated"),
    [
        (_paper(1, source="ieee"), True),
        (_paper(2, pdf_url="https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=1"), True),
        (_paper(3), False),
        (_paper(4, pdf_url="https://notieee.org/x.pdf"), False),
        (_paper(5, source="springer", pdf_url="https://link.springer.com/x.pdf"), False),
    ],
)
def test_only_ieee_needs_institutional_access(paper, gated):
    assert needs_institutional_access(paper) is gated


@pytest.fixture
def fake_download(monkeypatch):
    """Record the batch handed to ``download_pdfs``; every paper but #3 saves."""
    batches: list[list[str]] = []

    async def download(collection, out_dir, **_kwargs):
        batches.append([p.source_id for p in collection.papers])
        return [
            PdfDownloadResult(p.source_id, None if p.source_id == "3" else Path(out_dir), None)
            for p in collection.papers
        ]

    async def shutdown():
        return None

    monkeypatch.setattr(pdf_stage, "download_pdfs", download)
    monkeypatch.setattr(pdf_stage, "shutdown_clients", shutdown)
    return batches


def test_without_access_ieee_papers_are_held_back(fake_download, tmp_path):
    collection = _collection(_paper(1), _paper(2, source="ieee"), _paper(3))
    report = pdf_stage.run_pdf_stage(collection, tmp_path, vpn_access=False)
    assert fake_download == [["1", "3"]]
    assert (report.saved, report.skipped, report.held) == (1, 1, 1)
    assert report.folder == tmp_path / "pdfs"


def test_with_access_every_paper_is_attempted(fake_download, tmp_path):
    collection = _collection(_paper(1), _paper(2, source="ieee"))
    report = pdf_stage.run_pdf_stage(collection, tmp_path, vpn_access=True)
    assert fake_download == [["1", "2"]]
    assert report.held == 0


def test_an_all_ieee_batch_without_access_downloads_nothing(fake_download, tmp_path):
    report = pdf_stage.run_pdf_stage(_collection(_paper(1, source="ieee")), tmp_path,
                                     vpn_access=False)
    assert fake_download == []
    assert (report.saved, report.skipped, report.held) == (0, 0, 1)


def test_access_is_off_until_settings_say_otherwise(qtbot):
    assert saved_vpn_access() is False
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert not page.vpn_checkbox().isChecked()
    page.vpn_checkbox().setChecked(True)
    page.trigger_save()
    assert saved_vpn_access() is True


def test_deck_export_runs_the_pdf_stage_with_the_saved_access(qtbot, monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def fake_stage(collection, out_dir, *, vpn_access):
        seen.update(papers=len(collection.papers), out_dir=out_dir, vpn_access=vpn_access)
        return PdfStageReport(Path(out_dir) / "pdfs", saved=1, skipped=0, held=1)

    monkeypatch.setattr("thesisagents.gui.pages.deck.run_pdf_stage", fake_stage)
    monkeypatch.setattr(
        "thesisagents.gui.pages.deck.export_collection",
        lambda *_a, **_k: pytest.fail("no file format was ticked"),
    )
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1), _paper(2, source="ieee")))
    for fmt in ("pptx", "xlsx", "bib"):
        page.format_checkbox(fmt).setChecked(False)
    page.download_pdfs_checkbox().setChecked(True)
    page._out_dir_input.setText(str(tmp_path))  # noqa: SLF001
    with qtbot.waitSignal(page.busy_changed, timeout=5000, check_params_cb=lambda b: not b):
        page._on_export_clicked()  # noqa: SLF001
    assert seen == {"papers": 2, "out_dir": str(tmp_path), "vpn_access": False}
    assert page.files_model().item(0, 0).text() == "pdf"
    assert "PDFs: 1 saved, 0 not downloaded." in page.status_text()
    assert "1 IEEE PDFs left out" in page.status_text()
    assert page._open_folder_button.isEnabled()  # noqa: SLF001


def test_no_format_and_no_pdfs_is_refused(qtbot):
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1)))
    for fmt in ("pptx", "xlsx", "bib"):
        page.format_checkbox(fmt).setChecked(False)
    page._on_export_clicked()  # noqa: SLF001
    assert "format" in page.status_text().lower()


# --- #25 language switch without a restart ------------------------------------------


def _switch(window: MainWindow, qtbot, language: str) -> MainWindow:
    settings = window.settings_page()
    settings.language_combo().setCurrentIndex(settings.language_combo().findData(language))
    settings.trigger_save()
    replacement = main_window_module._REPLACEMENTS[-1]  # noqa: SLF001
    qtbot.addWidget(replacement)
    return replacement


def test_saving_a_new_language_rebuilds_the_window_with_the_work(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.show()
    result = _collection(_paper(1), _paper(2), _paper(3))
    window.search_page().show_results(result)
    window.search_page().papers_model().set_checked(1, False)
    window.search_page().set_query_text("attention")
    window.nav_rail().set_current(3)                              # Deck
    new = _switch(window, qtbot, "zh-tw")
    assert new is not window
    assert not window.isVisible()
    assert new.nav_rail().button_tooltip(0) == "搜尋"
    assert new.nav_rail().current() == 3
    assert new.search_page().papers_model().rowCount() == 3
    assert new.search_page().papers_model().unchecked_rows() == [1]
    assert new.search_page()._query_input.text() == "attention"  # noqa: SLF001
    assert new.deck_page().collection() is not None
    assert new.statusBar().currentMessage() == "設定已儲存並套用。"


def test_saving_the_same_language_keeps_the_window(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    before = len(main_window_module._REPLACEMENTS)  # noqa: SLF001
    window.settings_page().trigger_save()
    assert len(main_window_module._REPLACEMENTS) == before  # noqa: SLF001


def test_a_language_switch_waits_while_work_runs(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.search_page().busy_changed.emit(True)
    before = len(main_window_module._REPLACEMENTS)  # noqa: SLF001
    settings = window.settings_page()
    settings.language_combo().setCurrentIndex(settings.language_combo().findData("de"))
    settings.trigger_save()
    assert len(main_window_module._REPLACEMENTS) == before  # noqa: SLF001
    assert "next start" in window.statusBar().currentMessage()
    window.search_page().busy_changed.emit(False)


# --- #30 the Search page follows the access switch --------------------------------


def test_ieee_is_locked_out_of_searches_while_access_is_off(qtbot):
    from thesisagents.gui.pages.search import SearchPage

    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    page.show()
    sources = page._sources_widget  # noqa: SLF001
    assert sources.is_locked("ieee")
    assert not sources.box("ieee").isEnabled()
    assert "ieee" not in sources.selected()
    assert page._ieee_note.isVisible()  # noqa: SLF001
    sources.box("ieee").setChecked(True)          # even a ticked box is not sent
    assert "ieee" not in sources.selected()


def test_a_restored_form_cannot_bring_ieee_back_without_access(qtbot):
    from thesisagents.gui.pages.search import SearchPage
    from thesisagents.gui.pages.settings import settings_store

    settings_store().setValue("form/search/sources", "arxiv,ieee")
    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    page.restore_form(settings_store())
    assert page._sources_widget.selected() == ("arxiv",)  # noqa: SLF001


def test_saving_access_in_settings_unlocks_ieee_on_the_search_page(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    sources = window.search_page()._sources_widget  # noqa: SLF001
    assert sources.is_locked("ieee")
    window.settings_page().vpn_checkbox().setChecked(True)
    window.settings_page().trigger_save()
    assert not sources.is_locked("ieee")
    assert "ieee" in sources.selected()           # a default source comes back ticked
    window.settings_page().vpn_checkbox().setChecked(False)
    window.settings_page().trigger_save()
    assert "ieee" not in sources.selected()


def test_with_access_saved_ieee_starts_unlocked(qtbot):
    from thesisagents.gui.pages.search import SearchPage
    from thesisagents.gui.pages.settings import settings_store

    settings_store().setValue("access/vpn", True)
    page = SearchPage(ui_language="en")
    qtbot.addWidget(page)
    assert "ieee" in page._sources_widget.selected()  # noqa: SLF001


# --- #31 the route each PDF took is shown ----------------------------------------


def test_the_stage_counts_the_routes(monkeypatch, tmp_path):
    from thesisagents.core import pdf_download as core

    routes = {"1": core.ROUTE_BROWSER, "2": core.ROUTE_DIRECT_NO_BROWSER,
              "3": core.ROUTE_DIRECT_BROWSER_FAILED, "4": core.ROUTE_DIRECT}

    async def download(collection, out_dir, **_kwargs):
        return [
            PdfDownloadResult(p.source_id, Path(out_dir) if p.source_id in "14" else None,
                              None, routes[p.source_id])
            for p in collection.papers
        ]

    async def shutdown():
        return None

    monkeypatch.setattr(pdf_stage, "download_pdfs", download)
    monkeypatch.setattr(pdf_stage, "shutdown_clients", shutdown)
    report = pdf_stage.run_pdf_stage(
        _collection(*(_paper(i) for i in range(1, 5))), tmp_path, vpn_access=True
    )
    assert (report.saved, report.via_browser, report.without_browser, report.browser_failed) == (
        2, 1, 1, 1,
    )


def test_the_deck_status_warns_when_chrome_was_not_used(qtbot, monkeypatch, tmp_path):
    report = PdfStageReport(tmp_path / "pdfs", saved=3, skipped=2, held=0,
                            via_browser=1, without_browser=2, browser_failed=0)
    monkeypatch.setattr("thesisagents.gui.pages.deck.run_pdf_stage", lambda *_a, **_k: report)
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1)))
    for fmt in ("pptx", "xlsx", "bib"):
        page.format_checkbox(fmt).setChecked(False)
    page.download_pdfs_checkbox().setChecked(True)
    page._out_dir_input.setText(str(tmp_path))  # noqa: SLF001
    with qtbot.waitSignal(page.busy_changed, timeout=5000, check_params_cb=lambda b: not b):
        page._on_export_clicked()  # noqa: SLF001
    status = page.status_text()
    assert "1 through Chrome." in status
    assert "Chrome automation was not available, so 2 publisher PDFs" in status
    assert "could not fetch" not in status

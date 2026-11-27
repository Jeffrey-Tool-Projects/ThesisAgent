"""Exercise reopening an exported search from the Deck page."""

from __future__ import annotations

import json
from dataclasses import replace

from PySide6.QtWidgets import QFileDialog

from thesisagents.core.models import ExportOptions, PaperCollection, Query
from thesisagents.core.search_workbook import read_search_workbook
from thesisagents.exporters.xlsx import XlsxExporter
from thesisagents.gui.main_window import MainWindow
from thesisagents.intelligence.pdf import ExtractedPdf


def _save_workbook(tmp_path, papers):
    collection = PaperCollection(Query("search from yesterday", ("arxiv",)), tuple(papers))
    return XlsxExporter().export(collection, ExportOptions(formats=("xlsx",), out_dir=tmp_path))


def test_open_workbook_from_deck_then_change_the_search_selection(
    qtbot, monkeypatch, tmp_path, sample_papers
):
    path = _save_workbook(tmp_path, sample_papers)
    window = MainWindow()
    qtbot.addWidget(window)
    deck = window.deck_page()
    old = PaperCollection(Query("earlier selection", ("arxiv",)), (sample_papers[0],))
    window.search_page().show_results(old)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_: (str(path), ""))
    deck._source_button.click()  # noqa: SLF001
    assert not deck._export_button.isEnabled()  # noqa: SLF001
    qtbot.waitUntil(lambda: deck._export_button.isEnabled())  # noqa: SLF001
    titles = deck._paper_titles  # noqa: SLF001
    shown = [titles.item(i).text() for i in range(titles.count())]
    assert shown == [p.title for p in sample_papers]
    first, second = deck.collection().papers
    assert first.pdf_url == sample_papers[0].pdf_url
    assert first.arxiv_id == "2401.00001"
    assert (second.doi, second.url, second.venue) == (
        sample_papers[1].doi, sample_papers[1].url, sample_papers[1].venue
    )
    assert deck.collection().query.keywords == "search from yesterday"
    window.search_page().papers_model().set_checked(0, False)
    assert deck.collection().papers == (second,)
    assert titles.count() == 1 and titles.item(0).text() == second.title
    assert window.enrich_page().collection().papers == (second,)


def test_bad_workbook_leaves_previous_selection_and_reports_failure_on_deck(
    qtbot, monkeypatch, tmp_path, sample_papers
):
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"unreadable")
    window = MainWindow()
    qtbot.addWidget(window)
    original = PaperCollection(Query("current", ("arxiv",)), tuple(sample_papers))
    window.search_page().show_results(original)
    deck = window.deck_page()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *_: (str(path), ""))
    deck._source_button.click()  # noqa: SLF001
    qtbot.waitUntil(lambda: "Could not open" in deck.status_text())
    assert deck.collection() == original
    assert deck._source_button.isEnabled() and deck._export_button.isEnabled()  # noqa: SLF001


def test_saved_search_reads_only_the_pdf_owned_by_each_paper(tmp_path, monkeypatch, sample_papers):
    first = sample_papers[0]
    second = replace(first, title=first.title + " revisited", doi="10.1234/second")
    third = replace(first, title="Other study", doi="10.1234/third", pdf_url="file:///other.pdf")
    path = _save_workbook(tmp_path, (first, second, third))
    folder = tmp_path / "pdfs"
    folder.mkdir()
    name = first.bibtex_key()
    assert second.bibtex_key() == name
    (folder / f"{name}.pdf").write_bytes(b"unowned legacy file")
    (folder / f"{name}-abcd1234.pdf").write_bytes(b"owned")
    (tmp_path / "outside.pdf").write_bytes(b"outside")
    (folder / ".owners.json").write_text(json.dumps({
        f"{name}-abcd1234.pdf": second.dedup_key(), "../outside.pdf": third.dedup_key()
    }))
    monkeypatch.setattr(
        "thesisagents.core.search_workbook.extract_pdf_file",
        lambda path, *, url, source: ExtractedPdf(url, 2, 5, path.read_bytes().decode()),
    )
    papers = read_search_workbook(path).papers
    assert [p.raw.get("extracted_text") for p in papers] == [None, "owned", None]
    assert papers[1].raw["page_count"] == 2
    assert papers[2].pdf_url is None

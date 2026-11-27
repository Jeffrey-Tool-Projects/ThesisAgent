"""Tests for the Enrich page.

The Anthropic call is mocked end-to-end so the test never hits the
network and never needs ``ANTHROPIC_API_KEY``-shaped credentials in
the environment except where we explicitly set one to drive a code
path.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import replace

import pytest

from thesisagents.core.exceptions import ConfigError
from thesisagents.core.models import (
    Paper,
    PaperCollection,
    PaperSummary,
    Query,
)
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.enrich import EnrichPage
from thesisagents.gui.pages.settings import settings_store
from thesisagents.intelligence import providers


def _paper(idx: int, *, with_pdf: bool = True) -> Paper:
    return Paper(
        source="arxiv",
        source_id=f"2401.{idx:05d}",
        title=f"Test paper {idx}",
        authors=("Author A",),
        year=2024,
        venue=None,
        abstract="…",
        url="https://example.com/abs",
        doi=None,
        arxiv_id=f"2401.{idx:05d}",
        pdf_url=f"https://example.com/pdf/{idx}" if with_pdf else None,
    )


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(
        query=Query(keywords="enrich-test", sources=("arxiv",)),
        papers=papers,
    )


def test_initial_state_no_collection(qtbot):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    # Enrich button disabled, status mentions running a search first.
    assert page._enrich_button.isEnabled() is False  # noqa: SLF001
    assert "search" in page.status_text().lower()


def test_set_collection_enables_button_and_populates_table(qtbot):
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1), _paper(2)))
    assert page._enrich_button.isEnabled() is True  # noqa: SLF001
    assert page.table_model().rowCount() == 2
    assert "2" in page.status_text()


def test_enrich_without_api_key_surfaces_settings_hint(qtbot, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1)))
    page._on_enrich_clicked()  # noqa: SLF001
    assert "ANTHROPIC_API_KEY" in page.status_text()


def test_enrich_happy_path_attaches_summaries(qtbot, monkeypatch):
    """Mock fetch_and_extract + summarise_with so the worker thread
    drives the UI without any real network or LLM call."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    class FakeExtracted:
        text = "abstract … methods … results …"
        chars = 50_000

    async def fake_fetch(_url, source="intelligence"):
        return FakeExtracted()

    def fake_summarise(settings, paper, _text, language, chars):
        return PaperSummary(
            language=language,
            model=settings.model,
            raw_text_chars=chars,
            core_observation=f"fake summary for {paper.source_id}",
        )

    monkeypatch.setattr(
        "thesisagents.intelligence.pdf.fetch_and_extract", fake_fetch,
    )
    monkeypatch.setattr(
        "thesisagents.intelligence.summarise.summarise_with",
        fake_summarise,
    )

    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1), _paper(2)))
    page._on_enrich_clicked()  # noqa: SLF001

    qtbot.waitUntil(
        lambda: "Done" in page.status_text() or "Done:" in page.status_text(),
        timeout=5000,
    )

    enriched = page.collection()
    assert enriched is not None
    assert len(enriched.papers) == 2
    assert all(p.summary is not None for p in enriched.papers)
    assert "1" in page.status_text() or "2" in page.status_text()


def test_paper_without_pdf_url_is_skipped(qtbot, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1, with_pdf=False)))
    page._on_enrich_clicked()  # noqa: SLF001

    qtbot.waitUntil(
        lambda: "Done" in page.status_text(), timeout=3000,
    )
    enriched = page.collection()
    assert enriched is not None
    # Original paper preserved, summary stays None.
    assert enriched.papers[0].summary is None


def test_collection_ready_emitted_after_enrich(qtbot, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    received: list[object] = []
    page.collection_ready.connect(lambda c: received.append(c))
    page.set_collection(_collection(_paper(1, with_pdf=False)))
    page._on_enrich_clicked()  # noqa: SLF001
    qtbot.waitUntil(lambda: len(received) >= 1, timeout=3000)
    assert isinstance(received[0], PaperCollection)


def test_large_selection_without_pdf_links_completes(qtbot, monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    papers = _collection(*(_paper(i, with_pdf=False) for i in range(1050)))
    page = EnrichPage()
    qtbot.addWidget(page)
    page.set_collection(papers)
    with qtbot.waitSignal(page.collection_ready, timeout=10000) as finished:
        page._enrich_button.click()  # noqa: SLF001
    assert finished.args[0] == papers
    assert "skipped" in page.table_model().item(1049, 2).text()


def test_selecting_a_terminal_program_runs_it_for_each_paper(qtbot, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv(providers.PROVIDER_ENV, "anthropic")
    program = tmp_path / "summary program.py"
    program.write_text(
        "import json, sys\n"
        "prompt = sys.stdin.read()\n"
        "body = next(line for line in prompt.splitlines() if line.startswith('Trial '))\n"
        "print(json.dumps({'results': [body + ' / ' + sys.argv[-1]]}))\n",
        encoding="utf-8",
    )
    store = settings_store()
    store.setValue("llm/base_url/codex-cli", f'"{sys.executable}" "{program}"')
    store.setValue("llm/model/codex-cli", "first-model")
    page = EnrichPage(ui_language="en")
    qtbot.addWidget(page)
    combo = page._provider_combo  # noqa: SLF001
    for preset in ("claude-cli", "codex-cli", "agy-cli"):
        assert combo.findData(preset) >= 0
    combo.setCurrentIndex(combo.findData("codex-cli"))
    papers = tuple(
        replace(_paper(i, with_pdf=False), raw={"extracted_text": f"Trial {i}"})
        for i in (1, 2)
    )
    page.set_collection(_collection(*papers))
    with qtbot.waitSignal(page.collection_ready, timeout=10000) as finished:
        page._enrich_button.click()  # noqa: SLF001
        assert not combo.isEnabled()
        store.setValue("llm/base_url/codex-cli", "missing-command")
        monkeypatch.setenv(providers.PROVIDER_ENV, "codex-cli")
        monkeypatch.setenv(providers.COMMAND_ENV, "another-missing-command")
    first, second = finished.args[0].papers
    assert first.summary.results == ("Trial 1 / first-model",)
    assert second.summary.results == ("Trial 2 / first-model",)
    assert combo.isEnabled()


def test_missing_terminal_program_names_the_command(qtbot, monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, "codex-cli")
    monkeypatch.setenv(providers.COMMAND_ENV, "missing-terminal-program-for-test")
    page = EnrichPage()
    qtbot.addWidget(page)
    combo = page._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData("codex-cli"))
    page.set_collection(_collection(_paper(1)))
    page._enrich_button.click()  # noqa: SLF001
    qtbot.waitUntil(lambda: not page.is_running())
    assert "missing-terminal-program-for-test" in page.status_text()


def test_cli_sign_in_is_checked_before_reading_and_can_be_retried(qtbot, monkeypatch):
    page = EnrichPage("zh-tw")
    qtbot.addWidget(page)
    papers = _collection(*(
        replace(_paper(i), raw={"extracted_text": f"body {i}"}) for i in (1, 2)
    ))
    page.set_collection(papers)
    combo = page._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(providers.CLI))
    assert combo.currentData() == providers.CLI
    checks = []
    reads = []
    signed_in = False

    def check(settings):
        checks.append((settings.provider.name, threading.current_thread()))
        return None if signed_in else "Please run the CLI sign-in command"

    async def summarise(_settings, paper, language):
        reads.append(paper.title)
        return PaperSummary(language=language, core_observation=paper.title)

    monkeypatch.setattr(providers, "cli_readiness_problem", check)
    monkeypatch.setattr("thesisagents.gui.pages.enrich.summarise_for_page", summarise)
    with qtbot.waitSignal(page.collection_ready):
        page._enrich_button.click()  # noqa: SLF001
    assert "CLI sign-in command" in page.status_text() and "登入" in page.status_text()
    assert reads == []
    assert page.collection() == papers
    signed_in = True
    with qtbot.waitSignal(page.collection_ready):
        page._enrich_button.click()  # noqa: SLF001
    assert reads == [p.title for p in papers.papers]
    assert [name for name, _ in checks] == [providers.CLI, providers.CLI]
    assert all(thread != threading.current_thread() for _, thread in checks)
    assert all(p.summary is not None for p in page.collection().papers)

    signed_in = False
    with qtbot.waitSignal(page.collection_ready):
        page._enrich_button.click()  # noqa: SLF001
    assert all(p.summary is not None for p in page.collection().papers)


def test_runtime_cli_login_stops_batch_and_keeps_every_paper(qtbot, monkeypatch):
    page = EnrichPage()
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1), _paper(2), _paper(3)))
    combo = page._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData("gemini-cli"))
    attempts = []

    async def summarise(_settings, paper, language):
        attempts.append(paper.source_id)
        if len(attempts) == 1:
            return PaperSummary(language=language, core_observation="first summary")
        raise ConfigError("Open the program in a terminal and sign in")

    monkeypatch.setattr(providers, "cli_readiness_problem", lambda _settings: None)
    monkeypatch.setattr("thesisagents.gui.pages.enrich.summarise_for_page", summarise)
    with qtbot.waitSignal(page.collection_ready) as signal:
        page._enrich_button.click()  # noqa: SLF001
    first, second, third = signal.args[0].papers
    assert first.summary.core_observation == "first summary"
    assert attempts == [first.source_id, second.source_id]
    assert second.summary is None and third.summary is None
    assert "Open the program in a terminal and sign in" in page.status_text()


def test_cancel_during_cli_check_keeps_the_new_search(qtbot, monkeypatch):
    page = EnrichPage()
    qtbot.addWidget(page)
    page.set_collection(_collection(_paper(1)))
    combo = page._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(providers.CLI))
    started = threading.Event()
    release = threading.Event()

    def check(_settings):
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(providers, "cli_readiness_problem", check)
    completed = []
    page.collection_ready.connect(completed.append)
    page._enrich_button.click()  # noqa: SLF001
    try:
        qtbot.waitUntil(started.is_set)
        newer = _collection(_paper(9))
        page.set_collection(newer)
        page._cancel_button.click()  # noqa: SLF001
    finally:
        release.set()
    qtbot.waitUntil(lambda: not page.is_running())
    assert page.collection() == newer
    assert completed == []


def test_summaries_follow_search_checkboxes_during_and_after_enrichment(qtbot, monkeypatch):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    search = window.search_page()
    enrich = window.enrich_page()
    deck = window.deck_page()
    papers = _collection(_paper(1), _paper(2), _paper(3))
    search.show_results(papers)
    combo = enrich._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(providers.CLI))
    monkeypatch.setattr(providers, "cli_readiness_problem", lambda _: None)

    async def summarise(_settings, paper, language):
        if paper is papers.papers[2]:
            raise ConfigError("sign in again")
        return PaperSummary(language=language, core_observation=paper.title)

    monkeypatch.setattr("thesisagents.gui.pages.enrich.summarise_for_page", summarise)
    with qtbot.waitSignal(enrich.collection_ready):
        enrich._enrich_button.click()  # noqa: SLF001
        search.papers_model().set_checked(1, False)
    selected = deck.collection().papers
    assert [paper.title for paper in selected] == ["Test paper 1", "Test paper 3"]
    assert selected[0].summary.core_observation == selected[0].title
    assert selected[1].summary is None
    assert "sign in again" in enrich.status_text()
    assert enrich.table_model().item(0, 2).text() == "ok"
    search.papers_model().set_checked(1, True)
    first, second, third = deck.collection().papers
    assert first.summary.core_observation == first.title
    assert second.summary.core_observation == second.title
    assert third.summary is None
    assert search.collection() == enrich.collection() == deck.collection()


def test_runtime_summary_does_not_replace_an_independently_loaded_paper(qtbot, monkeypatch):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    search = window.search_page()
    enrich = window.enrich_page()
    paper = _paper(1)
    search.show_results(_collection(paper))
    combo = enrich._provider_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(providers.CLI))
    monkeypatch.setattr(providers, "cli_readiness_problem", lambda _: None)

    async def summarise(_settings, _paper, language):
        return PaperSummary(language=language, core_observation="old run")

    monkeypatch.setattr("thesisagents.gui.pages.enrich.summarise_for_page", summarise)
    completed = []
    enrich.collection_ready.connect(completed.append)
    enrich._enrich_button.click()  # noqa: SLF001
    newer = replace(paper, summary=PaperSummary(language="en", core_observation="my edit"))
    search.show_results(_collection(newer))
    qtbot.waitUntil(lambda: not enrich.is_running())
    assert completed == []
    assert search.collection().papers[0] is newer
    assert enrich.collection().papers[0] is newer
    assert window.deck_page().collection().papers[0] is newer


@pytest.fixture(autouse=True)
def _clear_anthropic_key_after_test():
    """Defensive: never leak a fake key into other tests."""
    yield
    os.environ.pop("ANTHROPIC_API_KEY", None)

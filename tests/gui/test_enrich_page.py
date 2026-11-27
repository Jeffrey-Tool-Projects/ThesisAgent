"""Tests for the Enrich page.

The Anthropic call is mocked end-to-end so the test never hits the
network and never needs ``ANTHROPIC_API_KEY``-shaped credentials in
the environment except where we explicitly set one to drive a code
path.
"""

from __future__ import annotations

import os
import sys
from dataclasses import replace

import pytest

from thesisagents.core.models import (
    Paper,
    PaperCollection,
    PaperSummary,
    Query,
)
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
    assert "missing-terminal-program-for-test" in page.status_text()
    assert not page.is_running()


@pytest.fixture(autouse=True)
def _clear_anthropic_key_after_test():
    """Defensive: never leak a fake key into other tests."""
    yield
    os.environ.pop("ANTHROPIC_API_KEY", None)

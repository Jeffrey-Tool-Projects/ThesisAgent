"""The Search page runs one search at a time and ignores stale results (code review R12).

Enter in the query field is connected straight to the search handler, so it
still fired while the Search button was disabled by a running search. Two
workers then took turns as ``_worker``, and the older query, finishing later,
replaced the newer result and re-enabled the form while a search was still
running. No test here makes a network call: ``run_search`` is replaced by a
coroutine that waits before it answers.
"""

from __future__ import annotations

import asyncio

import pytest
from PySide6.QtCore import QThreadPool

from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui.pages.search import SearchPage
from thesisagents.gui.workers import AsyncWorker

SEARCH = "thesisagents.gui.pages.search"


def _collection(keywords: str, count: int) -> PaperCollection:
    papers = tuple(
        Paper(
            source="arxiv", source_id=f"{keywords}-{i}", title=f"{keywords} paper {i}",
            authors=("Ada Author",), year=2024, venue=None, abstract="",
            url=f"https://example.org/{keywords}/{i}",
        )
        for i in range(count)
    )
    return PaperCollection(Query(keywords, ("arxiv",)), papers)


@pytest.fixture
def page(qtbot, monkeypatch):
    """A Search page whose search answers after a delay and records each call."""
    calls: list[str] = []

    async def delayed_run_search(query, **_kwargs):
        calls.append(query.keywords)
        await asyncio.sleep(0.4)
        return _collection(query.keywords, 2)

    async def no_shutdown():
        return None

    monkeypatch.setattr(f"{SEARCH}.run_search", delayed_run_search)
    monkeypatch.setattr(f"{SEARCH}.shutdown_clients", no_shutdown)
    widget = SearchPage(ui_language="en")
    qtbot.addWidget(widget)
    widget.calls = calls
    return widget


def test_a_second_enter_while_searching_starts_no_second_worker(page, qtbot):
    page.set_query_text("first query")
    page._query_input.returnPressed.emit()  # noqa: SLF001
    first_worker = page._worker  # noqa: SLF001
    assert first_worker is not None
    page.set_query_text("second query")
    page._query_input.returnPressed.emit()  # noqa: SLF001
    # The running search keeps its worker, so Cancel still stops that search.
    assert page._worker is first_worker  # noqa: SLF001
    assert page._cancel_button.isVisibleTo(page)  # noqa: SLF001
    with qtbot.waitSignal(page.busy_changed, timeout=5000) as signal:
        pass
    assert signal.args == [False]
    qtbot.wait(600)  # time for a second worker, had one started, to answer
    assert page.calls == ["first query"]
    collection = page.collection()
    assert collection is not None
    assert collection.query.keywords == "first query"
    assert page._search_button.isEnabled()  # noqa: SLF001
    assert not page._cancel_button.isVisibleTo(page)  # noqa: SLF001


def test_library_search_and_local_pdfs_wait_for_a_running_search(page, qtbot, tmp_path):
    page.set_query_text("first query")
    page._on_search_clicked()  # noqa: SLF001
    seen: list[bool] = []
    page.busy_changed.connect(seen.append)
    page.set_library_path(str(tmp_path / "missing.db"))
    page._on_library_search_clicked()  # noqa: SLF001
    page.read_local_pdfs([str(tmp_path / "missing.pdf")])
    # Neither started a run of its own, so the only busy change is the end of
    # the search, and the form stays locked until then.
    qtbot.wait(150)
    assert seen == []
    assert not page._search_button.isEnabled()  # noqa: SLF001
    qtbot.waitUntil(lambda: page._search_button.isEnabled(), timeout=5000)  # noqa: SLF001
    assert seen == [False]
    collection = page.collection()
    assert collection is not None
    assert collection.query.keywords == "first query"


def test_a_result_from_a_worker_that_is_not_current_is_ignored(page, qtbot):
    page.set_query_text("current query")
    page._on_search_clicked()  # noqa: SLF001
    current_worker = page._worker  # noqa: SLF001

    async def stale_result() -> PaperCollection:
        return _collection("stale query", 5)

    # A worker the page did not start as its current run, connected the way
    # the page connects its own (bound methods, never lambdas).
    stale = AsyncWorker(stale_result)
    stale.signals.finished.connect(page._on_search_finished)  # noqa: SLF001
    stale.signals.failed.connect(page._on_worker_failed)  # noqa: SLF001
    with qtbot.waitSignal(stale.signals.finished, timeout=5000):
        QThreadPool.globalInstance().start(stale)
    qtbot.wait(50)
    # The stale result neither filled the table nor ended the running search.
    assert page.papers_model().rowCount() == 0
    assert not page._search_button.isEnabled()  # noqa: SLF001
    assert page._worker is current_worker  # noqa: SLF001
    qtbot.waitUntil(lambda: page.papers_model().rowCount() == 2, timeout=5000)
    collection = page.collection()
    assert collection is not None
    assert collection.query.keywords == "current query"


def test_an_export_failure_does_not_end_a_running_search(page, qtbot):
    page.set_query_text("current query")
    page._on_search_clicked()  # noqa: SLF001
    page._on_export_failed(RuntimeError("disk full"))  # noqa: SLF001
    assert not page._search_button.isEnabled()  # noqa: SLF001
    assert page._worker is not None  # noqa: SLF001
    assert "disk full" in page.status_text()
    qtbot.waitUntil(lambda: page.papers_model().rowCount() == 2, timeout=5000)

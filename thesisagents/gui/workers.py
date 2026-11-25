"""Background-thread wrappers for the GUI.

Qt's event loop runs on the main thread; calling a blocking or async
backend function directly from a button handler freezes the UI. Each
worker here wraps one backend call, runs it on a worker thread (via
``QThreadPool``), and emits a signal back to the main thread when done.

Signals are typed as ``object`` because ``Signal`` doesn't accept
``PaperCollection`` / ``Path`` as parameter types directly; the
receiving slot casts as needed.

Connect the signals to methods of a ``QObject`` (a page), never to a lambda.
A result is delivered through the event loop after the runnable has ended,
and with it its signals object. A connection to a method belongs to the page
and survives that. One to a lambda belongs to the signals object, so the
result is sometimes lost and the page stays busy for ever.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class _WorkerSignals(QObject):
    """Signals emitted by :class:`AsyncWorker` and :class:`BlockingWorker`.

    Defined here (not on the QRunnable subclasses) because QRunnable is
    not a QObject and can't carry signals directly. ``cancelled`` fires
    instead of ``finished`` / ``failed`` when :meth:`AsyncWorker.cancel`
    stopped the coroutine.
    """

    finished = Signal(object)
    failed = Signal(object)
    cancelled = Signal()


class AsyncWorker(QRunnable):
    """Run a coroutine off the main thread and report back via signals.

    Use this for anything that calls ``await`` — searches, single-paper
    fetches, anything that touches ``httpx.AsyncClient``.

    :meth:`cancel` may be called from the UI thread at any time. It cancels
    the coroutine at its next ``await``, so its ``finally`` blocks still run
    (a search closes its HTTP clients), and ``cancelled`` is emitted. Work
    that never awaits (a synchronous API call inside the coroutine) finishes
    first, and then the result is dropped in favour of ``cancelled``.

    Example::

        worker = AsyncWorker(lambda: run_search(query))
        worker.signals.cancelled.connect(on_cancelled)
        QThreadPool.globalInstance().start(worker)
        ...
        worker.cancel()   # the Cancel button
    """

    def __init__(self, coro_factory: Callable[[], Any]) -> None:
        super().__init__()
        self._coro_factory = coro_factory
        self.signals = _WorkerSignals()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[Any] | None = None
        self._cancel_requested = False

    def cancel(self) -> None:
        """Ask the running coroutine to stop. Safe from any thread, idempotent."""
        with self._lock:
            self._cancel_requested = True
            loop, task = self._loop, self._task
        if loop is not None and task is not None and not loop.is_closed():
            loop.call_soon_threadsafe(task.cancel)

    def is_cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    async def _main(self) -> Any:
        task = asyncio.current_task()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._task = task
            cancel_now = self._cancel_requested
        if cancel_now and task is not None:
            task.cancel()
        return await self._coro_factory()

    @Slot()
    def run(self) -> None:
        try:
            result = asyncio.run(self._main())
        except asyncio.CancelledError:
            self.signals.cancelled.emit()
            return
        except Exception as err:  # noqa: BLE001 — UI must catch everything
            if self.is_cancel_requested():
                self.signals.cancelled.emit()
                return
            self.signals.failed.emit(err)
            return
        finally:
            with self._lock:
                self._loop = None
                self._task = None
        if self.is_cancel_requested():
            self.signals.cancelled.emit()
            return
        self.signals.finished.emit(result)


class BlockingWorker(QRunnable):
    """Run a plain blocking callable off the main thread.

    Use this for synchronous CPU / IO calls — ``export_collection``
    is the main one (renders a pptx via python-pptx). It cannot be
    cancelled: a half-written export would leave partial files behind.
    """

    def __init__(self, func: Callable[[], Any]) -> None:
        super().__init__()
        self._func = func
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self._func()
        except Exception as err:  # noqa: BLE001
            self.signals.failed.emit(err)
            return
        self.signals.finished.emit(result)

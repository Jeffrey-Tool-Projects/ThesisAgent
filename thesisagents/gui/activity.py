"""What the app is doing, kept where a user without a console can read it.

The released app is a windowed program: its log lines went to a console that
no longer exists. This module catches them three ways:

* the last :data:`MAX_LINES` lines in memory, for the log window,
* a rotating file under :func:`log_directory`, to attach to a bug report,
* errors nobody caught (``sys.excepthook``, threads), which Qt would print.

Every line passes :func:`redact` first, because some sources take their API
key as a URL parameter and an error message quotes the URL.

Example::

    install()                                    # once, at boot
    activity().line_added.connect(view.append)
"""

from __future__ import annotations

import logging
import os
import re
import sys
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Final

from PySide6.QtCore import QObject, QStandardPaths, Signal

from thesisagents.utils import notices
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

MAX_LINES: Final[int] = 2000
_FILE_BYTES: Final[int] = 1_000_000
_FILE_COUNT: Final[int] = 3
_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"

_SECRET_PARAMETER = re.compile(
    r"(?i)\b(api[-_]?key|apikey|token|access_token|key)=([^&\s\"']{4,})"
)
#: Environment variables that hold a secret, by their ending.
_SECRET_ENV_SUFFIXES: Final[tuple[str, ...]] = ("_API_KEY", "_TOKEN")
_SHORTEST_SECRET: Final[int] = 6
_HIDDEN: Final[str] = "***"


def redact(text: str) -> str:
    """``text`` without API keys: URL parameters and the values in the environment.

    >>> redact("GET https://x.example/?apikey=abcdef&q=1")
    'GET https://x.example/?apikey=***&q=1'
    """
    text = _SECRET_PARAMETER.sub(rf"\1={_HIDDEN}", text)
    for name, value in os.environ.items():
        if name.endswith(_SECRET_ENV_SUFFIXES) and len(value) >= _SHORTEST_SECRET:
            text = text.replace(value, _HIDDEN)
    return text


def log_directory() -> Path:
    """Where the log file is written (``%LOCALAPPDATA%\\ThesisAgents\\logs`` on Windows)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)
    return Path(base) / "ThesisAgents" / "logs"


def log_file() -> Path:
    return log_directory() / "thesisagents.log"


class _RedactingFormatter(logging.Formatter):
    """Formats a record, traceback included, then removes secrets."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


class Activity(QObject):
    """The in-memory log and the notices, as Qt signals.

    Records arrive on worker threads. Emitting from there is safe: Qt queues
    the call to slots that live on the main thread.
    """

    line_added = Signal(str)
    #: A :class:`thesisagents.utils.notices.Notice`.
    notice = Signal(object)
    #: An exception nobody caught, as its one-line text.
    unexpected_error = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._lines: deque[str] = deque(maxlen=MAX_LINES)
        self._lock = threading.Lock()

    def add_line(self, line: str) -> None:
        with self._lock:
            self._lines.append(line)
        self.line_added.emit(line)

    def text(self) -> str:
        with self._lock:
            return "\n".join(self._lines)

    def clear(self) -> None:
        with self._lock:
            self._lines.clear()


class _ActivityHandler(logging.Handler):
    """Feeds log records to the :class:`Activity`."""

    def __init__(self, target: Activity) -> None:
        super().__init__()
        self._target = target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._target.add_line(self.format(record))
        except RuntimeError:
            # The Qt object is gone: the interpreter is shutting down.
            return
        except Exception:  # noqa: BLE001 - logging must not raise into the caller
            self.handleError(record)


_STATE: dict[str, Activity] = {}


def activity() -> Activity:
    """The app's one :class:`Activity`."""
    if "activity" not in _STATE:
        _STATE["activity"] = Activity()
    return _STATE["activity"]


def install() -> None:
    """Start collecting. Safe to call again, the second call does nothing."""
    logger = logging.getLogger("thesisagents")
    if any(isinstance(handler, _ActivityHandler) for handler in logger.handlers):
        return
    target = activity()
    formatter = _RedactingFormatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    handlers: list[logging.Handler] = [_ActivityHandler(target)]
    try:
        log_directory().mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_file(), maxBytes=_FILE_BYTES, backupCount=_FILE_COUNT, encoding="utf-8"
            )
        )
    except OSError as err:
        # A read-only profile must not stop the app, the window still logs.
        _LOG.warning("no log file: %s", err)
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    notices.subscribe(target.notice.emit)
    sys.excepthook = _on_unhandled
    threading.excepthook = lambda args: _on_unhandled(
        args.exc_type, args.exc_value, args.exc_traceback
    )


def _on_unhandled(
    kind: type[BaseException], error: BaseException | None, trace: TracebackType | None
) -> None:
    """Log an exception nobody caught and tell the window about it."""
    if issubclass(kind, KeyboardInterrupt):
        sys.__excepthook__(kind, error, trace)
        return
    _LOG.error("unexpected error", exc_info=(kind, error, trace))
    activity().unexpected_error.emit(redact(f"{kind.__name__}: {error}"))

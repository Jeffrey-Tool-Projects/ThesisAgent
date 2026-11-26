"""Messages from background work that need the user, not just the log.

The boundary this module guards: fetchers must not know about Qt, and the
desktop app must not parse log text. A captcha in the visible Chrome window
is the case it exists for. It was announced by a log line only, so a user of
the windowed release, which has no console, saw a search that did nothing
until the five minute wait ran out.

Anyone may :func:`subscribe`. Without a subscriber (the CLI, MCP) publishing
does nothing, and the log line remains the announcement.

Example::

    unsubscribe = subscribe(lambda notice: print(notice.kind, notice.site))
    publish(Notice(CAPTCHA_WAITING, site="scholar.google.com", seconds=300))
    unsubscribe()
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

#: Chrome shows a "prove you are human" page and work waits for the user.
CAPTCHA_WAITING: Final[str] = "captcha_waiting"
#: The user solved it, work goes on.
CAPTCHA_CLEARED: Final[str] = "captcha_cleared"
#: Nobody solved it in time, that source returns nothing.
CAPTCHA_TIMED_OUT: Final[str] = "captcha_timed_out"


@dataclass(frozen=True, slots=True)
class Notice:
    """One message. ``seconds`` is how long the work will wait."""

    kind: str
    site: str = ""
    seconds: float = 0.0


_SUBSCRIBERS: list[Callable[[Notice], None]] = []
_LOCK = threading.Lock()


def subscribe(callback: Callable[[Notice], None]) -> Callable[[], None]:
    """Call ``callback`` for every notice. Returns a function that stops it.

    The callback runs on the thread that publishes, usually a worker.
    """
    with _LOCK:
        _SUBSCRIBERS.append(callback)

    def unsubscribe() -> None:
        with _LOCK:
            if callback in _SUBSCRIBERS:
                _SUBSCRIBERS.remove(callback)

    return unsubscribe


def publish(notice: Notice) -> None:
    """Hand ``notice`` to every subscriber. Never raises.

    A failing subscriber is logged and skipped: a broken window must not
    stop the search that wanted to tell it something.
    """
    with _LOCK:
        subscribers = list(_SUBSCRIBERS)
    for callback in subscribers:
        try:
            callback(notice)
        except Exception:  # noqa: BLE001 - any subscriber error is contained here
            _LOG.exception("a notice subscriber failed")

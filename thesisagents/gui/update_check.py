"""Tell the user about a newer release, at most once a day.

The button appears in the status bar and opens the download page. Nothing is
downloaded or installed by the app itself.

Example::

    UpdateCheck(window).start()      # once, after the window is shown
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from PySide6.QtCore import QObject, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from thesisagents import __version__
from thesisagents.core.updates import RELEASES_URL, is_newer, newer_version
from thesisagents.gui.pages.settings import saved_update_check, settings_store
from thesisagents.gui.workers import AsyncWorker

_LAST_CHECK_KEY: Final[str] = "updates/last_check"
#: The newest release seen, so a start within the same day still shows it.
_SEEN_KEY: Final[str] = "updates/seen"
_INTERVAL: Final[timedelta] = timedelta(days=1)


def _checked_recently(now: datetime) -> bool:
    stamp = settings_store().value(_LAST_CHECK_KEY, "", type=str)
    try:
        last = datetime.fromisoformat(stamp)
        return timedelta(0) <= now - last < _INTERVAL
    except (TypeError, ValueError):
        # Never checked, or a hand-edited value.
        return False


class UpdateCheck(QObject):
    """Looks for a newer release and reports it once."""

    #: The version of a newer release.
    found = Signal(str)

    def start(self, current: str = __version__) -> bool:
        """Report a release, asking PyPI when the last answer is a day old.

        Returns whether PyPI is being asked.
        """
        if not saved_update_check():
            return False
        now = datetime.now(UTC)
        if _checked_recently(now):
            seen = settings_store().value(_SEEN_KEY, "", type=str)
            if is_newer(seen, current):
                self.found.emit(seen)
            return False
        settings_store().setValue(_LAST_CHECK_KEY, now.isoformat())
        worker = AsyncWorker(lambda: newer_version(current))
        worker.signals.finished.connect(self._on_answer)
        QThreadPool.globalInstance().start(worker)
        return True

    def _on_answer(self, version: object) -> None:
        # No answer is also what a machine without network gets, so the release
        # seen before stays. It is compared with the running version on use.
        if isinstance(version, str):
            settings_store().setValue(_SEEN_KEY, version)
            self.found.emit(version)


def open_download_page() -> None:
    QDesktopServices.openUrl(QUrl(RELEASES_URL))

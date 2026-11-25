"""A strip above the page for what cannot wait: Chrome needs the user.

A status bar line is too easy to miss for work that stops until somebody
solves a captcha. The banner stays until the work goes on, counts down how
long it will wait, and the window asks for attention in the taskbar.

Example::

    banner = NoticeBanner(language="en")
    banner.show_notice(Notice(CAPTCHA_WAITING, site="scholar.google.com", seconds=300))
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from thesisagents.gui.i18n import t
from thesisagents.utils.notices import (
    CAPTCHA_CLEARED,
    CAPTCHA_TIMED_OUT,
    CAPTCHA_WAITING,
    Notice,
)

_FINAL_MESSAGE_MS = 8000


class NoticeBanner(QFrame):
    """Shows one notice at a time. Hidden while there is none."""

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NoticeBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._language = language
        self._site = ""
        self._seconds_left = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 12, 10)
        self._label = QLabel("", self)
        self._label.setObjectName("NoticeText")
        self._label.setWordWrap(True)
        layout.addWidget(self._label, stretch=1)
        self._dismiss = QPushButton(t("action.close", language), self)
        self._dismiss.clicked.connect(self.clear)
        layout.addWidget(self._dismiss)
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._count_down)
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.clear)
        self.hide()

    def show_notice(self, notice: Notice) -> None:
        """Display ``notice``. Kinds the banner does not know are ignored."""
        self._hide.stop()
        self._tick.stop()
        if notice.kind == CAPTCHA_WAITING:
            self._site = notice.site
            self._seconds_left = int(notice.seconds)
            self._tick.start()
            self._show_waiting()
        elif notice.kind == CAPTCHA_CLEARED:
            self._show(t("notice.captcha_cleared", self._language))
            self._hide.start(_FINAL_MESSAGE_MS)
        elif notice.kind == CAPTCHA_TIMED_OUT:
            # Stays until closed: the user was away, and results are missing.
            self._show(t("notice.captcha_timed_out", self._language, site=notice.site))

    def clear(self) -> None:
        self._tick.stop()
        self._hide.stop()
        self.hide()

    def text(self) -> str:
        return self._label.text()

    def _count_down(self) -> None:
        self._seconds_left = max(0, self._seconds_left - 1)
        self._show_waiting()

    def _show_waiting(self) -> None:
        minutes, seconds = divmod(self._seconds_left, 60)
        self._show(
            t(
                "notice.captcha_waiting", self._language,
                site=self._site, time=f"{minutes}:{seconds:02d}",
            )
        )

    def _show(self, text: str) -> None:
        self._label.setText(text)
        self.show()

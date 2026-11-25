"""The log window: what the app did, live, with a way to pass it on.

Example::

    dialog = LogDialog(language="zh-tw", parent=window)
    dialog.show()      # not modal, so it can stay open beside a running search
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFontDatabase, QGuiApplication
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QPushButton, QVBoxLayout

from thesisagents.gui.activity import MAX_LINES, activity, log_directory
from thesisagents.gui.font_size import current_font_size
from thesisagents.gui.i18n import t


class LogDialog(QDialog):
    """Live view of the app's log, with Copy and Open folder."""

    def __init__(self, language: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("log.title", language))
        self.resize(860, 480)
        layout = QVBoxLayout(self)
        self._view = QPlainTextEdit(self)
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(MAX_LINES)
        self._view.setAccessibleName(t("log.title", language))
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(current_font_size())
        self._view.setFont(font)
        self._view.setPlainText(activity().text())
        self._scroll_to_end()
        layout.addWidget(self._view)
        buttons = QDialogButtonBox(self)
        for key, slot in (
            ("action.copy", self._copy),
            ("log.open_folder", self._open_folder),
        ):
            button = QPushButton(t(key, language), self)
            button.clicked.connect(slot)
            buttons.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
        close = QPushButton(t("action.close", language), self)
        close.clicked.connect(self.close)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        activity().line_added.connect(self._append)

    def _append(self, line: str) -> None:
        bar = self._view.verticalScrollBar()
        following = bar.value() >= bar.maximum() - 2
        self._view.appendPlainText(line)
        if following:
            self._scroll_to_end()

    def _scroll_to_end(self) -> None:
        bar = self._view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self._view.toPlainText())

    def _open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_directory())))

    def text(self) -> str:
        return self._view.toPlainText()

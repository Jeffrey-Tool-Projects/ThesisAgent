"""A window that shows a multi-line text report (template check, deck review).

The boundary this guards: the status line. A template check or a deck
review produces one line per finding, often a dozen, and a status label
either truncates them or grows the page. The dialog shows the full text in a
monospace box the user can read, select and copy, while the status line
keeps a one-line verdict.

It opens non-modally (``open()``), so the page stays usable and tests do not
block on an event loop.

Example::

    dialog = ReportDialog("Template check", report_text, copy_label="Copy",
                          close_label="Close", parent=page)
    dialog.open()
"""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.font_size import current_font_size


class ReportDialog(QDialog):
    """Read-only monospace text with Copy and Close buttons."""

    def __init__(
        self,
        title: str,
        text: str,
        *,
        copy_label: str,
        close_label: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        fixed.setPointSize(current_font_size())
        self._text.setFont(fixed)
        self._text.setPlainText(text)
        layout.addWidget(self._text)
        buttons = QDialogButtonBox(self)
        copy = QPushButton(copy_label, self)
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        close = QPushButton(close_label, self)
        close.clicked.connect(self.accept)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

    def text(self) -> str:
        return self._text.toPlainText()

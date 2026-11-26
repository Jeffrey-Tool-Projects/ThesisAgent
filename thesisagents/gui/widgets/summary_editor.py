"""Edit a paper's summary by hand, section by section.

One tab per thesis section, one text box per field. The strip above the tabs
says which of the seven sections have nothing yet, the same check a deck is
judged by, so a gap shows before the export does.

Example::

    editor = SummaryEditor(paper, "zh-tw", parent=window)
    editor.saved.connect(lambda paper: ...)      # the paper with its new summary
    editor.open()
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.models import Paper, PaperSummary
from thesisagents.core.summary_text import (
    FIELDS,
    SECTIONS,
    covered_sections,
    summary_to_texts,
    texts_to_summary,
)
from thesisagents.gui.i18n import t

_CHECK_DELAY_MS = 300


class SummaryEditor(QDialog):
    """The form. Nothing is changed until **Save**."""

    #: The paper with its edited summary.
    saved = Signal(object)

    def __init__(self, paper: Paper, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paper = paper
        self._language = language
        self._boxes: dict[str, QPlainTextEdit] = {}
        self.setWindowTitle(t("summary.title", language))
        self.resize(860, 640)
        layout = QVBoxLayout(self)
        heading = QLabel(paper.title, self)
        heading.setObjectName("CardTitle")
        heading.setWordWrap(True)
        # Plain text: the title comes from a remote API.
        heading.setTextFormat(heading.textFormat().PlainText)
        layout.addWidget(heading)
        self._coverage = QLabel("", self)
        self._coverage.setObjectName("Muted")
        self._coverage.setWordWrap(True)
        layout.addWidget(self._coverage)
        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)
        texts = summary_to_texts(paper.summary)
        for section in SECTIONS:
            specs = [spec for spec in FIELDS if spec.section == section]
            if specs:
                self._tabs.addTab(
                    self._section_page(specs, texts), t(f"summary.section_{section}", language)
                )
        layout.addWidget(self._tabs, stretch=1)
        buttons = QDialogButtonBox(self)
        save = QPushButton(t("settings.save_button", language), self)
        save.setProperty("primary", True)
        save.clicked.connect(self._save)
        buttons.addButton(save, QDialogButtonBox.ButtonRole.ActionRole)
        cancel = QPushButton(t("action.cancel", language), self)
        cancel.clicked.connect(self.reject)
        buttons.addButton(cancel, QDialogButtonBox.ButtonRole.RejectRole)
        self._save_button = save
        layout.addWidget(buttons)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(_CHECK_DELAY_MS)
        self._timer.timeout.connect(self._show_coverage)
        self._initial = self.texts()
        self._show_coverage()

    def _section_page(self, specs: list, texts: dict[str, str]) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        for spec in specs:
            label = QLabel(t(f"summary.field_{spec.name}", self._language), page)
            label.setObjectName("CardTitle")
            hint = QLabel(t(f"summary.hint_{spec.kind}", self._language), page)
            hint.setObjectName("Muted")
            hint.setWordWrap(True)
            box = QPlainTextEdit(texts[spec.name], page)
            box.setTabChangesFocus(True)
            box.setMinimumHeight(84)
            box.setAccessibleName(label.text())
            box.textChanged.connect(lambda: self._timer.start())
            layout.addWidget(label)
            layout.addWidget(hint)
            layout.addWidget(box)
            self._boxes[spec.name] = box
        layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setWidget(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def texts(self) -> dict[str, str]:
        return {name: box.toPlainText() for name, box in self._boxes.items()}

    def summary(self) -> PaperSummary:
        """What the form describes now."""
        return texts_to_summary(self._paper.summary, self.texts(), language=self._language)

    def missing_sections(self) -> list[str]:
        covered = covered_sections(self._paper, self.summary())
        return [section for section in SECTIONS if not covered[section]]

    def _show_coverage(self) -> None:
        missing = self.missing_sections()
        if not missing:
            self._coverage.setText(t("summary.complete", self._language))
            return
        names = ", ".join(t(f"summary.section_{name}", self._language) for name in missing)
        self._coverage.setText(t("summary.missing", self._language, sections=names))

    def _save(self) -> None:
        summary = self.summary()
        self.saved.emit(
            replace(  # NOSONAR dataclasses.replace returns the same dataclass type
                self._paper, summary=None if summary.is_empty() else summary
            )
        )
        self._initial = self.texts()
        self.accept()

    def reject(self) -> None:
        """Close, asking first when there are changes that would be lost."""
        if self.texts() != self._initial and not self._confirm_discard():
            return
        super().reject()

    def _confirm_discard(self) -> bool:
        answer = QMessageBox.question(
            self, t("summary.title", self._language), t("summary.discard", self._language)
        )
        return answer == QMessageBox.StandardButton.Yes

    # --- accessors used by tests ------------------------------------------

    def box(self, name: str) -> QPlainTextEdit:
        return self._boxes[name]

    def coverage_text(self) -> str:
        return self._coverage.text()

    def save_button(self) -> QPushButton:
        return self._save_button

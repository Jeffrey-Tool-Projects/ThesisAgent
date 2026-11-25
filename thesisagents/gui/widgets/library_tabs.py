"""The smaller tabs and dialogs of the Library page.

* :class:`SavedSearchesTab`: named searches that report only what is new.
* :class:`ReviewTab`: the PRISMA numbers and the diagram.
* :class:`DuplicatesDialog`: papers that look like one, to merge or keep.

Like the paper editor they hold no database. They emit what the user asked
for, and the page does it on a worker thread.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.i18n import t
from thesisagents.gui.widgets.responsive import make_card
from thesisagents.library import LibraryEntry, PrismaFlow, SavedSearch
from thesisagents.library.prisma import DEFAULT_LABELS


class SavedSearchesTab(QWidget):
    """A table of saved searches with Run and Delete, and a row to save one."""

    run_requested = Signal(str)
    delete_requested = Signal(str)
    #: The name to save the Search page's current search under.
    save_requested = Signal(str)

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = language
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels([
            t("library.col_name", language),
            t("library.col_keywords", language),
            t("library.col_last_run", language),
            t("library.col_new", language),
        ])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.itemSelectionChanged.connect(self._refresh)
        layout.addWidget(self._table, stretch=1)
        row = QHBoxLayout()
        self._name = QLineEdit(self)
        self._name.setPlaceholderText(t("library.saved_name_placeholder", language))
        self._name.returnPressed.connect(self._save)
        self._save_button = QPushButton(t("library.saved_from_search", language), self)
        self._save_button.clicked.connect(self._save)
        self._run = QPushButton(t("library.saved_run", language), self)
        self._run.setProperty("primary", True)
        self._run.clicked.connect(lambda: self.run_requested.emit(self.selected()))
        self._delete = QPushButton(t("library.action_delete", language), self)
        self._delete.clicked.connect(lambda: self.delete_requested.emit(self.selected()))
        row.addWidget(self._name, stretch=1)
        row.addWidget(self._save_button)
        row.addWidget(self._run)
        row.addWidget(self._delete)
        layout.addLayout(row)
        self._refresh()

    def show_searches(self, searches: Sequence[SavedSearch]) -> None:
        self._table.setRowCount(0)
        for saved in searches:
            row = self._table.rowCount()
            self._table.insertRow(row)
            values = (
                saved.name,
                saved.query.keywords,
                (saved.last_run_at or "")[:16].replace("T", " "),
                "" if saved.last_new is None else str(saved.last_new),
            )
            for column, value in enumerate(values):
                self._table.setItem(row, column, QTableWidgetItem(value))
        self._refresh()

    def selected(self) -> str:
        items = self._table.selectedItems()
        return items[0].text() if items else ""

    def set_busy(self, busy: bool) -> None:
        self._save_button.setEnabled(not busy)
        self._refresh(busy)

    def _refresh(self, busy: bool = False) -> None:
        for button in (self._run, self._delete):
            button.setEnabled(bool(self.selected()) and not busy)

    def _save(self) -> None:
        name = self._name.text().strip()
        if name:
            self.save_requested.emit(name)
            self._name.clear()

    # --- accessors used by tests ------------------------------------------

    def table(self) -> QTableWidget:
        return self._table

    def name_input(self) -> QLineEdit:
        return self._name

    def run_button(self) -> QPushButton:
        return self._run

    def delete_button(self) -> QPushButton:
        return self._delete

    def save_button(self) -> QPushButton:
        return self._save_button


def prisma_labels(language: str) -> dict[str, str]:
    """The wording of the PRISMA diagram in the interface language."""
    return {key: t(f"prisma.{key}", language) for key in DEFAULT_LABELS}


class ReviewTab(QWidget):
    """The flow's numbers as text, and a button that saves the diagram."""

    save_requested = Signal()

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = language
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        self._text = QTextBrowser(self)
        self._text.setOpenLinks(False)
        layout.addWidget(self._text, stretch=1)
        row = QHBoxLayout()
        row.addStretch(1)
        self._save = QPushButton(t("library.review_save", language), self)
        self._save.setEnabled(False)
        self._save.clicked.connect(self.save_requested)
        row.addWidget(self._save)
        layout.addLayout(row)

    def show_flow(self, flow: PrismaFlow) -> None:
        labels = prisma_labels(self._language)
        rows = [
            (labels["identified"], sum(flow.identified.values()), flow.identified),
            (labels["duplicates"], flow.duplicates_removed, {}),
            (labels["screened"], flow.unique, {}),
            (labels["awaiting"], flow.awaiting, {}),
            (labels["excluded"], flow.excluded_abstract, flow.reasons_abstract),
            (labels["full_text"], flow.full_text, {}),
            (labels["full_text_awaiting"], flow.full_text_awaiting, {}),
            (labels["excluded_full_text"], flow.excluded_full_text, flow.reasons_full_text),
            (labels["included"], flow.included, {}),
        ]
        lines: list[str] = []
        for label, count, parts in rows:
            lines.append(f"{label}: {count}")
            lines += [
                f"      {name or labels['no_reason']}: {value}" for name, value in parts.items()
            ]
        # Plain text: reasons are typed by the user and are not markup.
        self._text.setPlainText("\n".join(lines))
        self._save.setEnabled(True)

    def text(self) -> str:
        return self._text.toPlainText()

    def save_button(self) -> QPushButton:
        return self._save


class DuplicatesDialog(QDialog):
    """Groups of similar papers. The ticked ones of a group become one."""

    #: The paper ids to merge, the one to keep first.
    merge_requested = Signal(object)

    def __init__(
        self,
        groups: Sequence[Sequence[LibraryEntry]],
        language: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("library.duplicates_title", language))
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        hint = QLabel(
            t("library.duplicates_hint" if groups else "library.duplicates_none", language), self
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        body = QWidget(scroll)
        body_layout = QVBoxLayout(body)
        self._merge_buttons: list[QPushButton] = []
        self._boxes: list[list[tuple[QCheckBox, int]]] = []
        for group in groups:
            card, card_layout = make_card("", body)
            boxes: list[tuple[QCheckBox, int]] = []
            for entry in group:
                box = QCheckBox(_describe(entry), card)
                box.setChecked(True)
                card_layout.addWidget(box)
                boxes.append((box, entry.paper_id))
            button = QPushButton(t("library.action_merge", language), card)
            button.clicked.connect(lambda _c=False, b=boxes, w=button: self._merge(b, w))
            card_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)
            body_layout.addWidget(card)
            self._boxes.append(boxes)
            self._merge_buttons.append(button)
        body_layout.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll, stretch=1)
        buttons = QDialogButtonBox(self)
        close = QPushButton(t("action.close", language), self)
        close.clicked.connect(self.accept)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

    def _merge(self, boxes: list[tuple[QCheckBox, int]], button: QPushButton) -> None:
        ids = [paper_id for box, paper_id in boxes if box.isChecked()]
        if len(ids) < 2:
            return
        button.setEnabled(False)
        for box, _paper_id in boxes:
            box.setEnabled(False)
        self.merge_requested.emit(ids)

    def merge_button(self, group: int) -> QPushButton:
        return self._merge_buttons[group]

    def boxes(self, group: int) -> list[QCheckBox]:
        return [box for box, _paper_id in self._boxes[group]]


def _describe(entry: LibraryEntry) -> str:
    paper = entry.paper
    author = paper.authors[0] if paper.authors else "?"
    where = paper.venue or paper.doi or paper.arxiv_id or ", ".join(entry.sources)
    # A lone "&" in a check box label would become a keyboard shortcut.
    return f"{paper.title}\n{author}, {paper.year or 'n.d.'}, {where}".replace("&", "&&")

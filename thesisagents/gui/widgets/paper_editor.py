"""What the reader records about the selected papers of a library.

The widget holds no database: it emits an :class:`EditRequest`, and the
Library page applies it on a worker thread. With several papers selected,
the note is left alone and the tags typed are added to all of them.

Example::

    editor.requested.connect(page.apply_edit)
    editor.show_entries([entry])
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.i18n import t
from thesisagents.library import DECISIONS, READING_STATUSES, STAGES, Library, LibraryEntry


@dataclass(frozen=True)
class EditRequest:
    """One change to make. ``None`` leaves a field alone."""

    paper_ids: tuple[int, ...]
    add_tags: tuple[str, ...] = ()
    remove_tags: tuple[str, ...] = ()
    status: str | None = None
    note: str | None = None
    decision: str | None = None
    reason: str = ""
    stage: str = field(default=STAGES[0])

    def apply(self, library: Library) -> None:
        """Make the change, all of it or nothing. Blocking, for a worker thread."""
        with library.together():
            library.remove_tags(self.paper_ids, self.remove_tags)
            library.add_tags(self.paper_ids, self.add_tags)
            if self.status is not None:
                library.set_reading_status(self.paper_ids, self.status)
            if self.note is not None:
                library.set_note(self.paper_ids[0], self.note)
            if self.decision is not None:
                library.screen(
                    self.paper_ids, self.decision, reason=self.reason, stage=self.stage
                )


def split_tags(text: str) -> tuple[str, ...]:
    """Comma separated tags. The full-width comma counts too.

    >>> split_tags("a, b，c ,, ")
    ('a', 'b', 'c')
    """
    parts = text.replace("，", ",").replace("、", ",").split(",")
    return tuple(dict.fromkeys(part.strip() for part in parts if part.strip()))


class PaperEditor(QWidget):
    """Form for tags, reading status, note and screening decision."""

    #: An :class:`EditRequest`.
    requested = Signal(object)

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = language
        self._entries: tuple[LibraryEntry, ...] = ()
        self._shown_reason = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        self._heading = QLabel("", self)
        self._heading.setObjectName("Muted")
        self._heading.setWordWrap(True)
        layout.addWidget(self._heading)

        grid = QGridLayout()
        self._status = QComboBox(self)
        for status in READING_STATUSES:
            self._status.addItem(t(f"library.status_{status}", language), status)
        self._status.setAccessibleName(t("library.filter_status", language))
        self._tags = QLineEdit(self)
        self._tags.setPlaceholderText(t("library.edit_tags_placeholder", language))
        self._tags.setAccessibleName(t("library.col_tags", language))
        self._tags.returnPressed.connect(self._save)
        grid.addWidget(self._status, 0, 0)
        grid.addWidget(self._tags, 0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self._note = QPlainTextEdit(self)
        self._note.setPlaceholderText(t("library.edit_note_placeholder", language))
        self._note.setAccessibleName(t("library.edit_note_placeholder", language))
        self._note.setTabChangesFocus(True)
        self._note.setMaximumHeight(90)
        layout.addWidget(self._note)

        row = QHBoxLayout()
        self._stage = QComboBox(self)
        for stage in STAGES:
            self._stage.addItem(t(f"library.stage_{stage}", language), stage)
        self._stage.setAccessibleName(t("library.filter_decision", language))
        self._reason = QLineEdit(self)
        self._reason.setPlaceholderText(t("library.edit_reason_placeholder", language))
        self._reason.setAccessibleName(t("library.edit_reason_placeholder", language))
        self._stage.currentIndexChanged.connect(lambda _index: self._show_reason())
        row.addWidget(self._stage)
        row.addWidget(self._reason, stretch=1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self._buttons: dict[str, QPushButton] = {}
        for decision in DECISIONS:
            button = QPushButton(t(f"library.decision_{decision}", language), self)
            button.clicked.connect(lambda _checked=False, d=decision: self._decide(d))
            buttons.addWidget(button)
            self._buttons[decision] = button
        undo = QPushButton(t("library.edit_undo", language), self)
        undo.clicked.connect(lambda: self._decide(""))
        buttons.addWidget(undo)
        self._buttons[""] = undo
        buttons.addStretch(1)
        save = QPushButton(t("settings.save_button", language), self)
        save.setProperty("primary", True)
        save.clicked.connect(self._save)
        buttons.addWidget(save)
        self._buttons["save"] = save
        layout.addLayout(buttons)
        self.show_entries(())

    def show_entries(self, entries: Sequence[LibraryEntry]) -> None:
        """Fill the form from the selected papers (none disables it)."""
        self._entries = tuple(entries)
        single = self._entries[0] if len(self._entries) == 1 else None
        self.setEnabled(bool(self._entries))
        self._heading.setText(
            "" if single or not self._entries
            else t("library.edit_many", self._language, count=len(self._entries))
        )
        self._heading.setVisible(len(self._entries) > 1)
        self._note.setVisible(single is not None or not self._entries)
        self._note.setPlainText(single.note if single else "")
        self._tags.setText(", ".join(single.tags) if single else "")
        status = single.status if single else self._common_status()
        self._status.setCurrentIndex(self._status.findData(status))
        self._reason.clear()
        self._shown = (self._tags.text(), self._status.currentData(), self._note.toPlainText())
        self._shown_reason = self._reason.text()
        self._show_reason()

    def _show_reason(self) -> None:
        """The reason recorded at the chosen stage, unless one is being typed.

        Without the stage, the reason of a full-text exclusion was recorded
        again by a title and abstract decision.
        """
        if self._reason.text() != self._shown_reason:
            return
        stage = self._stage.currentData()
        recorded = self._entries[0].screening if len(self._entries) == 1 else ()
        self._reason.setText(next((s.reason for s in recorded if s.stage == stage), ""))
        self._shown_reason = self._reason.text()

    def _common_status(self) -> str:
        """The status all selected papers share, empty when they differ."""
        found = {entry.status for entry in self._entries}
        return found.pop() if len(found) == 1 else ""

    def _ids(self) -> tuple[int, ...]:
        return tuple(entry.paper_id for entry in self._entries)

    def _removed_tags(self, wanted: tuple[str, ...]) -> tuple[str, ...]:
        """Tags taken off. With several papers what is typed is only added."""
        if len(self._entries) != 1:
            return ()
        kept = {tag.casefold() for tag in wanted}
        return tuple(tag for tag in self._entries[0].tags if tag.casefold() not in kept)

    def _save(self) -> None:
        if not self._entries:
            return
        wanted = split_tags(self._tags.text())
        self.requested.emit(
            EditRequest(
                self._ids(),
                add_tags=wanted,
                remove_tags=self._removed_tags(wanted),
                status=self._status.currentData(),
                note=self._note.toPlainText() if len(self._entries) == 1 else None,
            )
        )

    def _decide(self, decision: str) -> None:
        if not self._entries:
            return
        # The form is filled again after the decision, so what was typed in it
        # and not saved goes along.
        tags, status, note = self._shown
        wanted = split_tags(self._tags.text()) if self._tags.text() != tags else None
        chosen, written = self._status.currentData(), self._note.toPlainText()
        self.requested.emit(
            EditRequest(
                self._ids(),
                add_tags=wanted or (),
                remove_tags=self._removed_tags(wanted) if wanted is not None else (),
                status=chosen if chosen != status else None,
                note=written if len(self._entries) == 1 and written != note else None,
                decision=decision,
                reason=self._reason.text().strip(),
                stage=self._stage.currentData(),
            )
        )

    # --- accessors used by tests ------------------------------------------

    def tags_input(self) -> QLineEdit:
        return self._tags

    def note_input(self) -> QPlainTextEdit:
        return self._note

    def status_combo(self) -> QComboBox:
        return self._status

    def stage_combo(self) -> QComboBox:
        return self._stage

    def reason_input(self) -> QLineEdit:
        return self._reason

    def button(self, name: str) -> QPushButton:
        """``include`` / ``maybe`` / ``exclude`` / ``""`` (undo) / ``save``."""
        return self._buttons[name]

"""Edit a finished deck: texts, order, added and deleted slides.

The editor works on a copy in a temporary folder, through the same functions
the MCP tools use (``exporters/pptx_edit.py``). The file on disk changes only
with **Save**, every step can be undone, and closing with unsaved changes
asks first.

Example::

    editor = DeckEditor("paper.pptx", "en", parent=page)
    editor.open()
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.exceptions import ExportError
from thesisagents.exporters import pptx_edit
from thesisagents.gui.i18n import t
from thesisagents.gui.widgets.slide_preview import render_slide

_THUMBNAIL_WIDTH: Final[int] = 176
_PREVIEW_WIDTH: Final[int] = 640
_MAX_UNDO: Final[int] = 30
_PPTX_FILTER: Final[str] = "PowerPoint (*.pptx)"
#: Shapes whose text is written by the exporter itself.
_AUTOMATIC: Final[frozenset[str]] = frozenset({"page_number"})


class DeckEditor(QDialog):
    """Slides on the left, the selected one and its texts on the right."""

    #: The path the deck was saved to.
    saved = Signal(str)

    def __init__(self, path: str, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = language
        self._path = Path(path)
        self._folder = Path(tempfile.mkdtemp(prefix="thesisagents_deck_"))
        self._work = self._folder / "deck.pptx"
        shutil.copyfile(self._path, self._work)
        self._undo: list[bytes] = []
        self._dirty = False
        self._boxes: list[tuple[int, str, QPlainTextEdit]] = []
        self._shown = 0
        self.setWindowTitle(f"{t('slides.title', language)}: {self._path.name}")
        self.resize(1100, 720)
        self._build()
        self.destroyed.connect(_remover(self._folder))
        # The working copy goes with the dialog, so a closed one must not linger.
        self.finished.connect(self.deleteLater)
        self._reload(0)

    def _build(self) -> None:
        language = self._language
        layout = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal, self)
        self._list = QListWidget(split)
        self._list.setIconSize(QSize(_THUMBNAIL_WIDTH, _THUMBNAIL_WIDTH * 9 // 16))
        self._list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._list.setAccessibleName(t("slides.title", language))
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.model().rowsMoved.connect(lambda *_: self._on_reordered())
        split.addWidget(self._list)
        right = QWidget(split)
        right_layout = QVBoxLayout(right)
        self._preview = QLabel(right)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(200)
        right_layout.addWidget(self._preview)
        hint = QLabel(t("slides.preview_hint", language), right)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        right_layout.addWidget(hint)
        self._form_scroll = QScrollArea(right)
        self._form_scroll.setWidgetResizable(True)
        self._form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_layout.addWidget(self._form_scroll, stretch=1)
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([230, 870])
        layout.addWidget(split, stretch=1)

        row = QHBoxLayout()
        self._buttons: dict[str, QPushButton] = {}
        for name, key, slot in (
            ("apply", "slides.apply", self.apply_texts),
            ("add", "slides.add", self.add_slide),
            ("delete", "library.action_delete", self.delete_slide),
            ("up", "slides.up", lambda: self.move_slide(-1)),
            ("down", "slides.down", lambda: self.move_slide(1)),
            ("undo", "slides.undo", self.undo),
        ):
            button = QPushButton(t(key, language), self)
            button.clicked.connect(slot)
            row.addWidget(button)
            self._buttons[name] = button
        row.addStretch(1)
        layout.addLayout(row)
        self._status = QLabel("", self)
        self._status.setObjectName("Muted")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        buttons = QDialogButtonBox(self)
        for name, key, slot in (
            ("save", "settings.save_button", self.save),
            ("save_as", "slides.save_as", self._on_save_as),
        ):
            button = QPushButton(t(key, language), self)
            button.setProperty("primary", name == "save")
            button.clicked.connect(slot)
            buttons.addButton(button, QDialogButtonBox.ButtonRole.ActionRole)
            self._buttons[name] = button
        close = QPushButton(t("action.close", language), self)
        close.clicked.connect(self.reject)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Save), self).activated.connect(self.save)

    # --- showing ------------------------------------------------------------

    def _reload(self, current: int) -> None:
        """Read the working copy again and show slide ``current``."""
        presentation = pptx_edit._open(self._work)  # noqa: SLF001 - same package family
        size = (presentation.slide_width, presentation.slide_height)
        self._views = pptx_edit.inspect(self._work)
        self._images: list[QImage] = [
            render_slide(slide, size, _PREVIEW_WIDTH) for slide in presentation.slides
        ]
        self._list.blockSignals(True)
        self._list.clear()
        for index, (view, image) in enumerate(zip(self._views, self._images, strict=True)):
            thumbnail = image.scaledToWidth(
                _THUMBNAIL_WIDTH, Qt.TransformationMode.SmoothTransformation
            )
            item = QListWidgetItem(QIcon(QPixmap.fromImage(thumbnail)), str(index + 1))
            item.setToolTip(view.title)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._list.addItem(item)
        self._list.blockSignals(False)
        row = min(max(0, current), self._list.count() - 1)
        self._list.setCurrentRow(row)
        self._show_slide(row)
        self._refresh_buttons()

    def _on_row_changed(self, row: int) -> None:
        """Another slide was selected: keep what was typed on the one before."""
        if row != self._shown and self._pending():
            changes, shown = self._pending(), self._shown
            self._boxes = []
            self._edit(
                lambda: pptx_edit.update_slide(self._work, shown, shape_updates=changes), row
            )
            return
        self._show_slide(row)

    def _show_slide(self, row: int) -> None:
        self._shown = row
        self._boxes = []
        form = QWidget(self._form_scroll)
        layout = QVBoxLayout(form)
        if 0 <= row < len(self._views):
            self._preview.setPixmap(QPixmap.fromImage(self._images[row]))
            for shape in self._views[row].shapes:
                if not shape.text.strip() or (shape.name or "").lower() in _AUTOMATIC:
                    continue
                label = QLabel(shape.name, form)
                label.setObjectName("Muted")
                box = QPlainTextEdit(shape.text, form)
                box.setAccessibleName(shape.name)
                box.setTabChangesFocus(True)
                lines = shape.text.count("\n") + 1
                box.setFixedHeight(min(220, 28 + lines * (box.fontMetrics().height() + 2)))
                layout.addWidget(label)
                layout.addWidget(box)
                self._boxes.append((shape.index, shape.text, box))
                box.textChanged.connect(self._refresh_buttons)
        layout.addStretch(1)
        self._form_scroll.setWidget(form)
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        count = self._list.count()
        row = self._list.currentRow()
        self._buttons["delete"].setEnabled(count > 1)
        self._buttons["up"].setEnabled(row > 0)
        self._buttons["down"].setEnabled(0 <= row < count - 1)
        self._buttons["undo"].setEnabled(bool(self._undo))
        self._buttons["apply"].setEnabled(bool(self._boxes))
        self._buttons["save"].setEnabled(self._dirty or self._pending() != {})

    # --- editing ---------------------------------------------------------------

    def _pending(self) -> dict[int, str]:
        """Texts changed in the form and not applied yet."""
        return {
            index: box.toPlainText()
            for index, before, box in self._boxes
            if box.toPlainText() != before
        }

    def _edit(self, change: Callable[[], object], current: int) -> bool:
        """Run one step on the working copy, keeping the state before it."""
        before = self._work.read_bytes()
        try:
            change()
        except (ExportError, OSError) as err:
            self._work.write_bytes(before)
            self._status.setText(t("deck.check_failed", self._language, error=str(err)))
            return False
        self._undo = [*self._undo[-(_MAX_UNDO - 1):], before]
        self._dirty = True
        self._status.setText("")
        self._reload(current)
        return True

    def apply_texts(self) -> bool:
        """Write the texts of the form into the slide. True when there were any."""
        changes = self._pending()
        row = self._list.currentRow()
        if not changes:
            return False
        return self._edit(
            lambda: pptx_edit.update_slide(self._work, row, shape_updates=changes), row
        )

    def add_slide(self) -> None:
        """A new slide after the selected one, in the deck's own look."""
        self.apply_texts()
        position = self._list.currentRow() + 1
        title = t("slides.new_title", self._language)
        body = t("slides.new_body", self._language)
        self._edit(
            lambda: pptx_edit.add_slide(self._work, title=title, body=body, position=position),
            position,
        )

    def delete_slide(self) -> None:
        row = self._list.currentRow()
        if self._list.count() > 1:
            self._edit(lambda: pptx_edit.delete_slide(self._work, row), row)

    def move_slide(self, step: int) -> None:
        """Move the selected slide up (-1) or down (1)."""
        self.apply_texts()
        row = self._list.currentRow()
        target = row + step
        if not 0 <= target < self._list.count():
            return
        order = list(range(self._list.count()))
        order.insert(target, order.pop(row))
        self._edit(lambda: pptx_edit.reorder_slides(self._work, order), target)

    def _on_reordered(self) -> None:
        """The user dragged a thumbnail."""
        order = [
            self._list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self._list.count())
        ]
        if order != sorted(order):
            self._edit(
                lambda: pptx_edit.reorder_slides(self._work, order), self._list.currentRow()
            )

    def undo(self) -> None:
        """Take the last step back."""
        if not self._undo:
            return
        self._work.write_bytes(self._undo.pop())
        self._dirty = bool(self._undo)
        self._reload(self._list.currentRow())

    # --- saving ------------------------------------------------------------------

    def save(self) -> bool:
        return self.save_to(str(self._path))

    def save_to(self, path: str) -> bool:
        """Write the deck to ``path``, whole or not at all."""
        self.apply_texts()
        target = Path(path)
        temporary = target.with_name(f".{target.name}.saving")
        try:
            shutil.copyfile(self._work, temporary)
            os.replace(temporary, target)
        except OSError as err:
            temporary.unlink(missing_ok=True)
            # Usually the deck is open in PowerPoint, which locks it.
            self._status.setText(t("slides.save_failed", self._language, error=str(err)))
            return False
        self._path = target
        self._dirty = False
        self._undo = []
        self._status.setText(t("library.status_saved", self._language))
        self._refresh_buttons()
        self.saved.emit(str(target))
        return True

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("slides.save_as", self._language), str(self._path), _PPTX_FILTER
        )
        if path:
            self.save_to(path if path.lower().endswith(".pptx") else path + ".pptx")

    def reject(self) -> None:
        if (self._dirty or self._pending()) and not self._confirm_discard():
            return
        super().reject()

    def _confirm_discard(self) -> bool:
        answer = QMessageBox.question(
            self, t("slides.title", self._language), t("summary.discard", self._language)
        )
        return answer == QMessageBox.StandardButton.Yes

    # --- accessors used by tests ----------------------------------------------

    def slide_list(self) -> QListWidget:
        return self._list

    def text_boxes(self) -> dict[str, QPlainTextEdit]:
        return {box.accessibleName(): box for _index, _before, box in self._boxes}

    def button(self, name: str) -> QPushButton:
        return self._buttons[name]

    def status_text(self) -> str:
        return self._status.text()

    def preview(self) -> QPixmap:
        return self._preview.pixmap()

    def working_folder(self) -> Path:
        return self._folder


def _remover(folder: Path) -> Callable[..., None]:
    """Deletes the working copy when the dialog goes."""

    def remove(*_args: object) -> None:
        shutil.rmtree(folder, ignore_errors=True)

    return remove

"""Sidebar navigation that collapses to an icon rail on narrow windows.

Replaces the ``QTabWidget`` the window used before. Tabs across the top
had two problems the sidebar fixes: on a narrow window, the four tab labels
in German or Russian ran out of room and Qt added scroll arrows, and a tab
strip has nowhere to show that a step has data waiting (the Enrich and Deck
entries now carry the paper count once a search finishes).

Expanded, each entry shows its icon and label. Compact (64 px), only the
icon shows, and the label moves to the tooltip. The main window collapses
the rail on compact windows, and the menu button at the top toggles it by
hand at any width.

Example::

    rail = NavRail(brand="ThesisAgents", toggle_tip="Collapse or expand")
    rail.add_item("search", "Search")
    rail.current_changed.connect(stack.setCurrentIndex)
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.font_size import layout_scale
from thesisagents.gui.icons import ICON_SIZE, nav_icon
from thesisagents.gui.theme import Palette, current_palette

#: Width with labels. Larger text widens the rail (``refresh_width``).
EXPANDED_WIDTH: Final[int] = 208
COMPACT_WIDTH: Final[int] = 64
#: The checked entry is bold, so it needs more than its size hint says.
_LABEL_SLACK: Final[int] = 12


class NavRail(QFrame):
    """The sidebar: a brand row, the page entries, and a bottom group."""

    #: The index of the entry the user picked.
    current_changed = Signal(int)

    def __init__(self, brand: str, toggle_tip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NavRail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._brand_text = brand
        self._compact = False
        self._buttons: list[QPushButton] = []
        self._icons: list[str] = []
        self._labels: list[str] = []
        self._badges: list[str] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self._on_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self._toggle = QPushButton(self)
        self._toggle.setObjectName("NavButton")
        self._toggle.setToolTip(toggle_tip)
        self._toggle.setAccessibleName(toggle_tip)
        self._toggle.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        self._toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle.clicked.connect(lambda: self.set_compact(not self._compact))
        self._brand = QLabel(brand, self)
        self._brand.setObjectName("NavBrand")
        top.addWidget(self._toggle)
        top.addWidget(self._brand, stretch=1)
        layout.addLayout(top)
        layout.addSpacing(14)

        self._items_layout = QVBoxLayout()
        self._items_layout.setSpacing(4)
        layout.addLayout(self._items_layout)
        layout.addStretch(1)
        self._bottom_layout = QVBoxLayout()
        self._bottom_layout.setSpacing(4)
        layout.addLayout(self._bottom_layout)

        self.refresh_icons()
        self._apply_width()

    # --- building -----------------------------------------------------

    def add_item(self, icon: str, label: str, *, bottom: bool = False) -> int:
        """Append an entry and return its index. ``bottom`` pins it low."""
        index = len(self._buttons)
        button = QPushButton(self)
        button.setObjectName("NavButton")
        button.setCheckable(True)
        button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._group.addButton(button, index)
        (self._bottom_layout if bottom else self._items_layout).addWidget(button)
        self._buttons.append(button)
        self._icons.append(icon)
        self._labels.append(label)
        self._badges.append("")
        tokens = current_palette()
        button.setIcon(nav_icon(icon, tokens.nav_muted, tokens.nav_text))
        self._refresh_button(index)
        if index == 0:
            button.setChecked(True)
        return index

    # --- state ----------------------------------------------------------

    def count(self) -> int:
        return len(self._buttons)

    def current(self) -> int:
        return self._group.checkedId()

    def set_current(self, index: int) -> None:
        """Select entry ``index`` and emit :attr:`current_changed`."""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
            self.current_changed.emit(index)

    def is_compact(self) -> bool:
        return self._compact

    def set_compact(self, compact: bool) -> None:
        """Show icons only (``True``) or icons with labels (``False``)."""
        if compact == self._compact:
            return
        self._compact = compact
        for index in range(len(self._buttons)):
            self._refresh_button(index)
        self._apply_width()

    def set_badge(self, index: int, text: str) -> None:
        """Show ``text`` (a paper count) after the label of entry ``index``."""
        if 0 <= index < len(self._buttons):
            self._badges[index] = text
            self._refresh_button(index)
            self._apply_width()

    def button_text(self, index: int) -> str:
        """What entry ``index`` shows now (empty while compact)."""
        return self._buttons[index].text()

    def button_tooltip(self, index: int) -> str:
        return self._buttons[index].toolTip()

    def refresh_icons(self, palette: Palette | None = None) -> None:
        """Repaint every icon in ``palette``'s sidebar colours (after a theme switch)."""
        tokens = palette or current_palette()
        self._toggle.setIcon(nav_icon("menu", tokens.nav_muted, tokens.nav_text))
        for index, button in enumerate(self._buttons):
            button.setIcon(nav_icon(self._icons[index], tokens.nav_muted, tokens.nav_text))

    def refresh_width(self) -> None:
        """Fit the rail to its labels again (after a font size change)."""
        self._apply_width()

    # --- internals ------------------------------------------------------

    def _on_clicked(self, index: int) -> None:
        self.current_changed.emit(index)

    def _caption(self, index: int) -> str:
        badge = self._badges[index]
        label = self._labels[index]
        return f"{label}  ·  {badge}" if badge else label

    def _refresh_button(self, index: int) -> None:
        button = self._buttons[index]
        caption = self._caption(index)
        button.setText("" if self._compact else f"  {caption}")
        button.setToolTip(caption)
        button.setAccessibleName(caption)

    def _apply_width(self) -> None:
        self._brand.setVisible(not self._compact)
        self.setFixedWidth(COMPACT_WIDTH if self._compact else self._expanded_width())

    def _expanded_width(self) -> int:
        """:data:`EXPANDED_WIDTH`, or what the widest label needs at this font size."""
        if layout_scale() <= 1.0:
            return EXPANDED_WIDTH
        for button in self._buttons:
            button.ensurePolished()
        self._brand.ensurePolished()
        margins = self.layout().contentsMargins()
        brand_row = self._toggle.sizeHint().width() + self._brand.sizeHint().width()
        widest = max([brand_row, *(button.sizeHint().width() for button in self._buttons)])
        return max(EXPANDED_WIDTH, widest + margins.left() + margins.right() + _LABEL_SLACK)

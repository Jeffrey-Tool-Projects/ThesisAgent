"""Building blocks that let the GUI adapt its layout to the window width.

The boundary this module guards: how a page arranges itself as the window
narrows. Before it, every page was one fixed vertical form inside a scroll
area, so a wide window left most of the screen empty beside a stretched
form, and the window could not go below 900 x 600 without clipping. The
pieces here answer three questions:

* **How wide is the window?** :func:`breakpoint_for_width` maps a width to a
  :class:`Breakpoint` (compact / medium / expanded, the same three size
  classes Material and Fluent use), and the main window tells every page
  when the class changes.
* **Where do the controls go?** :class:`AdaptiveSplit` puts a page's controls
  beside its results on an expanded window and above them otherwise.
* **How do a group's items wrap?** :class:`ReflowGrid` re-flows a set of
  widgets (the source check boxes, the export formats) into as many columns
  as fit its own width, and :func:`adapt_form_rows` moves a form's labels
  above their fields when the form is narrow.

Example::

    split = AdaptiveSplit(controls, results, footer=buttons)
    split.apply_breakpoint(breakpoint_for_width(window.width()))
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Final

from PySide6.QtCore import QEvent, QObject, QSize, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.font_size import layout_scale, table_row_height


class Breakpoint(Enum):
    """The window size class a page lays itself out for."""

    COMPACT = "compact"
    MEDIUM = "medium"
    EXPANDED = "expanded"


#: Below this window width the sidebar collapses to icons and forms put
#: their labels above the fields.
COMPACT_MAX_WIDTH: Final[int] = 760
#: From this width up, controls sit beside the results instead of above them.
EXPANDED_MIN_WIDTH: Final[int] = 1180


def breakpoint_for_width(width: int, scale: float = 1.0) -> Breakpoint:
    """The size class for a window ``width`` pixels wide.

    ``scale`` is how much larger than the default the interface text is. The
    size classes were drawn for the default, so a 1400 px window with text
    twice as big has the room of a 700 px one and is laid out as such.

    >>> breakpoint_for_width(640).value, breakpoint_for_width(1000).value
    ('compact', 'medium')
    >>> breakpoint_for_width(1280).value
    'expanded'
    >>> breakpoint_for_width(1400, scale=2.0).value
    'compact'
    """
    if width < COMPACT_MAX_WIDTH * scale:
        return Breakpoint.COMPACT
    if width < EXPANDED_MIN_WIDTH * scale:
        return Breakpoint.MEDIUM
    return Breakpoint.EXPANDED


# --- cards ------------------------------------------------------------


def make_card(title: str | None, parent: QWidget | None = None) -> tuple[QFrame, QVBoxLayout]:
    """A rounded panel (``#Card`` in the stylesheet) and its content layout.

    Replaces ``QGroupBox``: a group box draws its title on the frame line,
    which the Fusion style renders as a thin grey caption that is easy to
    miss, and it cannot be themed without restyling its indicator. The card
    puts a bold title above its content instead.
    """
    card = QFrame(parent)
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 16)
    layout.setSpacing(10)
    if title:
        heading = QLabel(title, card)
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)
    return card, layout


# --- forms ------------------------------------------------------------

#: Below this width a form puts each label above its field.
FORM_WRAP_WIDTH: Final[int] = 460


class _FormWrapFilter(QObject):
    """Switches one form's row-wrap policy as its container or its text resizes.

    Only the width in view counts. Inside a scroll area a container is
    stretched to its own minimum width, and that minimum depends on the
    policy: with the labels beside the fields it is wider. Judging by the
    stretched width made the answer depend on itself. With a threshold
    between the two minimums (1104 px between 1052 and 1466 at 24 pt) the
    page changed back and forth within one call until the stack overflowed,
    and a form widened once kept its labels beside the fields in a pane too
    narrow to show both.
    """

    def __init__(self, container: QWidget, form: QFormLayout, threshold: int) -> None:
        super().__init__(container)
        self._container = container
        self._form = form
        self._threshold = threshold
        self._viewports: list[QWidget] = []

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt override
        if event.type() in (QEvent.Type.Resize, QEvent.Type.FontChange):
            self.apply()
        return False

    def visible_width(self) -> int:
        """The container's width, at most that of every scroll area around it."""
        self._watch_viewports()
        return min([self._container.width(), *(view.width() for view in self._viewports)])

    def _watch_viewports(self) -> None:
        """Find the scroll areas around the container, which joins them after it is built.

        Their viewports are watched too: a pane that narrows leaves a
        stretched container as wide as it was, so the container says nothing.
        """
        viewports = []
        ancestor = self._container.parentWidget()
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                viewports.append(ancestor.viewport())
            ancestor = ancestor.parentWidget()
        for view in viewports:
            if view not in self._viewports:
                view.installEventFilter(self)
        for view in self._viewports:
            if view not in viewports:
                view.removeEventFilter(self)
        self._viewports = viewports

    def apply(self) -> None:
        policy = (
            QFormLayout.RowWrapPolicy.WrapAllRows
            if self.visible_width() < self._threshold * layout_scale()
            else QFormLayout.RowWrapPolicy.DontWrapRows
        )
        if self._form.rowWrapPolicy() != policy:
            self._form.setRowWrapPolicy(policy)


def adapt_form_rows(
    container: QWidget, form: QFormLayout, threshold: int = FORM_WRAP_WIDTH
) -> None:
    """Put ``form``'s labels above their fields while ``container`` is narrow.

    It watches the container's own width rather than the window's, because
    the same form is narrow in the side pane of an expanded window and wide
    when stacked on a medium one. Labels in languages with long words
    (German, Russian) otherwise squeeze the fields to a few characters. In a
    scroll area the part of that width in view counts, see
    :class:`_FormWrapFilter`.
    """
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    watcher = _FormWrapFilter(container, form, threshold)
    container.installEventFilter(watcher)
    watcher.apply()


# --- reflowing grid ---------------------------------------------------


class ReflowGrid(QWidget):
    """A grid that re-flows its widgets into as many columns as fit.

    Every cell is as wide as the widest widget, so the items line up in
    columns at any width (a flow layout would leave a ragged right edge).
    The grid reports a one-column minimum width and its height for a given
    width, so a parent layout can shrink it and give it the rows it needs.

    It places its children itself instead of using a ``QGridLayout``: Qt
    asks a widget's *layout*, not the widget, for its height-for-width, so a
    grid layout inside would hide the row count from the parent and the
    grid would be given no height at all.

    Example::

        grid = ReflowGrid([QCheckBox(name) for name in ALL_SOURCES])
        grid.columns_for_width(480)   # 3 with ~150 px boxes
    """

    _H_SPACING: Final[int] = 12
    _V_SPACING: Final[int] = 6
    _SLACK: Final[int] = 8

    def __init__(
        self,
        widgets: Sequence[QWidget],
        *,
        max_columns: int = 6,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._items: tuple[QWidget, ...] = tuple(widgets)
        self._max_columns = max(1, max_columns)
        self._columns = 1
        for item in self._items:
            item.setParent(self)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def columns(self) -> int:
        """How many columns the items were last laid out in."""
        return self._columns

    def _cell_width(self) -> int:
        # A widget on a page that has never been shown is not polished yet,
        # so its size hint ignores the stylesheet (a 16 px check-box
        # indicator) and the cells come out too narrow, clipping labels.
        for item in self._items:
            item.ensurePolished()
        widest = max((item.sizeHint().width() for item in self._items), default=1)
        # Slack for styles whose indicator border is drawn outside the size
        # the check box reports (Material's 2 px outline clipped the last
        # letters of "Markdown" without it).
        return widest + self._H_SPACING + self._SLACK

    def _row_height(self) -> int:
        tallest = max((item.sizeHint().height() for item in self._items), default=1)
        return tallest + self._V_SPACING

    def columns_for_width(self, width: int) -> int:
        """The column count a grid ``width`` pixels wide would use."""
        fit = (width + self._H_SPACING) // max(1, self._cell_width())
        return max(1, min(self._max_columns, len(self._items) or 1, fit))

    def _place(self, width: int) -> None:
        columns = self.columns_for_width(width)
        cell = max(1, width // columns)
        row_height = self._row_height()
        for index, item in enumerate(self._items):
            row, column = divmod(index, columns)
            item.setGeometry(
                column * cell,
                row * row_height,
                max(1, cell - self._H_SPACING),
                row_height - self._V_SPACING,
            )
        if columns != self._columns:
            self._columns = columns
            self.updateGeometry()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._place(event.size().width())
        super().resizeEvent(event)

    def event(self, event: QEvent) -> bool:
        # Posted when an item's size hint changes, which happens when the
        # interface font does. Nothing else would move the items then, and
        # the larger labels would be cut off in the old cells.
        if event.type() == QEvent.Type.LayoutRequest:
            self._place(self.width())
            self.updateGeometry()
        return super().event(event)

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt override
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt override
        columns = self.columns_for_width(width)
        rows = -(-len(self._items) // columns)
        return max(0, rows * self._row_height() - self._V_SPACING)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(self._cell_width(), self._row_height())

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        width = min(3, len(self._items) or 1) * self._cell_width()
        return QSize(width, self.heightForWidth(width))


# --- controls beside / above results ----------------------------------

#: Width of the controls pane when it sits beside the results.
SIDE_PANE_WIDTH: Final[int] = 420
#: How far the user can drag that column's edge.
_SIDE_PANE_MIN: Final[int] = 320
_SIDE_PANE_MAX: Final[int] = 640
#: The results pane never gets shorter than this when stacked, so the
#: table always shows a few rows.
_RESULTS_MIN_HEIGHT: Final[int] = 220
#: The controls pane keeps at least this much of itself in view with
#: enlarged text, when its page has to scroll anyway.
_CONTROLS_MIN_HEIGHT: Final[int] = 100


class AdaptiveSplit(QSplitter):
    """A page's controls and results, side by side or stacked.

    On an expanded window the controls take a :data:`SIDE_PANE_WIDTH` column
    on the left and the results fill the rest. On medium and compact windows
    the controls sit above the results. Either way the controls scroll on
    their own and an optional ``footer`` (the page's action buttons) stays
    pinned below them, so the main action never scrolls out of reach.

    The user can drag the handle; a breakpoint change resets the sizes.
    """

    def __init__(
        self,
        controls: QWidget,
        results: QWidget,
        *,
        footer: QWidget | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(8)
        self._breakpoint: Breakpoint | None = None
        self._scale = 1.0

        side = QWidget(self)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)
        scroll = QScrollArea(side)
        scroll.setWidget(controls)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        side_layout.addWidget(scroll, stretch=1)
        if footer is not None:
            side_layout.addWidget(footer)
        self._scroll = scroll
        self._side = side
        self._results = results

        results.setMinimumHeight(_RESULTS_MIN_HEIGHT)
        self.addWidget(side)
        self.addWidget(results)
        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 1)

    def controls_scroll(self) -> QScrollArea:
        """The scroll area holding the controls (tests read its policy)."""
        return self._scroll

    def current_breakpoint(self) -> Breakpoint | None:
        return self._breakpoint

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Arrange the panes for ``breakpoint`` and the font size. Idempotent."""
        scale = layout_scale()
        if (breakpoint, scale) == (self._breakpoint, self._scale):
            return
        self._breakpoint = breakpoint
        self._scale = scale
        self._fit_minimums(scale)
        if breakpoint is Breakpoint.EXPANDED:
            self.setOrientation(Qt.Orientation.Horizontal)
            self._side.setMinimumWidth(round(_SIDE_PANE_MIN * scale))
            self._side.setMaximumWidth(round(_SIDE_PANE_MAX * scale))
            side = round(SIDE_PANE_WIDTH * scale)
            total = max(self.width(), side * 2)
            self.setSizes([side, total - side])
        else:
            self.setOrientation(Qt.Orientation.Vertical)
            self._side.setMinimumWidth(0)
            self._side.setMaximumWidth(16_777_215)
            total = max(self.height(), 600)
            # Controls get up to 55 % of the height, never more than they need.
            wanted = self._scroll.widget().sizeHint().height() + 70
            top = min(wanted, int(total * 0.55))
            self.setSizes([top, total - top])

    def _fit_minimums(self, scale: float) -> None:
        """Keep both panes tall enough for enlarged text.

        An explicit minimum height replaces the one Qt works out from the
        pane's content, so a fixed 220 px let the filter row, the buttons and
        the table overlap at 24 pt. The page scrolls when the two do not fit.
        """
        results = _RESULTS_MIN_HEIGHT
        controls = 0
        if scale > 1.0:
            needed = self._results.minimumSizeHint().height() + table_row_height()
            results = max(results, needed)
            controls = round(_CONTROLS_MIN_HEIGHT * scale)
        self._results.setMinimumHeight(results)
        self._scroll.setMinimumHeight(controls)
        # A check box cannot wrap its label, so enlarged ones outgrow the pane.
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if scale > 1.0
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

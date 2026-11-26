"""The citation links of a library as a drawing.

Papers stand in columns by year, oldest on the left, so an arrow always
points back in time to the paper it cites. Within a column they are ordered
to keep connected papers close (a few barycentre passes), which is enough to
read a graph of a few hundred papers and needs no extra package.

Example::

    nodes = [GraphNode("doi:10.1/a", "Attention", 2017, 90000), ...]
    graph.show_graph(nodes, [("doi:10.1/b", "doi:10.1/a")])
    graph.node_clicked.connect(page.select_key)
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from thesisagents.gui.theme import current_palette

_COLUMN_WIDTH: Final[float] = 170.0
_ROW_HEIGHT: Final[float] = 46.0
_PASSES: Final[int] = 8
_MIN_RADIUS: Final[float] = 6.0
_MAX_RADIUS: Final[float] = 18.0
_LABEL_CHARS: Final[int] = 22
_ARROW: Final[float] = 7.0
#: A large graph scrolls rather than being shrunk until nobody can read it.
_SMALLEST_SCALE: Final[float] = 0.7


@dataclass(frozen=True)
class GraphNode:
    """One paper: its key, what to write beside it, and how big to draw it."""

    key: str
    title: str
    year: int | None
    citations: int | None = None


def layout(
    nodes: Sequence[GraphNode], edges: Iterable[tuple[str, str]]
) -> dict[str, tuple[float, float]]:
    """Positions by key. Deterministic, so a drawing does not jump on reload.

    Papers without a year share the first column, left of the oldest.
    """
    years = sorted({node.year for node in nodes if node.year is not None})
    column_of = {year: index + 1 for index, year in enumerate(years)}
    columns: dict[int, list[str]] = {}
    for node in sorted(nodes, key=lambda n: (n.title.casefold(), n.key)):
        column = column_of[node.year] if node.year is not None else 0
        columns.setdefault(column, []).append(node.key)
    neighbours: dict[str, list[str]] = {node.key: [] for node in nodes}
    for source, target in edges:
        if source in neighbours and target in neighbours and source != target:
            neighbours[source].append(target)
            neighbours[target].append(source)
    row = {key: float(i) for keys in columns.values() for i, key in enumerate(keys)}
    for _pass in range(_PASSES):
        for keys in columns.values():
            keys.sort(
                key=lambda key: (
                    sum(row[other] for other in neighbours[key]) / len(neighbours[key])
                    if neighbours[key] else row[key],
                    row[key],
                )
            )
            # Columns are centred on each other, so a short one does not cling to the top.
            offset = -(len(keys) - 1) / 2
            row.update({key: offset + i for i, key in enumerate(keys)})
    return {
        key: (column * _COLUMN_WIDTH, row[key] * _ROW_HEIGHT)
        for column, keys in columns.items()
        for key in keys
    }


def radius(citations: int | None) -> float:
    """Node size: grows with the logarithm, so one famous paper does not fill the view."""
    if not citations or citations < 0:
        return _MIN_RADIUS
    return min(_MAX_RADIUS, _MIN_RADIUS + 2.2 * math.log10(citations + 1))


class _Node(QGraphicsEllipseItem):
    """A paper's circle. Clicking it reports its key."""

    def __init__(self, node: GraphNode, size: float, view: CitationGraph) -> None:
        super().__init__(-size, -size, 2 * size, 2 * size)
        self.node = node
        self._view = view
        self.setToolTip(node.title + (f" ({node.year})" if node.year else ""))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(2)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802 - Qt override
        self._view.select(self.node.key)
        self._view.node_clicked.emit(self.node.key)
        event.accept()


class CitationGraph(QGraphicsView):
    """Draws the graph. Wheel with Ctrl zooms, dragging pans."""

    #: The key of the paper whose circle was clicked.
    node_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._nodes: dict[str, _Node] = {}
        self._edges: list[tuple[str, str, QGraphicsLineItem, QGraphicsPolygonItem]] = []
        self._labels: dict[str, QGraphicsSimpleTextItem] = {}
        self._years: list[QGraphicsSimpleTextItem] = []
        self._selected = ""

    def show_graph(
        self, nodes: Sequence[GraphNode], edges: Sequence[tuple[str, str]]
    ) -> None:
        """Replace the drawing. Only papers with a link are drawn."""
        # Forget the items before the scene deletes them: touching one after
        # that is a crash, not an exception.
        self._nodes.clear()
        self._edges.clear()
        self._labels.clear()
        self._years.clear()
        scene = self.scene()
        scene.clear()
        linked = {key for edge in edges for key in edge}
        shown = [node for node in nodes if node.key in linked]
        keys = {node.key for node in shown}
        drawn = [edge for edge in dict.fromkeys(edges) if edge[0] in keys and edge[1] in keys]
        places = layout(shown, drawn)
        sizes = {node.key: radius(node.citations) for node in shown}
        for citing, cited in drawn:
            line, head = self._draw_edge(places, sizes, citing, cited)
            self._edges.append((citing, cited, line, head))
        for node in shown:
            item = _Node(node, sizes[node.key], self)
            item.setPos(*places[node.key])
            scene.addItem(item)
            label = scene.addSimpleText(_shorten(node.title))
            label.setFont(self.font())
            label.setPos(
                places[node.key][0] - label.boundingRect().width() / 2,
                places[node.key][1] + sizes[node.key] + 1,
            )
            label.setZValue(1)
            self._labels[node.key] = label
            self._nodes[node.key] = item
        self._draw_years(shown, places)
        self._selected = ""
        self.repaint_colours()
        margin = 40
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin))

    def _draw_edge(
        self,
        places: Mapping[str, tuple[float, float]],
        sizes: Mapping[str, float],
        citing: str,
        cited: str,
    ) -> tuple[QGraphicsLineItem, QGraphicsPolygonItem]:
        start, end = QPointF(*places[citing]), QPointF(*places[cited])
        delta = end - start
        length = math.hypot(delta.x(), delta.y()) or 1.0
        unit = delta / length
        tip = end - unit * (sizes[cited] + 2)
        across = QPointF(-unit.y(), unit.x()) * _ARROW / 2
        back = tip - unit * _ARROW
        line = self.scene().addLine(start.x(), start.y(), back.x(), back.y())
        head = self.scene().addPolygon(QPolygonF([tip, back + across, back - across]))
        return line, head

    def _draw_years(
        self, nodes: Sequence[GraphNode], places: Mapping[str, tuple[float, float]]
    ) -> None:
        if not nodes:
            return
        top = min(y for _x, y in places.values()) - 60
        for year, x in sorted({(node.year or 0, places[node.key][0]) for node in nodes}):
            text = self.scene().addSimpleText(str(year) if year else "n.d.")
            text.setFont(self.font())
            text.setPos(x - text.boundingRect().width() / 2, top)
            self._years.append(text)

    def select(self, key: str) -> None:
        """Highlight one paper and its links (an unknown key clears it)."""
        self._selected = key if key in self._nodes else ""
        self.repaint_colours()

    def repaint_colours(self) -> None:
        """Take the colours of the current theme."""
        tokens = current_palette()
        self.setBackgroundBrush(QColor(tokens.surface))
        near = {self._selected}
        for citing, cited, *_items in self._edges:
            if self._selected in (citing, cited):
                near |= {citing, cited}
        for citing, cited, line, head in self._edges:
            lit = bool(self._selected) and self._selected in (citing, cited)
            colour = QColor(tokens.accent if lit else tokens.border)
            line.setPen(QPen(colour, 1.6 if lit else 1.0))
            head.setPen(QPen(colour))
            head.setBrush(QBrush(colour))
            for drawn in (line, head):
                drawn.setZValue(0.5 if lit else 0)
        for key, item in self._nodes.items():
            dim = bool(self._selected) and key not in near
            fill = QColor(tokens.accent if key == self._selected else tokens.nav_active)
            fill.setAlphaF(0.35 if dim else 1.0)
            item.setBrush(QBrush(fill))
            item.setPen(QPen(QColor(tokens.accent), 1.5))
            self._labels[key].setBrush(QBrush(QColor(tokens.muted if dim else tokens.text)))
        for text in self._years:
            text.setBrush(QBrush(QColor(tokens.muted)))

    def fit(self) -> None:
        """Scale the drawing into the view, as far as it stays readable."""
        rect: QRectF = self.scene().sceneRect()
        if rect.isEmpty():
            return
        self.resetTransform()
        scale = min(
            1.0,
            self.viewport().width() / rect.width(),
            self.viewport().height() / rect.height(),
        )
        scale = max(scale, _SMALLEST_SCALE)
        self.scale(scale, scale)
        self.centerOn(rect.center())

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
            return
        super().wheelEvent(event)

    # --- accessors used by tests -----------------------------------------------

    def node_keys(self) -> set[str]:
        return set(self._nodes)

    def edge_count(self) -> int:
        return len(self._edges)

    def selected(self) -> str:
        return self._selected

    def node_item(self, key: str) -> QGraphicsEllipseItem:
        return self._nodes[key]


def _shorten(title: str) -> str:
    return title if len(title) <= _LABEL_CHARS else title[: _LABEL_CHARS - 1].rstrip() + "…"

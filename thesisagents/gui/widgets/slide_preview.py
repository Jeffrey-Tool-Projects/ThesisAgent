"""A drawing of a slide, close enough to see what is where.

PowerPoint is not asked: the app must work without it. Backgrounds, filled
shapes, pictures, tables and text with its size, colour and alignment are
drawn from the file. Fonts and line breaks differ a little from PowerPoint,
and charts, SmartArt and effects are not drawn.

Example::

    image = render_slide(presentation.slides[0], size, 480)
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPen, QTextOption

_EMU_PER_POINT: Final[int] = 12700
_DEFAULT_POINTS: Final[float] = 18.0
_INSET_POINTS: Final[float] = 4.0
_LINE_SPACING: Final[float] = 1.2


def render_slide(slide: Any, slide_size: tuple[int, int], width: int) -> QImage:
    """Draw ``slide`` ``width`` pixels wide. ``slide_size`` is in EMU.

    Never raises for odd content: a shape that cannot be drawn is left out,
    since a preview must not stop the edit.
    """
    total_width, total_height = slide_size
    scale = width / total_width
    image = QImage(width, max(1, round(total_height * scale)), QImage.Format.Format_RGB32)
    image.fill(_background(slide))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    try:
        for shape in _shapes(slide.shapes):
            try:
                _draw_shape(painter, shape, scale)
            except Exception:  # noqa: BLE001, S112 - one odd shape must not hide the rest
                continue  # nosec B112 - see above
    finally:
        painter.end()
    return image


def _shapes(shapes: Any) -> Iterator[Any]:
    """Every shape, those inside groups included (at the group's own position)."""
    for shape in shapes:
        if hasattr(shape, "shapes"):
            yield from _shapes(shape.shapes)
        else:
            yield shape


def _background(slide: Any) -> QColor:
    for owner in (slide, slide.slide_layout, slide.slide_layout.slide_master):
        try:
            return QColor(f"#{owner.background.fill.fore_color.rgb}")
        except (AttributeError, TypeError):
            continue
    return QColor("#FFFFFF")


def _draw_shape(painter: QPainter, shape: Any, scale: float) -> None:
    if shape.left is None or shape.width is None:
        return
    rect = QRectF(
        shape.left * scale, shape.top * scale, shape.width * scale, shape.height * scale
    )
    picture = _picture(shape)
    if picture is not None:
        painter.drawImage(rect, picture)
        return
    if getattr(shape, "has_table", False):
        _draw_table(painter, shape.table, rect, scale)
        return
    fill = _solid(getattr(shape, "fill", None))
    if fill is not None:
        painter.fillRect(rect, fill)
    if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
        _draw_text(painter, shape.text_frame, rect, scale)


def _picture(shape: Any) -> QImage | None:
    image = getattr(shape, "image", None) if hasattr(shape, "image") else None
    if image is None:
        return None
    loaded = QImage.fromData(image.blob)
    return None if loaded.isNull() else loaded


def _solid(fill: Any) -> QBrush | None:
    try:
        return QBrush(QColor(f"#{fill.fore_color.rgb}"))
    except (AttributeError, TypeError):
        return None


def _draw_table(painter: QPainter, table: Any, rect: QRectF, scale: float) -> None:
    top = rect.top()
    for row in table.rows:
        left = rect.left()
        height = row.height * scale
        for column, cell in zip(table.columns, row.cells, strict=False):
            box = QRectF(left, top, column.width * scale, height)
            fill = _solid(cell.fill)
            if fill is not None:
                painter.fillRect(box, fill)
            painter.setPen(QPen(QColor("#CBD5E1"), 0.5))
            painter.drawRect(box)
            if cell.text_frame.text.strip():
                _draw_text(painter, cell.text_frame, box, scale)
            left += column.width * scale
        top += height


_ALIGNMENTS = {2: Qt.AlignmentFlag.AlignHCenter, 3: Qt.AlignmentFlag.AlignRight}


def _draw_text(painter: QPainter, frame: Any, rect: QRectF, scale: float) -> None:
    """Paragraph after paragraph, each in the look of its first run."""
    pixels_per_point = scale * _EMU_PER_POINT
    inset = _INSET_POINTS * pixels_per_point
    area = rect.adjusted(inset, inset, -inset, -inset)
    blocks = []
    for paragraph in frame.paragraphs:
        run = paragraph.runs[0] if paragraph.runs else None
        points = run.font.size.pt if run is not None and run.font.size else _DEFAULT_POINTS
        font = QFont(run.font.name) if run is not None and run.font.name else QFont()
        font.setPixelSize(max(1, round(points * pixels_per_point)))
        font.setBold(bool(run is not None and run.font.bold))
        font.setItalic(bool(run is not None and run.font.italic))
        option = QTextOption(_ALIGNMENTS.get(paragraph.alignment, Qt.AlignmentFlag.AlignLeft))
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        painter.setFont(font)
        bounds = painter.boundingRect(
            QRectF(0, 0, max(1.0, area.width()), 1e6), paragraph.text or " ", option
        )
        height = max(bounds.height(), font.pixelSize() * _LINE_SPACING)
        blocks.append((paragraph.text, font, option, _colour(run), height))
    total = sum(block[-1] for block in blocks)
    top = area.top()
    if frame.vertical_anchor == 3:  # middle
        top += max(0.0, (area.height() - total) / 2)
    elif frame.vertical_anchor == 4:  # bottom
        top += max(0.0, area.height() - total)
    for text, font, option, colour, height in blocks:
        painter.setFont(font)
        painter.setPen(colour)
        painter.drawText(QRectF(area.left(), top, max(1.0, area.width()), height), text, option)
        top += height


def _colour(run: Any) -> QColor:
    try:
        return QColor(f"#{run.font.color.rgb}")
    except (AttributeError, TypeError):
        return QColor("#000000")

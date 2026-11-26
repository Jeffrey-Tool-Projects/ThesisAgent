"""The size of the interface text, and what follows from it.

The boundary this module guards: everything that depends on how big the text
is asks here instead of holding its own pixel constant. The layouts were
drawn for 10 pt text, so at 20 pt a fixed 30 px table row cuts the letters, a
208 px sidebar cuts its labels, and a window that counted as wide has no room
left for two columns. :func:`font_scale` is the factor those places use.

The default is the size the app starts with: the system's, at least
:data:`SMALLEST_DEFAULT_PT`. It is not a constant, because macOS starts at
13 pt, and a scale measured from 10 there would spread every layout.

Example::

    remember_default_size(app)      # once, at boot
    set_font_size(app, 15)
    font_scale()                    # 1.5 on Windows, where the default is 10
"""

from __future__ import annotations

from typing import Final

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

#: The range offered to the user. Below 8 pt CJK strokes merge, and above
#: 24 pt the smallest window shows a few words per line.
MIN_FONT_PT: Final[int] = 8
MAX_FONT_PT: Final[int] = 24
#: A system font smaller than this (9 pt on Windows) is raised to it.
SMALLEST_DEFAULT_PT: Final[int] = 10

_POINTS_PER_INCH: Final[int] = 72
_DEFAULT_PROPERTY: Final[str] = "thesisagents_default_font_pt"
#: Height Qt gives a table row at the default size, and the room the text of
#: a row needs around it.
_ROW_HEIGHT: Final[int] = 30
_ROW_PADDING: Final[int] = 10


def _points(font: QFont) -> int:
    """``font``'s size in points, also for one that was set in pixels."""
    size = font.pointSize()
    if size > 0:
        return size
    dots_per_inch = QApplication.primaryScreen().logicalDotsPerInch()
    return round(font.pixelSize() * _POINTS_PER_INCH / dots_per_inch)


def clamp_font_size(points: int) -> int:
    """``points`` moved into the range the interface supports."""
    return max(MIN_FONT_PT, min(MAX_FONT_PT, points))


def remember_default_size(app: QApplication) -> int:
    """Take the font ``app`` has now as the default size and return that size.

    Called once at boot, after the size has been raised to
    :data:`SMALLEST_DEFAULT_PT` and before the saved size is applied.
    """
    points = _points(app.font())
    app.setProperty(_DEFAULT_PROPERTY, points)
    return points


def current_font_size() -> int:
    """The interface font size in points."""
    return _points(QApplication.font())


def default_font_size() -> int:
    """The size the app starts with when the user has not picked one.

    Before :func:`remember_default_size` ran (a test that builds one page),
    whatever size is in use counts as the default.
    """
    app = QApplication.instance()
    remembered = app.property(_DEFAULT_PROPERTY) if app is not None else None
    return int(remembered) if remembered else current_font_size()


def set_font_size(app: QApplication, points: int) -> None:
    """Give ``app`` a font of ``points``, keeping its families.

    Follow with ``theme.apply_theme``, which sizes the page titles and makes
    every existing widget take the font.
    """
    font = QFont(app.font())
    font.setPointSize(clamp_font_size(points))
    app.setFont(font)


def font_scale() -> float:
    """Current size divided by the default one (1.0 until the user changes it)."""
    return current_font_size() / max(1, default_font_size())


def layout_scale() -> float:
    """:func:`font_scale`, but never below 1.

    Layout minimums (the sidebar, the side column, the window widths where
    the arrangement changes) grow with the text. They do not shrink with it,
    because buttons and check boxes keep their size.
    """
    return max(1.0, font_scale())


def table_row_height() -> int:
    """Height of a table row that fits one line of the current font."""
    return max(_ROW_HEIGHT, QFontMetrics(QApplication.font()).height() + _ROW_PADDING)

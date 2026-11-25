"""Tests for the adaptive layout: breakpoints, sidebar, split panes, grids."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui.i18n import SUPPORTED_LANGUAGES
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.widgets.nav_rail import COMPACT_WIDTH, EXPANDED_WIDTH
from thesisagents.gui.widgets.responsive import (
    COMPACT_MAX_WIDTH,
    EXPANDED_MIN_WIDTH,
    Breakpoint,
    ReflowGrid,
    adapt_form_rows,
    breakpoint_for_width,
)


def _window(qtbot, width: int = 1280, height: int = 800, language: str = "en") -> MainWindow:
    window = MainWindow(ui_language=language)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    return window


# --- breakpoints --------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (0, Breakpoint.COMPACT),
        (COMPACT_MAX_WIDTH - 1, Breakpoint.COMPACT),
        (COMPACT_MAX_WIDTH, Breakpoint.MEDIUM),
        (EXPANDED_MIN_WIDTH - 1, Breakpoint.MEDIUM),
        (EXPANDED_MIN_WIDTH, Breakpoint.EXPANDED),
        (3840, Breakpoint.EXPANDED),
    ],
)
def test_breakpoint_boundaries(width, expected):
    assert breakpoint_for_width(width) is expected


# --- window size --------------------------------------------------------


def test_minimum_size_fits_a_small_laptop_and_stays_usable(qtbot):
    """The compact layout lets the window go below the old 900 x 600 floor,
    but not so small that a form row and a few table rows no longer fit."""
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    min_size = window.minimumSize()
    assert 600 <= min_size.width() <= 720
    assert 450 <= min_size.height() <= 540


def test_main_window_default_size_is_reasonable(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    assert window.width() <= 1600
    assert window.height() <= 1000


def test_window_can_be_resized_down_to_its_minimum(qtbot):
    window = _window(qtbot)
    window.resize(640, 480)
    qtbot.wait(20)
    assert (window.width(), window.height()) == (640, 480)


# --- the window re-arranges itself --------------------------------------


def test_expanded_window_puts_controls_beside_results(qtbot):
    window = _window(qtbot, 1400, 860)
    assert window.current_breakpoint() is Breakpoint.EXPANDED
    for page in (window.search_page(), window.enrich_page(), window.deck_page()):
        assert page.split().orientation() == Qt.Orientation.Horizontal
    assert not window.nav_rail().is_compact()


def test_medium_window_stacks_controls_above_results(qtbot):
    window = _window(qtbot, 1000, 760)
    assert window.current_breakpoint() is Breakpoint.MEDIUM
    for page in (window.search_page(), window.enrich_page(), window.deck_page()):
        assert page.split().orientation() == Qt.Orientation.Vertical
    assert not window.nav_rail().is_compact()


def test_compact_window_collapses_the_sidebar(qtbot):
    window = _window(qtbot, 680, 600)
    assert window.current_breakpoint() is Breakpoint.COMPACT
    rail = window.nav_rail()
    assert rail.is_compact()
    assert rail.width() == COMPACT_WIDTH
    # Labels move to the tooltip, so an icon-only entry is still named.
    assert rail.button_text(0) == ""
    assert rail.button_tooltip(0) == "Search"


def test_growing_the_window_restores_the_full_sidebar(qtbot):
    window = _window(qtbot, 680, 600)
    window.resize(1300, 800)
    qtbot.wait(20)
    assert window.current_breakpoint() is Breakpoint.EXPANDED
    assert not window.nav_rail().is_compact()
    assert window.nav_rail().width() == EXPANDED_WIDTH


def test_compact_window_hides_the_authors_and_doi_columns(qtbot):
    window = _window(qtbot, 680, 600)
    table = window.search_page().table()
    assert table.isColumnHidden(1)
    assert table.isColumnHidden(4)
    window.resize(1300, 800)
    qtbot.wait(20)
    assert not table.isColumnHidden(1)
    assert not table.isColumnHidden(4)


def test_settings_columns_stack_only_on_a_compact_window(qtbot):
    window = _window(qtbot, 1000, 760)
    settings = window.settings_page()
    assert settings.columns_direction() == QBoxLayout.Direction.LeftToRight
    window.resize(680, 600)
    qtbot.wait(20)
    assert settings.columns_direction() == QBoxLayout.Direction.TopToBottom


def test_controls_scroll_on_their_own_with_no_sideways_scrollbar(qtbot):
    """A short window scrolls the controls, never the whole page sideways."""
    window = _window(qtbot, 1000, 600)
    scroll = window.search_page().split().controls_scroll()
    assert scroll.widgetResizable() is True
    assert scroll.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_main_window_constructs_in_every_supported_language(qtbot, language):
    """A missing key in one language would crash a label at construction."""
    window = MainWindow(ui_language=language)
    qtbot.addWidget(window)
    assert window.page_count() == 5


# --- building blocks ----------------------------------------------------


def _grid(count: int = 15) -> ReflowGrid:
    return ReflowGrid([QCheckBox(f"source_{i:02d}") for i in range(count)])


def test_reflow_grid_fits_more_columns_on_a_wider_grid(qtbot):
    grid = _grid()
    qtbot.addWidget(grid)
    narrow = grid.columns_for_width(grid.minimumSizeHint().width())
    wide = grid.columns_for_width(grid.minimumSizeHint().width() * 4)
    assert narrow == 1
    assert wide == 4


def test_reflow_grid_needs_more_height_when_narrow(qtbot):
    """Height-for-width is what makes a parent layout give the grid its rows."""
    grid = _grid()
    qtbot.addWidget(grid)
    cell = grid.minimumSizeHint().width()
    assert grid.hasHeightForWidth()
    assert grid.heightForWidth(cell) > grid.heightForWidth(cell * 5)


def test_reflow_grid_relayouts_when_resized(qtbot):
    grid = _grid(6)
    qtbot.addWidget(grid)
    cell = grid.minimumSizeHint().width()
    grid.resize(cell * 3, 200)
    grid.show()
    qtbot.waitExposed(grid)
    assert grid.columns() == 3
    grid.resize(cell, 400)
    qtbot.wait(20)
    assert grid.columns() == 1


def test_reflow_grid_never_exceeds_its_item_count(qtbot):
    grid = _grid(2)
    qtbot.addWidget(grid)
    assert grid.columns_for_width(5000) == 2


def test_form_rows_wrap_below_the_threshold(qtbot):
    container = QWidget()
    form = QFormLayout(container)
    qtbot.addWidget(container)
    adapt_form_rows(container, form, threshold=400)
    container.resize(300, 100)
    container.show()
    qtbot.waitExposed(container)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapAllRows
    container.resize(600, 100)
    qtbot.wait(20)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.DontWrapRows


def _form_in_a_scroll_area(qtbot):
    """A form 1400 px wide with its labels beside the fields, 900 px with them above."""
    scroll = QScrollArea()
    qtbot.addWidget(scroll)
    scroll.setWidgetResizable(True)
    content = QWidget()
    layout = QVBoxLayout(content)
    note = QLabel("a note that wraps its words " * 6)
    note.setWordWrap(True)
    layout.addWidget(note)
    card = QFrame()
    form = QFormLayout(card)
    label, field = QLabel("label"), QLineEdit()
    label.setMinimumWidth(500)
    field.setMinimumWidth(900)
    form.addRow(label, field)
    adapt_form_rows(card, form, threshold=1000)
    layout.addWidget(card)
    scroll.setWidget(content)
    scroll.resize(400, 300)
    scroll.show()
    qtbot.waitExposed(scroll)
    return scroll, card, form


def test_a_form_wraps_again_when_the_pane_around_it_narrows(qtbot):
    # The card keeps its width then, so only the scroll area tells.
    scroll, _card, form = _form_in_a_scroll_area(qtbot)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapAllRows
    scroll.resize(1300, 300)
    qtbot.wait(50)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.DontWrapRows
    scroll.resize(400, 300)
    qtbot.wait(50)
    assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapAllRows


def test_a_form_stretched_by_its_own_minimum_does_not_change_its_mind(qtbot):
    # Judging by the stretched width made the page change back and forth until
    # the stack overflowed (progress #59): wide, so labels beside the fields,
    # so a larger minimum, so wide.
    _scroll, card, form = _form_in_a_scroll_area(qtbot)
    for width in (1424, 918, 1424, 999, 5000):
        card.resize(width, card.height())
        assert form.rowWrapPolicy() == QFormLayout.RowWrapPolicy.WrapAllRows

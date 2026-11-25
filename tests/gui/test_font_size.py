"""The interface font size: picking it, keeping it, and what has to follow it."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QFont, QShortcut, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QCheckBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableView,
    QWidget,
)

from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui import app as gui_app
from thesisagents.gui import font_size, theme
from thesisagents.gui import main_window as window_module
from thesisagents.gui.i18n import SUPPORTED_LANGUAGES, t
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.settings import SettingsPage, saved_font_size, settings_store
from thesisagents.gui.widgets.nav_rail import EXPANDED_WIDTH, NavRail
from thesisagents.gui.widgets.report_dialog import ReportDialog
from thesisagents.gui.widgets.responsive import (
    EXPANDED_MIN_WIDTH,
    AdaptiveSplit,
    Breakpoint,
    ReflowGrid,
    breakpoint_for_width,
)

_DEFAULT = 10
_KEY = "ui/font_size"


@pytest.fixture(autouse=True)
def _default_font(qtbot):
    """A 10 pt default like Windows', and the app back as it was afterwards."""
    app = QApplication.instance()
    saved = QFont(app.font())
    font = QFont(saved)
    font.setPointSize(_DEFAULT)
    app.setFont(font)
    font_size.remember_default_size(app)
    yield
    app.setProperty("thesisagents_default_font_pt", None)
    app.setFont(saved)
    theme.apply_theme(app, "light")


def _apply(points: int) -> None:
    app = QApplication.instance()
    font_size.set_font_size(app, points)
    theme.apply_theme(app, "light")


def _window(qtbot, width: int = 1280, height: int = 800, language: str = "en") -> MainWindow:
    window = MainWindow(ui_language=language)
    qtbot.addWidget(window)
    window.resize(width, height)
    window.show()
    qtbot.waitExposed(window)
    return window


def _pick(qtbot, window: MainWindow, points: int) -> None:
    """Pick ``points`` in Settings and wait until the window has taken it."""
    window.settings_page().set_font_size(points)
    qtbot.waitUntil(lambda: font_size.current_font_size() == points, timeout=3000)
    qtbot.wait(50)


def _collection(count: int = 4) -> PaperCollection:
    papers = tuple(
        Paper(
            source="arxiv", source_id=str(i), title=f"Paper {i}", authors=("A",),
            year=2024, venue=None, abstract="", url=f"https://example.org/{i}",
        )
        for i in range(count)
    )
    return PaperCollection(query=Query(keywords="x", sources=("arxiv",)), papers=papers)


# --- the setting ----------------------------------------------------------


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        (None, _DEFAULT),
        ("large", _DEFAULT),
        ("", _DEFAULT),
        (14, 14),
        ("14", 14),
        (3, font_size.MIN_FONT_PT),
        (900, font_size.MAX_FONT_PT),
    ],
)
def test_saved_size_survives_bad_values(stored, expected):
    if stored is not None:
        settings_store().setValue(_KEY, stored)
    assert saved_font_size() == expected


def test_default_before_boot_is_the_size_in_use():
    QApplication.instance().setProperty("thesisagents_default_font_pt", None)
    assert font_size.default_font_size() == _DEFAULT
    assert font_size.font_scale() == pytest.approx(1.0)


def test_a_font_set_in_pixels_still_has_a_point_size():
    app = QApplication.instance()
    font = QFont(app.font())
    font.setPixelSize(20)
    app.setFont(font)
    assert font.pointSize() == -1
    dots_per_inch = app.primaryScreen().logicalDotsPerInch()
    assert font_size.current_font_size() == round(20 * 72 / dots_per_inch)


def test_settings_box_stores_and_announces_each_step(qtbot):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    box = page.font_size_box()
    assert (box.value(), box.minimum(), box.maximum()) == (_DEFAULT, 8, 24)
    heard: list[int] = []
    page.font_size_changed.connect(heard.append)

    box.stepUp()
    box.setValue(18)

    assert heard == [11, 18]
    assert saved_font_size() == 18
    again = SettingsPage(ui_language="en")
    qtbot.addWidget(again)
    assert again.font_size_box().value() == 18


def test_size_is_kept_inside_the_range(qtbot):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_font_size(99)
    assert (page.font_size_box().value(), saved_font_size()) == (24, 24)
    page.set_font_size(1)
    assert (page.font_size_box().value(), saved_font_size()) == (8, 8)


def test_reset_forgets_the_size_instead_of_storing_the_default(qtbot):
    # Storing 10 would pin a user to it on a system whose default changes.
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.set_font_size(20)
    heard: list[int] = []
    page.font_size_changed.connect(heard.append)
    page.reset_font_size()
    assert heard == [_DEFAULT]
    assert page.font_size_box().value() == _DEFAULT
    assert not settings_store().contains(_KEY)


def test_typing_applies_the_whole_number_only(qtbot):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert page.font_size_box().keyboardTracking() is False


@pytest.mark.parametrize("focused", [False, True])
def test_wheel_changes_the_size_only_with_focus(qtbot, monkeypatch, focused):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    box = page.font_size_box()
    monkeypatch.setattr(box, "hasFocus", lambda: focused)
    event = QWheelEvent(
        QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    box.wheelEvent(event)
    assert box.value() == (_DEFAULT + 1 if focused else _DEFAULT)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_font_size_controls_are_labelled(qtbot, language):
    page = SettingsPage(ui_language=language)
    qtbot.addWidget(page)
    assert page.font_size_box().accessibleName() == t("settings.font_size_label", language)
    hint = t("settings.font_size_hint", language)
    for keys in ("++", "+-", "+0"):
        assert keys in hint


# --- the window follows ---------------------------------------------------


def test_a_new_size_reaches_every_widget_of_an_open_window(qtbot):
    window = _window(qtbot)
    window.search_page().show_results(_collection(), set())
    for points in (18, 8, 13):
        _pick(qtbot, window, points)
        wrong = {
            (type(w).__name__, w.objectName())
            for w in window.findChildren(QWidget)
            if w.objectName() != "PageTitle" and w.font().pointSize() != points
        }
        assert not wrong


def test_page_titles_scale_with_the_text(qtbot):
    window = _window(qtbot)
    title = next(
        label for label in window.findChildren(QLabel) if label.objectName() == "PageTitle"
    )
    title.ensurePolished()
    assert title.font().pointSize() == theme.CLASSIC_SHAPE.title_size_pt
    _pick(qtbot, window, 20)
    assert title.font().pointSize() == theme.CLASSIC_SHAPE.title_size_pt * 2


def test_a_theme_switch_keeps_the_size_of_open_widgets(qtbot):
    # A second setStyle put the tables, headers and the status bar of an
    # open window back to the platform's 9 pt class fonts (Windows only).
    window = _window(qtbot)
    _pick(qtbot, window, 15)
    for choice, style in (("dark", "material"), ("light", "classic")):
        theme.apply_theme(QApplication.instance(), choice, style)
        qtbot.wait(20)
        for kind in (QTableView, QHeaderView, QPushButton, QCheckBox):
            assert {w.font().pointSize() for w in window.findChildren(kind)} == {15}
        assert window.statusBar().font().pointSize() == 15


def test_the_qt_style_is_set_once(monkeypatch):
    app = QApplication.instance()
    theme.apply_theme(app, "light")
    calls: list[object] = []
    monkeypatch.setattr(QApplication, "setStyle", lambda *args: calls.append(args))
    theme.apply_theme(app, "dark")
    assert calls == []


def test_a_burst_of_steps_restyles_the_window_once(qtbot, monkeypatch):
    window = _window(qtbot)
    applied: list[int] = []
    real = window_module.apply_theme

    def spy(app, *args):
        applied.append(font_size.current_font_size())
        return real(app, *args)

    monkeypatch.setattr(window_module, "apply_theme", spy)
    for _ in range(5):
        window.settings_page().font_size_box().stepUp()
    assert applied == []
    qtbot.waitUntil(lambda: bool(applied), timeout=3000)
    qtbot.wait(250)
    assert applied == [_DEFAULT + 5]


def test_the_status_bar_says_the_new_size_at_once(qtbot):
    window = _window(qtbot, language="zh-tw")
    window.settings_page().set_font_size(12)
    assert window.statusBar().currentMessage() == "字體大小 12 pt"


def test_zoom_shortcuts(qtbot):
    window = _window(qtbot)
    page = window.settings_page()
    keys = {s.key().toString(): s for s in window.findChildren(QShortcut)}
    keys["Ctrl++"].activated.emit()
    keys["Ctrl+="].activated.emit()
    assert page.font_size_box().value() == _DEFAULT + 2
    keys["Ctrl+-"].activated.emit()
    assert page.font_size_box().value() == _DEFAULT + 1
    keys["Ctrl+0"].activated.emit()
    assert page.font_size_box().value() == _DEFAULT
    assert not settings_store().contains(_KEY)


def test_table_rows_fit_the_text(qtbot):
    window = _window(qtbot)
    window.search_page().show_results(_collection(), set())
    table = window.search_page().table()
    default = table.rowHeight(0)
    _pick(qtbot, window, 24)
    assert table.rowHeight(0) > table.fontMetrics().height()
    assert table.rowHeight(0) > default
    _pick(qtbot, window, _DEFAULT)
    assert table.rowHeight(0) == default


def test_nothing_in_the_results_pane_overlaps_at_the_largest_size(qtbot):
    # A fixed minimum height replaced the one Qt works out from the content,
    # so the filter row, the buttons and the table were drawn over each other.
    window = _window(qtbot)
    window.search_page().show_results(_collection(), set())
    _pick(qtbot, window, font_size.MAX_FONT_PT)
    squashed = [
        button.text()
        for button in window.search_page().findChildren(QPushButton)
        if button.isVisible() and button.height() < button.sizeHint().height() - 1
    ]
    assert squashed == []
    table = window.search_page().table()
    shown = [
        widget
        for widget in table.parentWidget().findChildren(QWidget)
        if widget.isVisible() and isinstance(widget, (QPushButton, QLabel, QLineEdit, QTableView))
    ]
    boxes = [QRect(w.mapTo(window, QPoint(0, 0)), w.size()) for w in shown]
    overlaps = [
        (type(shown[i]).__name__, type(shown[j]).__name__)
        for i in range(len(boxes))
        for j in range(i)
        if boxes[i].intersects(boxes[j])
        and not shown[i].isAncestorOf(shown[j])
        and not shown[j].isAncestorOf(shown[i])
    ]
    assert len(shown) >= 5
    assert overlaps == []


@pytest.mark.parametrize("points", [8, _DEFAULT])
def test_pages_do_not_scroll_at_the_default_size(qtbot, points):
    window = _window(qtbot, 640, 480)
    _pick(qtbot, window, points) if points != _DEFAULT else None
    for index, page in enumerate(
        (window.search_page(), window.library_page(), window.enrich_page(), window.deck_page())
    ):
        window.nav_rail().set_current(index)
        qtbot.wait(20)
        viewport = page.parentWidget()
        assert isinstance(viewport.parentWidget(), QScrollArea)
        # With room to spare: fonts differ by a pixel or two between machines.
        assert page.minimumSizeHint().height() <= viewport.height() - 6


def test_a_language_switch_right_after_a_step_keeps_the_size(qtbot):
    window = _window(qtbot)
    window.settings_page().set_font_size(16)
    replacement = window.rebuild_in_language("de")
    qtbot.addWidget(replacement)
    assert font_size.current_font_size() == 16
    assert replacement.settings_page().font_size_box().value() == 16


def test_a_window_opened_at_a_large_size_is_laid_out_for_it(qtbot):
    _apply(20)
    window = _window(qtbot, 1280, 800)
    assert window.current_breakpoint() is Breakpoint.COMPACT
    rows = {t.verticalHeader().defaultSectionSize() for t in window.findChildren(QTableView)}
    assert rows == {font_size.table_row_height()}


def test_a_size_change_keeps_a_folded_sidebar_folded(qtbot):
    window = _window(qtbot, 1280, 800)
    window.nav_rail().set_compact(True)
    _pick(qtbot, window, 9)
    assert window.nav_rail().is_compact()


# --- layout parts -----------------------------------------------------------


def test_size_classes_grow_with_the_text():
    assert breakpoint_for_width(EXPANDED_MIN_WIDTH, 1.0) is Breakpoint.EXPANDED
    assert breakpoint_for_width(EXPANDED_MIN_WIDTH, 1.2) is Breakpoint.MEDIUM
    assert breakpoint_for_width(EXPANDED_MIN_WIDTH * 2, 2.0) is Breakpoint.EXPANDED


def test_layout_does_not_shrink_with_small_text():
    _apply(8)
    assert font_size.font_scale() == pytest.approx(0.8)
    assert font_size.layout_scale() == pytest.approx(1.0)


def test_sidebar_widens_for_large_labels(qtbot):
    rail = NavRail(brand="ThesisAgents", toggle_tip="Collapse")
    qtbot.addWidget(rail)
    rail.add_item("search", "Wissenschaftliche Suche")
    assert rail.width() == EXPANDED_WIDTH
    _apply(24)
    rail.refresh_width()
    assert rail.width() > EXPANDED_WIDTH
    _apply(_DEFAULT)
    rail.refresh_width()
    assert rail.width() == EXPANDED_WIDTH


def test_reflow_grid_moves_its_items_when_the_text_grows(qtbot):
    grid = ReflowGrid([QCheckBox(f"semantic_scholar_{i}") for i in range(6)])
    qtbot.addWidget(grid)
    grid.resize(760, 200)
    grid.show()
    qtbot.waitExposed(grid)
    before = grid.columns()
    _apply(24)
    qtbot.waitUntil(lambda: grid.columns() < before, timeout=3000)
    for box in grid.findChildren(QCheckBox):
        assert box.height() >= box.sizeHint().height()


def test_split_lets_wide_controls_be_reached_when_enlarged(qtbot):
    split = AdaptiveSplit(QWidget(), QWidget())
    qtbot.addWidget(split)
    off, needed = Qt.ScrollBarPolicy.ScrollBarAlwaysOff, Qt.ScrollBarPolicy.ScrollBarAsNeeded
    split.apply_breakpoint(Breakpoint.MEDIUM)
    assert split.controls_scroll().horizontalScrollBarPolicy() == off
    _apply(20)
    split.apply_breakpoint(Breakpoint.MEDIUM)
    assert split.controls_scroll().horizontalScrollBarPolicy() == needed
    _apply(_DEFAULT)
    split.apply_breakpoint(Breakpoint.MEDIUM)
    assert split.controls_scroll().horizontalScrollBarPolicy() == off


def test_settings_columns_stack_on_a_medium_window_when_enlarged(qtbot):
    page = SettingsPage(ui_language="de")
    qtbot.addWidget(page)
    page.apply_breakpoint(Breakpoint.MEDIUM)
    assert page.columns_direction() == QBoxLayout.Direction.LeftToRight
    _apply(14)
    page.apply_breakpoint(Breakpoint.MEDIUM)
    assert page.columns_direction() == QBoxLayout.Direction.TopToBottom
    page.apply_breakpoint(Breakpoint.EXPANDED)
    assert page.columns_direction() == QBoxLayout.Direction.LeftToRight


def test_report_text_uses_the_interface_size(qtbot):
    _apply(17)
    dialog = ReportDialog("r", "text", copy_label="Copy", close_label="Close")
    qtbot.addWidget(dialog)
    assert dialog._text.font().pointSize() == 17  # noqa: SLF001


# --- boot -------------------------------------------------------------------


def test_boot_applies_the_saved_size_over_the_default(monkeypatch, qtbot):
    settings_store().setValue(_KEY, 19)
    app = QApplication.instance()
    small = QFont(app.font())
    small.setPointSize(9)
    app.setFont(small)

    class _StopError(Exception):
        pass

    def stop(*_args):
        raise _StopError

    # main() reuses this QApplication; stop at the step after the fonts.
    with monkeypatch.context() as patch:
        patch.setattr(theme, "apply_theme", stop)
        patch.setattr(gui_app, "_silence_font_probe_messages", lambda: None)
        with pytest.raises(_StopError):
            gui_app._boot([])  # noqa: SLF001
    assert font_size.default_font_size() == font_size.SMALLEST_DEFAULT_PT
    assert font_size.current_font_size() == 19
    assert "Nirmala UI" in app.font().families()

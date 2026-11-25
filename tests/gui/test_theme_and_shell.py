"""Tests for the theme, the sidebar and the window shell around the pages."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui import theme
from thesisagents.gui.icons import ICON_NAMES, nav_icon, write_glyph
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages import search as search_module
from thesisagents.gui.pages.settings import (
    SettingsPage,
    saved_style,
    saved_theme,
    settings_store,
)
from thesisagents.gui.widgets.nav_rail import NavRail


def _collection(count: int = 3, url: str = "https://example.org/{i}") -> PaperCollection:
    papers = tuple(
        Paper(
            source="arxiv", source_id=str(i), title=f"Paper {i}", authors=("A",),
            year=2024, venue=None, abstract="", url=url.format(i=i),
        )
        for i in range(count)
    )
    return PaperCollection(query=Query(keywords="x", sources=("arxiv",)), papers=papers)


# --- theme ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("choice", "system_dark", "expected"),
    [
        ("system", False, "light"),
        ("system", True, "dark"),
        ("light", True, "light"),
        ("dark", False, "dark"),
        ("hand-edited nonsense", True, "dark"),
    ],
)
def test_resolve_theme(choice, system_dark, expected):
    assert theme.resolve_theme(choice, system_dark).name == expected


def _colours(palette: theme.Palette) -> set[str]:
    values = vars(palette).values()
    return {value for value in values if isinstance(value, str) and value.startswith("#")}


@pytest.mark.parametrize("tokens", theme.ALL_PALETTES, ids=lambda p: p.name)
def test_stylesheet_uses_only_its_own_palette(tokens):
    """No colour of another style or variant leaks into a stylesheet."""
    own = _colours(tokens)
    others = set().union(*(_colours(p) for p in theme.ALL_PALETTES if p is not tokens)) - own
    sheet = theme.build_stylesheet(tokens)
    assert tokens.accent in sheet
    assert not {colour for colour in others if colour in sheet}


@pytest.mark.parametrize(
    ("style", "dark", "expected"),
    [
        ("classic", False, "light"),
        ("classic", True, "dark"),
        ("material", False, "material-light"),
        ("material", True, "material-dark"),
        ("not-a-style", False, "light"),
    ],
)
def test_resolve_style(style, dark, expected):
    choice = "dark" if dark else "light"
    assert theme.resolve_theme(choice, system_is_dark=False, style=style).name == expected


def test_palette_names_are_unique():
    """The name keys the glyph files and current_palette(), so a clash would
    paint one style's check marks in another's colours."""
    names = [palette.name for palette in theme.ALL_PALETTES]
    assert len(names) == len(set(names))


def test_material_shape_reaches_the_stylesheet():
    sheet = theme.build_stylesheet(theme.MATERIAL_LIGHT)
    assert f"border-radius: {theme.MATERIAL_SHAPE.button_radius}px" in sheet
    assert f"border-radius: {theme.MATERIAL_SHAPE.nav_radius}px" in sheet
    classic = theme.build_stylesheet(theme.LIGHT)
    assert f"border-radius: {theme.MATERIAL_SHAPE.button_radius}px" not in classic


@pytest.mark.parametrize("tokens", theme.ALL_PALETTES, ids=lambda p: p.name)
def test_text_contrasts_with_its_backgrounds(tokens):
    """Body text on the window / card fill and the sidebar labels stay
    readable: WCAG AA asks for 4.5:1 for normal text."""

    def luminance(hex_colour: str) -> float:
        channels = []
        for channel in QColor(hex_colour).getRgbF()[:3]:
            channels.append(
                channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
            )
        r, g, b = channels
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def contrast(a: str, b: str) -> float:
        high, low = sorted((luminance(a), luminance(b)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    assert contrast(tokens.text, tokens.window) >= 4.5
    assert contrast(tokens.text, tokens.surface) >= 4.5
    assert contrast(tokens.muted, tokens.surface) >= 4.5
    assert contrast(tokens.nav_text, tokens.nav) >= 4.5
    assert contrast(tokens.on_accent, tokens.accent) >= 4.5


def test_apply_theme_leaves_no_class_font_over_the_application_font(qtbot):
    # Qt rebuilds its per-class platform fonts during apply_theme, so lists
    # and menus lost the per-script fallback families and the 10 pt minimum,
    # and opening a language list printed eight "OpenType support missing"
    # lines for the Hindi entry.
    app = QApplication.instance()
    saved = QFont(app.font())
    families = ["Noto Sans", "Nirmala UI", "Arial"]
    font = QFont(saved)
    font.setFamilies(families)
    font.setPointSize(13)
    try:
        app.setFont(font)
        for choice, style in (("light", "classic"), ("dark", "material")):
            app.setFont(QFont("Courier New", 7), "QAbstractItemView")
            theme.apply_theme(app, choice, style)
            for name in ("QAbstractItemView", "QMenu", "QStatusBar", "QMessageBox", "QLabel"):
                applied = QApplication.font(name)
                assert (applied.families(), applied.pointSize()) == (families, 13), name
    finally:
        app.setFont(saved)
        theme.apply_theme(app, "light")


def test_apply_theme_sets_palette_style_and_glyphs(qtbot):
    app = QApplication.instance()
    tokens = theme.apply_theme(app, "dark")
    try:
        assert tokens is theme.DARK
        assert theme.current_palette() is theme.DARK
        assert app.palette().color(QPalette.ColorRole.Window) == QColor(theme.DARK.window)
        assets = theme.write_theme_assets(theme.DARK)
        assert all(Path(path).is_file() for path in assets.values())
        assert assets["check"] in app.styleSheet()
    finally:
        theme.apply_theme(app, "light")


def test_glyphs_and_icons_draw(tmp_path):
    for name in ICON_NAMES:
        assert not nav_icon(name, "#000000", "#FFFFFF").isNull()
    target = tmp_path / "check.png"
    write_glyph("check", "#FFFFFF", str(target))
    assert target.stat().st_size > 0
    with pytest.raises(KeyError):
        nav_icon("no-such-icon", "#000000", "#FFFFFF")


# --- settings: theme choice ------------------------------------------------


def test_theme_defaults_to_following_the_system(qtbot):
    assert saved_theme() == "system"
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert page.theme_combo().currentData() == "system"


def test_saving_stores_and_announces_the_theme(qtbot):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.theme_combo().setCurrentIndex(page.theme_combo().findData("dark"))
    with qtbot.waitSignal(page.theme_changed) as signal:
        page.trigger_save()
    assert signal.args == ["dark"]
    assert saved_theme() == "dark"


def test_style_defaults_to_classic_and_is_saved(qtbot):
    assert saved_style() == "classic"
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert page.style_combo().currentData() == "classic"
    page.style_combo().setCurrentIndex(page.style_combo().findData("material"))
    page.trigger_save()
    assert saved_style() == "material"
    settings_store().setValue("ui/style", "neon")
    assert saved_style() == "classic"


def test_window_repaints_in_the_saved_style(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    page = window.settings_page()
    page.theme_combo().setCurrentIndex(page.theme_combo().findData("dark"))
    page.style_combo().setCurrentIndex(page.style_combo().findData("material"))
    try:
        page.trigger_save()
        assert theme.current_palette() is theme.MATERIAL_DARK
    finally:
        theme.apply_theme(QApplication.instance(), "light")


def test_unknown_saved_theme_reads_as_system():
    settings_store().setValue("ui/theme", "neon")
    assert saved_theme() == "system"


def test_window_repaints_when_settings_change_the_theme(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    page = window.settings_page()
    page.theme_combo().setCurrentIndex(page.theme_combo().findData("dark"))
    try:
        page.trigger_save()
        assert theme.current_palette() is theme.DARK
    finally:
        theme.apply_theme(QApplication.instance(), "light")


# --- sidebar --------------------------------------------------------------


def test_nav_rail_switches_pages(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.nav_rail().set_current(2)
    assert window.page_stack().currentIndex() == 2
    assert window.nav_rail().current() == 2


def test_nav_rail_toggle_collapses_by_hand(qtbot):
    rail = NavRail(brand="ThesisAgents", toggle_tip="toggle")
    qtbot.addWidget(rail)
    rail.add_item("search", "Search")
    rail.set_compact(True)
    assert rail.is_compact()
    assert rail.button_text(0) == ""
    rail.set_compact(False)
    assert rail.button_text(0).strip() == "Search"


def test_search_results_put_a_paper_count_on_the_next_steps(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    window.search_page()._on_search_finished(_collection(3))  # noqa: SLF001
    rail = window.nav_rail()
    assert rail.button_tooltip(2) == "Enrich  ·  3"
    assert rail.button_tooltip(3) == "Deck  ·  3"
    assert rail.button_tooltip(0) == "Search"
    assert rail.button_tooltip(1) == "Library"


# --- busy indicator ---------------------------------------------------------


def test_busy_indicator_follows_the_pages(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    assert not window.is_busy()
    window.search_page().busy_changed.emit(True)
    window.deck_page().busy_changed.emit(True)
    window.search_page().busy_changed.emit(False)
    assert window.is_busy()  # the deck export is still running
    window.deck_page().busy_changed.emit(False)
    assert not window.is_busy()


def test_search_page_reports_busy_until_the_run_ends(qtbot):
    page = search_module.SearchPage(ui_language="en")
    qtbot.addWidget(page)
    seen: list[bool] = []
    page.busy_changed.connect(seen.append)
    page._set_busy()  # noqa: SLF001
    page._on_search_finished(_collection(1))  # noqa: SLF001
    page._set_busy()  # noqa: SLF001
    page._on_worker_failed(RuntimeError("boom"))  # noqa: SLF001
    assert seen == [True, False, True, False]


# --- results table ----------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "opened"),
    [
        ("https://example.org/{i}", True),
        ("http://example.org/{i}", True),
        ("file:///C:/Windows/System32/calc.exe#{i}", False),
        ("javascript:alert({i})", False),
    ],
)
def test_double_click_opens_only_web_links(qtbot, monkeypatch, url, opened):
    calls: list[QUrl] = []
    monkeypatch.setattr(search_module.QDesktopServices, "openUrl", calls.append)
    page = search_module.SearchPage(ui_language="en")
    qtbot.addWidget(page)
    page._on_search_finished(_collection(1, url=url))  # noqa: SLF001
    page._on_row_double_clicked(page.papers_model().index(0, 0))  # noqa: SLF001
    assert bool(calls) is opened


def test_enter_in_the_query_field_starts_the_search(qtbot, monkeypatch):
    page = search_module.SearchPage(ui_language="en")
    qtbot.addWidget(page)
    started: list[bool] = []
    monkeypatch.setattr(page, "_set_busy", lambda: started.append(True))
    monkeypatch.setattr(search_module.QThreadPool, "globalInstance", lambda: _NoPool())
    page.set_query_text("graph neural networks")
    page._query_input.returnPressed.emit()  # noqa: SLF001
    assert started == [True]


class _NoPool:
    """Stands in for the thread pool so no search actually runs."""

    def start(self, _worker) -> None:
        return None

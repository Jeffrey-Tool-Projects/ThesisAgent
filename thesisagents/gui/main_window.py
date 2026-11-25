"""Main application window: a sidebar, the five pages, and a status bar.

Layout, from left to right: the :class:`NavRail` sidebar, then a stack
holding one page at a time. Each page has a title and a one-line subtitle
saying what the step does, above its body. The status bar at the bottom
shows a progress bar while any page has work running on a worker thread.

The window adapts to its width (see ``widgets/responsive.py``):

* **Compact** (< 760 px): the sidebar collapses to icons, forms put their
  labels above the fields, controls sit above the results.
* **Medium** (760-1179 px): full sidebar, controls above the results.
* **Expanded** (>= 1180 px): controls in a side column beside the results.

The pages are told when the size class changes (``apply_breakpoint``), so
each one decides how to re-arrange itself. ``Ctrl+1`` ... ``Ctrl+5`` switch
pages from the keyboard (Search, Library, Enrich, Deck, Settings), and
``Ctrl++`` / ``Ctrl+-`` / ``Ctrl+0`` change the interface font size. The
widths above are for text of the default size and grow with it.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, QTimer
from PySide6.QtGui import QCloseEvent, QGuiApplication, QKeySequence, QResizeEvent, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.models import PaperCollection
from thesisagents.gui.activity import activity
from thesisagents.gui.font_size import (
    current_font_size,
    layout_scale,
    set_font_size,
    table_row_height,
)
from thesisagents.gui.i18n import t
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.pages.enrich import EnrichPage
from thesisagents.gui.pages.library import LibraryPage
from thesisagents.gui.pages.search import SearchPage
from thesisagents.gui.pages.settings import (
    SettingsPage,
    saved_font_size,
    saved_style,
    saved_theme,
    settings_store,
)
from thesisagents.gui.theme import THEME_SYSTEM, apply_theme
from thesisagents.gui.update_check import UpdateCheck, open_download_page
from thesisagents.gui.widgets.log_dialog import LogDialog
from thesisagents.gui.widgets.nav_rail import NavRail
from thesisagents.gui.widgets.notice_banner import NoticeBanner
from thesisagents.gui.widgets.responsive import Breakpoint, breakpoint_for_width
from thesisagents.utils.notices import CAPTCHA_WAITING, Notice

# The floor fits a 1366 x 768 laptop at 125 % scaling with room to spare:
# the compact layout (icon sidebar, stacked panes, wrapped form rows) is
# what makes a window this small usable.
_MIN_WIDTH = 640
_MIN_HEIGHT = 480
_DEFAULT_WIDTH = 1280
_DEFAULT_HEIGHT = 800
# Restyling the window takes about half a second, so a burst of font size
# steps (a held key, the spin box arrows) is applied once, after this pause.
_FONT_SIZE_DELAY_MS = 150
# QSettings key holding the window's size, position and maximised state.
_GEOMETRY_KEY = "window/geometry"
#: Windows built by a language switch. The window that replaces another has
#: no other Python reference (``app.py`` holds the first one only), so it is
#: kept here until Qt destroys it.
_REPLACEMENTS: list[MainWindow] = []

# Page order: (icon, nav label key, subtitle key). The index is the
# sidebar index, the stack index and the Ctrl+N shortcut. The Library sits
# beside Search: both are where papers come from.
_SEARCH, _LIBRARY, _ENRICH, _DECK, _SETTINGS = range(5)
_PAGE_META: tuple[tuple[str, str, str], ...] = (
    ("search", "nav.search", "page.search_subtitle"),
    ("library", "nav.library", "page.library_subtitle"),
    ("enrich", "nav.enrich", "page.enrich_subtitle"),
    ("deck", "nav.deck", "page.deck_subtitle"),
    ("settings", "nav.settings", "page.settings_subtitle"),
)


class MainWindow(QMainWindow):
    """Top-level window. Owns the sidebar, the page stack and every page.

    The window's size and position are saved to QSettings when it closes
    and restored when the next one is built.
    """

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._breakpoint: Breakpoint | None = None
        self._layout_scale = 1.0
        self._busy_pages: set[str] = set()
        self.setWindowTitle(t("app.title", ui_language))
        self.setMinimumSize(_MIN_WIDTH, _MIN_HEIGHT)
        self.resize(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)
        self._restore_geometry()

        self._search_page = SearchPage(ui_language=ui_language)
        self._library_page = LibraryPage(ui_language=ui_language)
        self._enrich_page = EnrichPage(ui_language=ui_language)
        self._deck_page = DeckPage(ui_language=ui_language)
        self._settings_page = SettingsPage(ui_language=ui_language)

        self._nav = NavRail(
            brand=t("app.title", ui_language),
            toggle_tip=t("nav.toggle", ui_language),
        )
        self._stack = QStackedWidget(self)
        self._headers: list[QWidget] = []
        bodies: tuple[QWidget, ...] = (
            self._scrollable(self._search_page),
            self._scrollable(self._library_page),
            self._scrollable(self._enrich_page),
            self._scrollable(self._deck_page),
            self._scrollable(self._settings_page),
        )
        for index, (icon, label_key, subtitle_key) in enumerate(_PAGE_META):
            self._nav.add_item(
                icon, t(label_key, ui_language), bottom=index == _SETTINGS
            )
            self._stack.addWidget(
                self._page_frame(
                    t(label_key, ui_language), t(subtitle_key, ui_language), bodies[index]
                )
            )
        self._nav.current_changed.connect(self._stack.setCurrentIndex)

        central = QWidget(self)
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(self._nav)
        content = QWidget(central)
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        self._banner = NoticeBanner(ui_language, content)
        column.addWidget(self._banner)
        column.addWidget(self._stack, stretch=1)
        row.addWidget(content, stretch=1)
        self.setCentralWidget(central)

        self._build_status_bar()
        self._wire_pages()
        for index in range(len(_PAGE_META)):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index + 1}"), self)
            shortcut.activated.connect(lambda i=index: self._nav.set_current(i))
        self._build_font_size_controls()
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_system_scheme)
        self._fit_font_size()
        self._restore_forms()

    # --- construction ---------------------------------------------------

    def _page_frame(self, title: str, subtitle: str, body: QWidget) -> QWidget:
        """A page with its title and subtitle above ``body``."""
        frame = QWidget(self)
        frame.setObjectName("PageBody")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(24, 18, 24, 12)
        layout.setSpacing(4)
        header = QWidget(frame)
        header.setObjectName("PageHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)
        heading = QLabel(title, header)
        heading.setObjectName("PageTitle")
        caption = QLabel(subtitle, header)
        caption.setObjectName("PageSubtitle")
        caption.setWordWrap(True)
        header_layout.addWidget(heading)
        header_layout.addWidget(caption)
        layout.addWidget(header)
        layout.addSpacing(10)
        layout.addWidget(body, stretch=1)
        self._headers.append(frame)
        return frame

    def _scrollable(self, page: QWidget) -> QScrollArea:
        """Wrap a page, so it scrolls when the window is too small for it.

        ``widgetResizable=True`` makes the page stretch with the scroll area
        instead of sitting at its size hint. At the default font size every
        page but Settings fits the smallest window, so nothing scrolls. With
        enlarged text the alternative is widgets squeezed onto each other.
        """
        scroll = QScrollArea(self)
        scroll.setWidget(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def _build_status_bar(self) -> None:
        bar = QStatusBar(self)
        bar.setSizeGripEnabled(True)
        self._busy_bar = QProgressBar(bar)
        self._busy_bar.setRange(0, 0)  # indeterminate
        self._busy_bar.setFixedWidth(160)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setVisible(False)
        bar.addPermanentWidget(self._busy_bar)
        self._update_button = QPushButton("", bar)
        self._update_button.setObjectName("StatusButton")
        self._update_button.setProperty("primary", True)
        self._update_button.clicked.connect(open_download_page)
        self._update_button.setVisible(False)
        bar.addPermanentWidget(self._update_button)
        self._update_check = UpdateCheck(self)
        self._update_check.found.connect(self.show_update)
        self._log_dialog: LogDialog | None = None
        log_button = QPushButton(t("log.button", self._ui_language), bar)
        log_button.setObjectName("StatusButton")
        log_button.setToolTip(t("log.title", self._ui_language) + " (Ctrl+L)")
        log_button.clicked.connect(self.show_log)
        bar.addPermanentWidget(log_button)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.show_log)
        activity().notice.connect(self._on_notice)
        activity().unexpected_error.connect(self._on_unexpected_error)
        self.setStatusBar(bar)

    def _build_font_size_controls(self) -> None:
        """The zoom shortcuts, and the timer that applies a burst of steps once."""
        self._font_timer = QTimer(self)
        self._font_timer.setSingleShot(True)
        self._font_timer.setInterval(_FONT_SIZE_DELAY_MS)
        self._font_timer.timeout.connect(self._apply_font_size)
        page = self._settings_page
        for keys, action in (
            # Ctrl+= is Ctrl++ without the Shift that layouts put the + under.
            (("Ctrl++", "Ctrl+="), lambda: page.set_font_size(page.font_size_box().value() + 1)),
            (("Ctrl+-",), lambda: page.set_font_size(page.font_size_box().value() - 1)),
            (("Ctrl+0",), page.reset_font_size),
        ):
            for key in keys:
                QShortcut(QKeySequence(key), self).activated.connect(action)

    def _wire_pages(self) -> None:
        # Data flow between steps: Search → Enrich (raw collection) and
        # Search → Deck (so the user can skip enrichment), plus Enrich →
        # Deck (the enriched collection takes precedence).
        self._search_page.collection_ready.connect(self._enrich_page.set_collection)
        self._search_page.collection_ready.connect(self._deck_page.set_collection)
        self._search_page.library_path_changed.connect(self._deck_page.set_library_path)
        self._search_page.set_output_dir_provider(self._deck_page.output_dir)
        self._enrich_page.collection_ready.connect(self._deck_page.set_collection)
        self._search_page.collection_ready.connect(self._on_search_collection)
        # The Library page follows the Search page's library file, and hands
        # its papers on to Enrich and Deck the same way a search does.
        self._search_page.library_path_changed.connect(self._library_page.set_library_path)
        self._library_page.set_query_provider(self._search_page.current_query)
        self._library_page.collection_ready.connect(self._enrich_page.set_collection)
        self._library_page.collection_ready.connect(self._deck_page.set_collection)
        self._library_page.collection_ready.connect(self._on_search_collection)
        self._enrich_page.collection_ready.connect(self._on_enriched_collection)
        for key, page in (
            ("search", self._search_page),
            ("library", self._library_page),
            ("enrich", self._enrich_page),
            ("deck", self._deck_page),
        ):
            page.busy_changed.connect(lambda busy, k=key: self._on_busy_changed(k, busy))
        self._settings_page.theme_changed.connect(self._on_theme_changed)
        self._settings_page.font_size_changed.connect(self._on_font_size_changed)
        self._settings_page.language_changed.connect(self._on_language_changed)
        self._settings_page.access_changed.connect(self._search_page.apply_access)
        # Emitted by every save, whatever was changed.
        self._settings_page.access_changed.connect(lambda _on: self._enrich_page.refresh_model())

    # --- responsive -----------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._apply_breakpoint(breakpoint_for_width(event.size().width(), layout_scale()))

    def _apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Re-arrange the sidebar and every page for ``breakpoint`` and the font size."""
        scale = layout_scale()
        if (breakpoint, scale) == (self._breakpoint, self._layout_scale):
            return
        if breakpoint != self._breakpoint:
            # Only then: a font size change alone keeps a rail the user folded.
            self._nav.set_compact(breakpoint is Breakpoint.COMPACT)
        self._breakpoint = breakpoint
        self._layout_scale = scale
        compact = breakpoint is Breakpoint.COMPACT
        margin, top, bottom = (12, 8, 6) if compact else (24, 14, 10)
        for frame in self._headers:
            frame.layout().setContentsMargins(margin, top, margin, bottom)
        for page in (
            self._search_page, self._library_page, self._enrich_page,
            self._deck_page, self._settings_page,
        ):
            page.apply_breakpoint(breakpoint)

    # --- slots ------------------------------------------------------------

    def _on_search_collection(self, collection: object) -> None:
        count = len(collection.papers) if isinstance(collection, PaperCollection) else 0
        badge = str(count) if count else ""
        self._nav.set_badge(_ENRICH, badge)
        self._nav.set_badge(_DECK, badge)

    def _on_enriched_collection(self, collection: object) -> None:
        if isinstance(collection, PaperCollection):
            count = len(collection.papers)
            self._nav.set_badge(_DECK, str(count) if count else "")

    def _on_busy_changed(self, key: str, busy: bool) -> None:
        if busy:
            self._busy_pages.add(key)
        else:
            self._busy_pages.discard(key)
        working = bool(self._busy_pages)
        self._busy_bar.setVisible(working)
        if working:
            self.statusBar().showMessage(t("status.busy", self._ui_language))
        else:
            self.statusBar().clearMessage()

    def _on_language_changed(self, language: str) -> None:
        """Switch the interface language now, unless work is running.

        Every label is read when its page is built, so the window is rebuilt
        in the new language and the current work is carried over (owner's
        decision for ``progress.md`` #25). Running work cannot be carried,
        so then the switch waits for the next start.
        """
        if self.is_busy():
            self.statusBar().showMessage(t("status.language_later", self._ui_language))
            return
        self.rebuild_in_language(language)

    def rebuild_in_language(self, language: str) -> MainWindow:
        """Replace this window with one in ``language``; return the new one.

        Carried over: the window geometry, every form field (through the
        same QSettings save the window does on close), the search result
        with its ticks, the open library, the Enrich and Deck collections and
        the current page.
        """
        # A size picked a moment ago may still be waiting for the timer.
        self._apply_font_size()
        store = settings_store()
        store.setValue(_GEOMETRY_KEY, self.saveGeometry())
        self.save_forms(store)
        replacement = MainWindow(ui_language=language)
        replacement.adopt_work(self)
        # Repeats today's answer in the new window, without asking again.
        replacement.check_for_updates()
        replacement.statusBar().showMessage(t("settings.saved_message", language), 8000)
        _REPLACEMENTS.append(replacement)
        replacement.destroyed.connect(
            lambda *_: _REPLACEMENTS.remove(replacement) if replacement in _REPLACEMENTS else None
        )
        replacement.show()
        self.close()
        return replacement

    def adopt_work(self, old: MainWindow) -> None:
        """Take over ``old``'s results, collections and current page."""
        search = old.search_page()
        result = search.collection()
        if result is not None:
            self._search_page.show_results(result, search.papers_model().unchecked_rows())
        snapshot = old.library_page().snapshot()
        if snapshot is not None:
            self._library_page.show_snapshot(snapshot)
        enriched = old.enrich_page().collection()
        if enriched is not None:
            self._enrich_page.set_collection(enriched)
        deck = old.deck_page().collection()
        if deck is not None:
            self._deck_page.set_collection(deck)
        self._nav.set_current(old.nav_rail().current())

    def _on_theme_changed(self, choice: str) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, choice, saved_style())
        self._nav.refresh_icons()
        self._library_page.graph().repaint_colours()

    def check_for_updates(self) -> None:
        """Look for a newer release (``app.py`` calls this once the window shows)."""
        self._update_check.start()

    def show_update(self, version: str) -> None:
        """Offer the download page of ``version`` in the status bar."""
        self._update_button.setText(
            t("updates.available", self._ui_language, version=version)
        )
        self._update_button.setToolTip(t("updates.open", self._ui_language))
        self._update_button.setVisible(True)

    def update_button(self) -> QPushButton:
        return self._update_button

    def show_log(self) -> LogDialog:
        """Open the log window, or bring the open one to the front."""
        if self._log_dialog is None:
            self._log_dialog = LogDialog(self._ui_language, self)
        self._log_dialog.show()
        self._log_dialog.raise_()
        return self._log_dialog

    def _on_notice(self, notice: object) -> None:
        if not isinstance(notice, Notice):
            return
        self._banner.show_notice(notice)
        if notice.kind == CAPTCHA_WAITING:
            # Flash the taskbar entry: the user is likely in another window.
            QApplication.alert(self)

    def _on_unexpected_error(self, error: str) -> None:
        self.statusBar().showMessage(
            t("error.unexpected", self._ui_language, error=error), 15000
        )

    def notice_banner(self) -> NoticeBanner:
        return self._banner

    def _on_font_size_changed(self, points: int) -> None:
        """Say the new size at once and apply it when the steps stop coming."""
        label = t("settings.font_size_label", self._ui_language)
        self.statusBar().showMessage(f"{label} {points} pt", 3000)
        self._font_timer.start()

    def _apply_font_size(self) -> None:
        points = saved_font_size()
        app = QApplication.instance()
        if not isinstance(app, QApplication) or points == current_font_size():
            return
        set_font_size(app, points)
        apply_theme(app, saved_theme(), saved_style())
        self._fit_font_size()

    def _fit_font_size(self) -> None:
        """Re-fit what does not follow the font by itself: rows, sidebar, layout."""
        for table in self.findChildren(QTableView):
            table.verticalHeader().setDefaultSectionSize(table_row_height())
        self._nav.refresh_width()
        self._apply_breakpoint(breakpoint_for_width(self.width(), layout_scale()))

    def _on_system_scheme(self, _scheme: object) -> None:
        """Follow the OS switching light / dark, when the theme is "system"."""
        if saved_theme() == THEME_SYSTEM:
            self._on_theme_changed(THEME_SYSTEM)

    # --- geometry ---------------------------------------------------------

    def _restore_geometry(self) -> None:
        """Apply the geometry saved by the last window, if any.

        ``restoreGeometry`` moves a window that would land off-screen (a
        monitor that is gone) back onto an available screen, and ignores
        data it cannot parse, so the defaults above stay in that case.
        """
        saved = settings_store().value(_GEOMETRY_KEY)
        if isinstance(saved, QByteArray) and not saved.isEmpty():
            self.restoreGeometry(saved)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        """Save the window geometry and the form values, then close as usual."""
        store = settings_store()
        store.setValue(_GEOMETRY_KEY, self.saveGeometry())
        self.save_forms(store)
        super().closeEvent(event)

    def save_forms(self, store: QSettings) -> None:
        """Write the Search, Library, Enrich and Deck fields for the next start."""
        for page in self._form_pages():
            page.save_form(store)
        store.sync()

    def _restore_forms(self) -> None:
        store = settings_store()
        for page in self._form_pages():
            page.restore_form(store)

    def _form_pages(self) -> tuple[SearchPage | LibraryPage | EnrichPage | DeckPage, ...]:
        # The Library page restores after Search, so its own saved path wins
        # over the one the Search page's restore just echoed to it.
        return (self._search_page, self._library_page, self._enrich_page, self._deck_page)

    # --- accessors used by tests ----------------------------------------

    def search_page(self) -> SearchPage:
        return self._search_page

    def settings_page(self) -> SettingsPage:
        return self._settings_page

    def enrich_page(self) -> EnrichPage:
        return self._enrich_page

    def deck_page(self) -> DeckPage:
        return self._deck_page

    def library_page(self) -> LibraryPage:
        return self._library_page

    def nav_rail(self) -> NavRail:
        return self._nav

    def page_stack(self) -> QStackedWidget:
        return self._stack

    def current_breakpoint(self) -> Breakpoint | None:
        return self._breakpoint

    def is_busy(self) -> bool:
        """Whether the status-bar progress indicator is showing."""
        return bool(self._busy_pages)

    def page_count(self) -> int:
        return self._stack.count()

    def tab_count(self) -> int:
        """Kept for callers of the tabbed window: the number of pages."""
        return self.page_count()


if __name__ == "__main__":
    # Run this module directly for a quick look at the window while
    # developing: ``python -m thesisagents.gui.main_window``. It goes through
    # ``app.main`` rather than building ``MainWindow`` here, because ``main``
    # also pins the HiDPI policy, loads the saved API keys into the
    # environment, applies the saved theme and picks the interface language.
    # A bare ``MainWindow()`` would skip all four and open unstyled, in English.
    from thesisagents.gui.app import main

    raise SystemExit(main())

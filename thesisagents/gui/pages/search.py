"""Search + export tab.

End-to-end flow:

1. User fills query / sources / language / year range / max-results.
2. ``Search`` button kicks off :func:`thesisagents.core.pipeline.run_search`
   on a worker thread.
3. Results populate the table; status bar reports the count. With a
   citation snowball selected the top results are expanded along their
   citation links first, and with a library file and "add" ticked the
   results are merged into it.
   ``Search library`` fills the same table from the library file instead,
   without any network access.
4. ``Export…`` opens a directory picker and runs ``export_collection``
   on another worker thread.

All worker callbacks land on the main thread because Qt signal/slot
across threads is queue-routed automatically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QModelIndex, QObject, QPoint, QSettings, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.constants import (
    ALL_SOURCES,
    DEFAULT_PAGE_SIZE,
    EXPORT_BIBTEX,
    EXPORT_PPTX,
    EXPORT_XLSX,
    MAX_RESULTS_PER_SOURCE,
)
from thesisagents.core.local_pdf import build_local_collection
from thesisagents.core.models import ExportOptions, Paper, PaperCollection, Query
from thesisagents.core.pipeline import run_search
from thesisagents.core.query import normalize_query
from thesisagents.core.search_workbook import read_search_workbook
from thesisagents.core.snowball import Direction, expand_collection, snowball
from thesisagents.exporters import export_collection
from thesisagents.exporters.i18n import SUPPORTED_LANGUAGES as DECK_LANGUAGES
from thesisagents.fetchers.http import shutdown_clients
from thesisagents.gui.i18n import LANGUAGE_DISPLAY_NAMES, t
from thesisagents.gui.models.papers_table_model import PaperFilterProxy, PapersTableModel
from thesisagents.gui.pages.settings import saved_vpn_access
from thesisagents.gui.search_outcome import SearchOutcome, finished_status
from thesisagents.gui.widgets.paper_actions import open_web_link, paper_menu
from thesisagents.gui.widgets.responsive import (
    AdaptiveSplit,
    Breakpoint,
    adapt_form_rows,
    make_card,
)
from thesisagents.gui.widgets.snowball_bounds import SnowballBounds, SnowballBoundsForm
from thesisagents.gui.widgets.source_multiselect import SourceMultiselect
from thesisagents.gui.workers import AsyncWorker, BlockingWorker
from thesisagents.library import AddReport, Library

_MIN_YEAR = 1900
_MAX_YEAR = 2100
#: Formats the one-button Export writes. Built from the format constants, not
#: typed out: the literal ``"bibtex"`` used here before is not a registered
#: format (the name is ``"bib"``), so the button reported
#: "no exporter registered for this format" on every click.
QUICK_EXPORT_FORMATS: tuple[str, ...] = (EXPORT_PPTX, EXPORT_XLSX, EXPORT_BIBTEX)
#: Label shown next to a source that contributed nothing for a reason other
#: than "no match". ``SourceStatus.OK`` is absent on purpose: an ok source
#: shows its result count instead.


#: The snowball selector: label key and the direction it stands for. The
#: bounds (``SnowballBounds``) default to the CLI's, so the same search gives
#: the same expansion from either surface unless *Advanced* changes them.
_SNOWBALL_CHOICES: tuple[tuple[str, str | None], ...] = (
    ("search.snowball_off", None),
    ("search.snowball_references", Direction.REFERENCES.value),
    ("search.snowball_cited_by", Direction.CITED_BY.value),
    ("search.snowball_both", Direction.BOTH.value),
)
_LIBRARY_FILE_FILTER = "SQLite (*.db *.sqlite *.sqlite3);;All files (*)"
#: Result columns hidden on a compact window (authors, DOI): the title needs
#: the room, and both values stay in the export.
_COMPACT_HIDDEN_COLUMNS: tuple[int, ...] = (1, 4)
#: Starting widths of the title and authors columns, in pixels.
_TITLE_COLUMN_WIDTH = 300
_AUTHORS_COLUMN_WIDTH = 150
#: Link schemes a double-click may hand to the desktop browser.
#: QSettings group the form is saved under when the window closes.
_FORM_GROUP = "form/search"


class SearchPage(QWidget):
    """Search + export page."""

    # Emitted whenever a fresh search completes (or the cached collection
    # is cleared). Receivers should use ``isinstance(obj, PaperCollection)``
    # because Signal(object) is the only typed-Python way to ship a
    # frozen dataclass across threads.
    collection_ready = Signal(object)
    saved_search_loading = Signal(bool)
    saved_search_failed = Signal(object)
    #: The library file named on this tab, emitted as it is typed. The Deck
    #: tab listens, so its export keeps identifier checks in the same library.
    library_path_changed = Signal(str)
    #: ``True`` when a search, library search or export starts on a worker
    #: thread, ``False`` when it ends either way. The main window shows its
    #: progress indicator while any page is busy.
    busy_changed = Signal(bool)

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._papers_model = PapersTableModel(language=ui_language)
        self._proxy = PaperFilterProxy(self)
        self._proxy.setSourceModel(self._papers_model)
        self._worker: AsyncWorker | None = None
        # The signals object of the run whose result the page is waiting for.
        # A result from any other worker is stale and ignored, see
        # ``_is_stale_result``.
        self._run_signals: QObject | None = None
        self._opening_saved_search = False
        # Where local PDFs are copied (``{folder}/pdfs``). The main window
        # points it at the Deck page's output folder, so the copies sit next
        # to the deck built from them.
        self._output_dir: Callable[[], str] = lambda: str(Path.cwd() / "exports")
        # Set while a fresh result is loaded into the model, so the
        # ``checks_changed`` that loading fires does not send it on twice.
        self._loading = False
        self._build_ui()
        self._papers_model.checks_changed.connect(self._on_checks_changed)
        self.apply_access(saved_vpn_access())

    def _build_ui(self) -> None:
        """Controls in three cards, the results table beside or below them.

        The cards group the form by question: what to search (query and
        sources), which papers to keep (language, count, years, venues), and
        what to do around the search (snowball, library). The action buttons
        sit in a footer pinned below the cards, so Search stays in reach
        however far the cards are scrolled.
        """
        language = self._ui_language
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 6, 0)
        controls_layout.setSpacing(12)

        query_card, query_layout = make_card(t("search.card_query", language), controls)
        self._query_input = QLineEdit(self)
        self._query_input.setPlaceholderText(t("search.query_placeholder", language))
        self._query_input.setClearButtonEnabled(True)
        # Enter in the query field runs the search, like a browser's search box.
        self._query_input.returnPressed.connect(self._on_search_clicked)
        query_layout.addWidget(QLabel(t("search.query_label", language), query_card))
        query_layout.addWidget(self._query_input)
        query_layout.addWidget(QLabel(t("search.sources_label", language), query_card))
        self._sources_widget = SourceMultiselect(self)
        query_layout.addWidget(self._sources_widget)
        self._ieee_note = QLabel(t("search.ieee_locked_note", language), query_card)
        self._ieee_note.setObjectName("Muted")
        self._ieee_note.setWordWrap(True)
        query_layout.addWidget(self._ieee_note)
        local_row = QHBoxLayout()
        self._local_button = QPushButton(t("search.local_button", language), self)
        self._local_button.clicked.connect(self._on_local_clicked)
        local_row.addWidget(self._local_button)
        local_row.addStretch(1)
        query_layout.addLayout(local_row)
        controls_layout.addWidget(query_card)

        filters_card, filters_layout = make_card(t("search.card_filters", language), controls)
        form = QFormLayout()
        filters_layout.addLayout(form)

        self._language_combo = QComboBox(self)
        for code in DECK_LANGUAGES:
            display = LANGUAGE_DISPLAY_NAMES.get(code, code)
            # Suffix the BCP-47 code in dim parens so power users can
            # tell which slide-deck locale they are about to ship.
            self._language_combo.addItem(f"{display} ({code})", code)
        form.addRow(t("search.language_label", language), self._language_combo)

        self._max_spin = QSpinBox(self)
        self._max_spin.setRange(1, MAX_RESULTS_PER_SOURCE)
        self._max_spin.setValue(DEFAULT_PAGE_SIZE)
        form.addRow(t("search.max_results_label", language), self._max_spin)

        year_row = QWidget(self)
        year_layout = QHBoxLayout(year_row)
        year_layout.setContentsMargins(0, 0, 0, 0)
        self._year_from_spin = self._year_spin()
        self._year_to_spin = self._year_spin()
        year_layout.addWidget(QLabel(t("search.year_from", language)))
        year_layout.addWidget(self._year_from_spin, stretch=1)
        year_layout.addWidget(QLabel(t("search.year_to", language)))
        year_layout.addWidget(self._year_to_spin, stretch=1)
        form.addRow(year_row)

        self._top_tier_check = QCheckBox(t("search.top_tier_only", language), self)
        self._top_tier_check.setChecked(True)
        form.addRow(self._top_tier_check)
        adapt_form_rows(filters_card, form)
        controls_layout.addWidget(filters_card)

        library_card, library_card_layout = make_card(
            t("search.card_library", language), controls
        )
        library_form = QFormLayout()
        library_card_layout.addLayout(library_form)
        self._snowball_combo = QComboBox(self)
        for label_key, direction in _SNOWBALL_CHOICES:
            self._snowball_combo.addItem(t(label_key, language), direction)
        library_form.addRow(t("search.snowball_label", language), self._snowball_combo)
        self._snowball_advanced_check = QCheckBox(t("search.snowball_advanced", language), self)
        library_form.addRow(self._snowball_advanced_check)
        self._snowball_advanced = SnowballBoundsForm(language, self)
        self._snowball_advanced.setVisible(False)
        self._snowball_advanced_check.toggled.connect(self._snowball_advanced.setVisible)
        library_form.addRow(self._snowball_advanced)

        library_row = QWidget(self)
        library_layout = QHBoxLayout(library_row)
        library_layout.setContentsMargins(0, 0, 0, 0)
        self._library_input = QLineEdit(self)
        self._library_input.setPlaceholderText(t("search.library_placeholder", language))
        self._library_input.textChanged.connect(
            lambda text: self.library_path_changed.emit(text.strip())
        )
        library_browse = QPushButton(t("search.library_browse", language), self)
        library_browse.clicked.connect(self._on_browse_library)
        library_layout.addWidget(self._library_input, stretch=1)
        library_layout.addWidget(library_browse)
        library_form.addRow(t("search.library_label", language), library_row)

        self._library_add_check = QCheckBox(t("search.library_add", language), self)
        library_form.addRow(self._library_add_check)
        adapt_form_rows(library_card, library_form)
        controls_layout.addWidget(library_card)
        controls_layout.addStretch(1)

        footer = QWidget(self)
        button_row = QHBoxLayout(footer)
        button_row.setContentsMargins(0, 0, 6, 0)
        self._search_button = QPushButton(t("search.search_button", language), self)
        self._search_button.setProperty("primary", True)
        self._search_button.setDefault(True)
        self._search_button.clicked.connect(self._on_search_clicked)
        self._library_search_button = QPushButton(
            t("search.library_search_button", language), self
        )
        self._library_search_button.clicked.connect(self._on_library_search_clicked)
        self._export_button = QPushButton(t("search.export_button", language), self)
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._on_export_clicked)
        self._cancel_button = QPushButton(t("action.cancel", language), self)
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self._search_button, stretch=1)
        button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._library_search_button)
        button_row.addWidget(self._export_button)

        results = QWidget(self)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(6, 0, 0, 0)
        results_title = QLabel(t("search.results_title", language), results)
        results_title.setObjectName("CardTitle")
        results_layout.addWidget(results_title)
        results_layout.addLayout(self._build_filter_row())
        self._table = QTableView(self)
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # Title and authors get fixed, user-resizable widths and the last
        # column takes what is left. A stretched title shrank to a few
        # characters beside six content-sized columns; now a narrow pane
        # scrolls sideways instead and the title stays readable.
        for column, width in ((0, _TITLE_COLUMN_WIDTH), (1, _AUTHORS_COLUMN_WIDTH)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            header.resizeSection(column, width)
        header.setStretchLastSection(True)
        # No sort until the user clicks a header: the result keeps its
        # ranked order (Qt would otherwise sort by the first column at once).
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_menu)
        results_layout.addWidget(self._table, stretch=1)
        self._status_label = QLabel(t("search.status_idle", language), self)
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        results_layout.addWidget(self._status_label)

        self._split = AdaptiveSplit(controls, results, footer=footer, parent=self)
        outer.addWidget(self._split)

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Re-arrange for the window size class (called by the main window).

        On a compact window the authors and DOI columns are hidden: with the
        title squeezed to a few characters the table is unreadable, and both
        values stay in the row's export.
        """
        self._split.apply_breakpoint(breakpoint)
        compact = breakpoint is Breakpoint.COMPACT
        for column in _COMPACT_HIDDEN_COLUMNS:
            self._table.setColumnHidden(column, compact)

    def _on_row_double_clicked(self, index: QModelIndex) -> None:
        """Open the paper's landing page in the browser.

        Only ``http`` / ``https`` links are opened: the URL comes from a
        remote API, and handing a ``file:`` or custom-scheme link to the
        desktop would let a source record launch a local program.
        """
        paper = self._paper_at(index)
        if paper is not None:
            open_web_link(paper.url)

    def _paper_at(self, index: QModelIndex) -> Paper | None:
        """The paper behind a table index (sorted / filtered or not)."""
        if index.model() is self._proxy:
            index = self._proxy.mapToSource(index)
        papers = self._papers_model.papers()
        return papers[index.row()] if 0 <= index.row() < len(papers) else None

    # --- results: filter, ticks, context menu --------------------------

    def _build_filter_row(self) -> QVBoxLayout:
        """Filter box and source picker, then tick / untick and the count.

        Two lines rather than one: on one line the four controls squeezed
        the filter box to a few characters in long-label languages.
        """
        language = self._ui_language
        rows = QVBoxLayout()
        top = QHBoxLayout()
        row = QHBoxLayout()
        self._filter_input = QLineEdit(self)
        self._filter_input.setPlaceholderText(t("search.filter_placeholder", language))
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.textChanged.connect(self._proxy.set_text)
        self._filter_source = QComboBox(self)
        self._filter_source.addItem(t("search.filter_all_sources", language), None)
        self._filter_source.currentIndexChanged.connect(
            lambda _i: self._proxy.set_source(self._filter_source.currentData())
        )
        tick = QPushButton(t("search.tick_shown", language), self)
        tick.clicked.connect(lambda: self._tick_shown(True))
        untick = QPushButton(t("search.untick_shown", language), self)
        untick.clicked.connect(lambda: self._tick_shown(False))
        self._selection_label = QLabel("", self)
        self._selection_label.setObjectName("Muted")
        top.addWidget(self._filter_input, stretch=1)
        top.addWidget(self._filter_source)
        row.addWidget(tick)
        row.addWidget(untick)
        row.addStretch(1)
        row.addWidget(self._selection_label)
        rows.addLayout(top)
        rows.addLayout(row)
        return rows

    def _tick_shown(self, checked: bool) -> None:
        """Tick or untick every row the filter currently shows."""
        rows = [
            self._proxy.mapToSource(self._proxy.index(r, 0)).row()
            for r in range(self._proxy.rowCount())
        ]
        self._papers_model.set_all_checked(checked, rows)

    def _refresh_filter_sources(self, collection: PaperCollection) -> None:
        current = self._filter_source.currentData()
        self._filter_source.blockSignals(True)
        while self._filter_source.count() > 1:
            self._filter_source.removeItem(1)
        for source in sorted({paper.source for paper in collection.papers}):
            self._filter_source.addItem(source, source)
        index = self._filter_source.findData(current)
        self._filter_source.setCurrentIndex(max(0, index))
        self._filter_source.blockSignals(False)
        self._proxy.set_source(self._filter_source.currentData())

    def selected_collection(self) -> PaperCollection | None:
        """The current result narrowed to the ticked papers, or ``None``."""
        collection = self.collection()
        if collection is None:
            return None
        return replace(  # NOSONAR dataclasses.replace returns the same dataclass type
            collection, papers=self._papers_model.checked_papers()
        )

    def _on_checks_changed(self) -> None:
        total = len(self._papers_model.papers())
        self._selection_label.setText(
            t(
                "search.selection_count", self._ui_language,
                checked=self._papers_model.checked_count(), total=total,
            ) if total else ""
        )
        if self._loading or self.collection() is None:
            return
        subset = self.selected_collection()
        self._export_button.setEnabled(bool(subset and subset.papers) and not self._busy())
        self.collection_ready.emit(subset)

    def _on_table_menu(self, pos: QPoint) -> None:
        paper = self._paper_at(self._table.indexAt(pos))
        if paper is None:
            return
        menu = paper_menu(paper, self._ui_language, self)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # --- snowball bounds ------------------------------------------------

    def snowball_bounds(self) -> SnowballBounds:
        """The bounds the next search will use."""
        return self._snowball_advanced.bounds()

    def set_snowball_bounds(self, bounds: SnowballBounds) -> None:
        self._snowball_advanced.set_bounds(bounds)

    # --- local PDFs (progress #29) -----------------------------------------

    def set_output_dir_provider(self, provider: Callable[[], str]) -> None:
        """Where local PDFs are copied: ``provider()`` names the export folder."""
        self._output_dir = provider

    def choose_saved_search(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window(), t("deck.source_open", self._ui_language),
            self._output_dir(), "Excel (*.xlsx)",
        )
        if path:
            self.open_saved_search(path)

    def open_saved_search(self, path: str) -> None:
        """Load a prior export into the same selection as a live search."""
        if self._busy():
            return
        self._opening_saved_search = True
        self.saved_search_loading.emit(True)
        self._set_busy()
        worker = BlockingWorker(lambda: read_search_workbook(Path(path)))
        worker.signals.failed.connect(self.saved_search_failed)
        self._start_run(worker)

    def _on_local_clicked(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, t("search.local_dialog_title", self._ui_language),
            str(Path.cwd()), "PDF (*.pdf);;All files (*)",
        )
        if paths:
            self.read_local_pdfs(paths)

    def read_local_pdfs(self, paths: list[str]) -> None:
        """Read local PDFs on a worker thread and show them as the result.

        The GUI form of the CLI's ``--pdf`` mode
        (``core.local_pdf.build_local_collection``): each file's own front
        matter gives its title, authors, year, DOI and abstract, and a copy
        goes to ``{export folder}/pdfs``. The papers then behave like search
        results, so they can be ticked, enriched and built into a deck.
        """
        if self._busy():
            return
        out_dir = self._output_dir() or str(Path.cwd() / "exports")
        self._set_busy()
        self._local_button.setEnabled(False)
        self._set_status(t("search.local_running", self._ui_language))

        def call() -> SearchOutcome:
            return SearchOutcome(build_local_collection(paths, out_dir), local_folder=out_dir)

        self._start_run(BlockingWorker(call))

    # --- remembered form ------------------------------------------------

    def apply_access(self, vpn_access: bool) -> None:
        """Lock the ``ieee`` source while VPN / institutional access is not declared.

        The project's IEEE rule (``CLAUDE.md``) asks for the access status
        before any search with ``ieee`` in the mix. The GUI's answer is the
        Settings switch, so with it off ``ieee`` is unticked, greyed out and
        never sent, even when a restored form had it ticked (owner's option
        (a) for ``progress.md`` #30). Called at start and on every Settings save.
        """
        self._sources_widget.set_locked(
            "ieee", not vpn_access, t("search.ieee_locked_note", self._ui_language)
        )
        self._ieee_note.setVisible(not vpn_access)

    def save_form(self, store: QSettings) -> None:
        """Write every search field to ``store`` (called when the window closes)."""
        bounds = self.snowball_bounds()
        values: dict[str, object] = {
            "query": self._query_input.text(),
            "sources": ",".join(self._sources_widget.selected()),
            "language": self._language_combo.currentData() or "en",
            "max_results": self._max_spin.value(),
            "year_from": self._year_from_spin.value(),
            "year_to": self._year_to_spin.value(),
            "top_tier": self._top_tier_check.isChecked(),
            "snowball": self._snowball_combo.currentData() or "",
            "snowball_advanced": self._snowball_advanced_check.isChecked(),
            "snowball_seeds": bounds.seeds,
            "snowball_depth": bounds.depth,
            "snowball_max_per_seed": bounds.max_per_seed,
            "snowball_max_total": bounds.max_total,
            "snowball_min_relevance": bounds.min_relevance or 0.0,
            "library": self._library_input.text(),
            "library_add": self._library_add_check.isChecked(),
        }
        for key, value in values.items():
            store.setValue(f"{_FORM_GROUP}/{key}", value)

    def restore_form(self, store: QSettings) -> None:
        """Fill the fields from ``store``. Missing or invalid values keep the defaults."""

        def get(key: str, default: object, kind: type) -> object:
            full = f"{_FORM_GROUP}/{key}"
            if not store.contains(full):
                return default
            try:
                return store.value(full, default, type=kind)
            except (TypeError, ValueError):
                return default

        self._query_input.setText(str(get("query", "", str)))
        sources = str(get("sources", "", str))
        if store.contains(f"{_FORM_GROUP}/sources"):
            wanted = tuple(name for name in sources.split(",") if name in ALL_SOURCES)
            self._sources_widget.set_selected(wanted)
        _select_data(self._language_combo, get("language", "en", str))
        self._max_spin.setValue(int(get("max_results", self._max_spin.value(), int)))
        self._year_from_spin.setValue(int(get("year_from", self._year_from_spin.value(), int)))
        self._year_to_spin.setValue(int(get("year_to", self._year_to_spin.value(), int)))
        self._top_tier_check.setChecked(bool(get("top_tier", True, bool)))
        _select_data(self._snowball_combo, get("snowball", "", str) or None)
        self._snowball_advanced_check.setChecked(bool(get("snowball_advanced", False, bool)))
        defaults = SnowballBounds()
        floor = float(get("snowball_min_relevance", 0.0, float))
        self.set_snowball_bounds(
            SnowballBounds(
                seeds=int(get("snowball_seeds", defaults.seeds, int)),
                depth=int(get("snowball_depth", defaults.depth, int)),
                max_per_seed=int(get("snowball_max_per_seed", defaults.max_per_seed, int)),
                max_total=int(get("snowball_max_total", defaults.max_total, int)),
                min_relevance=floor if floor > 0 else None,
            )
        )
        self._library_input.setText(str(get("library", "", str)))
        self._library_add_check.setChecked(bool(get("library_add", False, bool)))

    def split(self) -> AdaptiveSplit:
        return self._split

    def table(self) -> QTableView:
        return self._table

    def _year_spin(self) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(_MIN_YEAR - 1, _MAX_YEAR)
        spin.setSpecialValueText("—")
        spin.setValue(_MIN_YEAR - 1)
        return spin

    def _year(self, spin: QSpinBox) -> int | None:
        value = spin.value()
        return value if value >= _MIN_YEAR else None

    def current_query(self) -> Query | None:
        """The search the form describes, None while it is incomplete.

        Raises ``ValueError`` for one that cannot be run, such as a year range
        that ends before it starts.
        """
        keywords = self._query_input.text().strip()
        sources = self._sources_widget.selected()
        if not keywords or not sources:
            return None
        return Query(
            keywords=normalize_query(keywords),
            sources=sources,
            max_results=self._max_spin.value(),
            year_from=self._year(self._year_from_spin),
            year_to=self._year(self._year_to_spin),
            top_tier_only=self._top_tier_check.isChecked(),
        )

    def _on_search_clicked(self) -> None:
        # Enter in the query field reaches this even while the Search button
        # is disabled, so the busy check has to live here and not on the button.
        if self._busy():
            return
        try:
            query = self.current_query()
        except ValueError as err:
            self._set_status(t("search.error_generic", self._ui_language, error=str(err)))
            return
        if query is None:
            self._set_status(t("search.error_empty_query", self._ui_language))
            return
        direction = self._snowball_combo.currentData()
        bounds = self.snowball_bounds()
        library_path = self._library_path()
        add_to_library = self._library_add_check.isChecked()
        if add_to_library and not library_path:
            self._set_status(t("search.error_no_library", self._ui_language))
            return
        self._set_busy()

        async def coro() -> SearchOutcome:
            discovered: int | None = None
            try:
                collection = await run_search(query)
                if direction and collection.papers:
                    found = await snowball(
                        collection.papers[: bounds.seeds],
                        known=collection.papers,
                        direction=direction,
                        depth=bounds.depth,
                        max_per_seed=bounds.max_per_seed,
                        max_total=bounds.max_total,
                        keywords=query.keywords,
                        min_relevance=bounds.min_relevance,
                    )
                    collection = expand_collection(collection, found)
                    discovered = len(found.discovered)
            finally:
                await shutdown_clients()
            report: AddReport | None = None
            if add_to_library and collection.papers:
                with Library(library_path) as library:
                    report = library.add_collection(collection)
            return SearchOutcome(collection, discovered=discovered, library=report)

        worker = AsyncWorker(coro)
        worker.signals.cancelled.connect(self._on_search_cancelled)
        self._worker = worker
        self._cancel_button.setVisible(True)
        self._start_run(worker)

    def _on_cancel_clicked(self) -> None:
        """Stop the running search at its next network wait."""
        if self._worker is not None:
            self._cancel_button.setEnabled(False)
            self._worker.cancel()

    def _on_search_cancelled(self) -> None:
        """A cancelled search changes nothing: the previous result stays."""
        if self._is_stale_result():
            return
        self._end_busy()
        self._set_status(t("search.status_cancelled", self._ui_language))

    def _on_library_search_clicked(self) -> None:
        """Fill the table from the library file. No network is used.

        The query field is the library query: stored papers matching it are
        listed best first, and an empty field lists the most recently seen.
        Max results and the year range apply. The papers then behave like
        search results: they can be exported, enriched and built into a deck.
        """
        if self._busy():
            return
        library_path = self._library_path()
        if not library_path:
            self._set_status(t("search.error_no_library", self._ui_language))
            return
        text = self._query_input.text().strip()
        limit = self._max_spin.value()
        year_from = self._year(self._year_from_spin)
        year_to = self._year(self._year_to_spin)
        self._set_busy()

        def call() -> SearchOutcome:
            with Library(library_path, create=False) as library:
                collection = library.collection(
                    text, limit=limit, year_from=year_from, year_to=year_to
                )
                return SearchOutcome(collection, library_total=len(library))

        self._start_run(BlockingWorker(call))

    def _on_browse_library(self) -> None:
        # A save dialog without the overwrite prompt: the file may exist (an
        # existing library) or not yet (one is created on the first add).
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("search.library_dialog_title", self._ui_language),
            self._library_path() or str(Path.cwd() / "thesis.db"),
            _LIBRARY_FILE_FILTER,
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if path:
            self._library_input.setText(path)

    def _library_path(self) -> str:
        return self._library_input.text().strip()

    def _set_busy(self) -> None:
        self._search_button.setEnabled(False)
        self._library_search_button.setEnabled(False)
        self._export_button.setEnabled(False)
        self._set_status(t("search.status_running", self._ui_language))
        self.busy_changed.emit(True)

    def _busy(self) -> bool:
        """True while a search, library search or local PDF read is running.

        Every entry point that starts one of those calls this first. **Failure
        mode prevented**: Enter in the query field bypasses the disabled
        Search button, so without the check a second worker replaced the
        first as the current one and the older query, finishing later,
        overwrote the newer result and re-enabled the form early.
        """
        return not self._search_button.isEnabled()

    def _start_run(self, worker: AsyncWorker | BlockingWorker) -> None:
        """Make ``worker`` the current run, connect its result, and start it.

        The page remembers the worker's signals object so the handlers can
        tell this run's result from a late one of an earlier worker. The
        signals connect to bound methods and never to a lambda (see
        ``gui/workers.py``).
        """
        worker.signals.finished.connect(self._on_search_finished)
        worker.signals.failed.connect(self._on_worker_failed)
        self._run_signals = worker.signals
        QThreadPool.globalInstance().start(worker)

    def _is_stale_result(self) -> bool:
        """True when the signal being handled comes from a worker that is not current.

        A direct call (``show_results``, tests) has no sender and is never
        stale. **Failure mode prevented**: a result delivered after its run
        stopped being the current one replaced the table and ended the busy
        state of the run that is still going.

        Example: run A starts, then A's result is delivered after run B became
        current. ``sender()`` is A's signals object, which is not
        ``_run_signals`` (B's), so the result is dropped.
        """
        sender = self.sender()
        return sender is not None and sender is not self._run_signals

    def _end_busy(self) -> None:
        """Re-enable the buttons and hide Cancel after any run ends."""
        self._worker = None
        self._run_signals = None
        self._cancel_button.setVisible(False)
        self._cancel_button.setEnabled(True)
        self._search_button.setEnabled(True)
        self._library_search_button.setEnabled(True)
        self._local_button.setEnabled(True)
        subset = self.selected_collection()
        self._export_button.setEnabled(bool(subset and subset.papers))
        if self._opening_saved_search:
            self._opening_saved_search = False
            self.saved_search_loading.emit(False)
        self.busy_changed.emit(False)

    def _on_search_finished(self, result: object) -> None:
        if self._is_stale_result():
            return
        outcome = result if isinstance(result, SearchOutcome) else None
        collection = outcome.collection if outcome is not None else result
        if not isinstance(collection, PaperCollection):  # pragma: no cover — defensive
            self._on_worker_failed(
                RuntimeError(f"unexpected worker result type: {type(collection)!r}")
            )
            return
        self._loading = True
        try:
            self._papers_model.set_collection(collection)
        finally:
            self._loading = False
        self._refresh_filter_sources(collection)
        self._end_busy()
        # Tell downstream pages (Enrich, Deck) about the fresh results
        # so they enable their own actions without polling. Every paper
        # starts ticked, so this is the whole result.
        self.collection_ready.emit(collection)
        self._set_status(finished_status(collection, outcome, self._ui_language))

    def _on_worker_failed(self, err: object) -> None:
        if self._is_stale_result():
            return
        self._end_busy()
        self._set_status(
            t("search.error_generic", self._ui_language, error=str(err))
        )

    def _on_export_clicked(self) -> None:
        subset = self.selected_collection()
        if subset is None or not subset.papers:
            self._set_status(t("search.error_no_results", self._ui_language))
            return
        directory = QFileDialog.getExistingDirectory(
            self,
            t("search.export_dialog_title", self._ui_language),
            str(Path.cwd() / "exports"),
        )
        if not directory:
            return
        language = self._language_combo.currentData() or "en"
        options = ExportOptions(
            formats=QUICK_EXPORT_FORMATS,
            out_dir=directory,
            language=language,
        )
        collection = subset
        self._export_button.setEnabled(False)
        self._set_status(t("search.status_export_running", self._ui_language))
        self.busy_changed.emit(True)

        library_path = self._library_path()

        def export_call() -> dict[str, Path]:
            if not library_path:
                return export_collection(collection, options)
            # With a library file the identifier checks are kept in it, so a
            # DOI or URL verified by an earlier export is not asked about again.
            with Library(library_path) as library:
                return export_collection(
                    collection, options, verification_cache=library.verification_cache()
                )

        worker = BlockingWorker(export_call)
        worker.signals.finished.connect(self._on_export_finished)
        worker.signals.failed.connect(self._on_export_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_export_finished(self, written: object) -> None:
        self.busy_changed.emit(False)
        self._export_button.setEnabled(True)
        if not isinstance(written, dict) or not written:
            self._set_status(t("search.error_no_results", self._ui_language))
            return
        any_path = next(iter(written.values()))
        self._set_status(
            t("search.status_export_done", self._ui_language, path=str(any_path))
        )

    def _on_export_failed(self, err: object) -> None:
        """An export failed: report it without touching the search run.

        An export is not a run of the form, so its failure must not end the
        busy state of a search that may still be going.
        """
        self.busy_changed.emit(False)
        subset = self.selected_collection()
        self._export_button.setEnabled(bool(subset and subset.papers) and not self._busy())
        self._set_status(t("search.error_generic", self._ui_language, error=str(err)))

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    # --- accessors used by tests ----------------------------------------

    def papers_model(self) -> PapersTableModel:
        return self._papers_model

    def collection(self) -> PaperCollection | None:
        """The whole current result (ticked or not), ``None`` before a search."""
        return self._papers_model.collection

    def show_results(
        self, collection: PaperCollection, unchecked_rows: tuple[int, ...] | list[int] = ()
    ) -> None:
        """Show ``collection`` as if a search had returned it, then untick
        ``unchecked_rows``. Used when the window is rebuilt in another language."""
        self._on_search_finished(collection)
        if unchecked_rows:
            self._papers_model.set_all_checked(False, list(unchecked_rows))

    def status_text(self) -> str:
        return self._status_label.text()

    def set_query_text(self, text: str) -> None:
        self._query_input.setText(text)

    def set_library_path(self, path: str) -> None:
        self._library_input.setText(path)

    def library_add_checkbox(self) -> QCheckBox:
        return self._library_add_check

    def snowball_combo(self) -> QComboBox:
        return self._snowball_combo


def _select_data(combo: QComboBox, data: object) -> None:
    """Select the item whose data is ``data``; leave the combo alone if absent."""
    index = combo.findData(data)
    if index >= 0:
        combo.setCurrentIndex(index)

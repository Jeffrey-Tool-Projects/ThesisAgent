"""Library page: a view of a literature library file, and the place to edit it.

Closes ``progress.md`` #20. Before this page a library (``thesisagents/library/``)
could only be *searched* from the GUI. Its statistics, the searches that
filled it, the citation links between its papers and the stored DOI / URL
verdicts were reachable from the CLI, MCP (``library_stats``) and Python only.

What the page shows, all read from one :class:`LibrarySnapshot` loaded on a
worker thread:

* an **Overview** card: papers, searches, citation links, year span, papers
  per source, identifier checks per status;
* a **Filter** card: by tag, reading status and screening decision;
* a **Papers** tab: every stored paper (or those matching the find box and
  the filter), for the selected one its citation neighbours inside the
  library and its stored identifier verdicts, and below it the editor for
  tags, status, note and screening (``widgets/paper_editor.py``);
* a **Saved searches** tab, a **Citations** tab (``widgets/citation_graph.py``),
  a **Review** tab (the PRISMA flow) and a **Searches** tab: every import.

Every write goes through :meth:`LibraryPage.run_edit`: a function of an open
``Library`` runs on a worker thread and a fresh snapshot comes back, so the
UI thread never touches the database. The file is opened with
``create=False`` except by an import, so a typo in the path says "no library
there" instead of creating an empty one. **Send to Enrich and Deck** hands
the listed papers on like a search result.
"""

from __future__ import annotations

import html
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QItemSelectionModel, QSettings, Qt, QThreadPool, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableView,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.bib_import import read_bibliography
from thesisagents.core.diagnostics import PaperRelation
from thesisagents.core.export_validation import KIND_DOI, KIND_URL
from thesisagents.core.identifiers import canonical_doi
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.gui.i18n import t
from thesisagents.gui.widgets.citation_graph import CitationGraph, GraphNode
from thesisagents.gui.widgets.library_tabs import (
    DuplicatesDialog,
    ReviewTab,
    SavedSearchesTab,
    prisma_labels,
)
from thesisagents.gui.widgets.paper_editor import EditRequest, PaperEditor
from thesisagents.gui.widgets.responsive import (
    AdaptiveSplit,
    Breakpoint,
    adapt_form_rows,
    make_card,
)
from thesisagents.gui.workers import AsyncWorker, BlockingWorker
from thesisagents.library import (
    DECISIONS,
    READING_STATUSES,
    Library,
    LibraryEntry,
    LibraryRun,
    LibraryStats,
    PrismaFlow,
    SavedSearch,
    SavedSearchOutcome,
    prisma_flow,
    prisma_svg,
    run_saved_search,
)

_BIBLIOGRAPHY_FILTER = "BibTeX / RIS (*.bib *.ris *.txt);;All files (*)"
_LIBRARY_FILE_FILTER = "SQLite (*.db *.sqlite *.sqlite3);;All files (*)"
_FORM_GROUP = "form/library"
_NO_VALUE = "—"
#: Role the tables sort by: numbers for counts and years (a missing year as
#: -1), case-folded text otherwise. A display column mixing ``2024`` and
#: ``"—"`` cannot be compared directly.
_SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 2


@dataclass(frozen=True)
class IdentifierVerdict:
    """One stored DOI / URL check of a paper: kind, value, status, date (ISO)."""

    kind: str
    value: str
    status: str
    checked_at: str


@dataclass(frozen=True)
class LibraryFilter:
    """The reader's filter. Empty means "any"."""

    tag: str = ""
    status: str = ""
    decision: str = ""

    def criteria(self) -> dict[str, object]:
        """As keyword arguments of ``Library.search``."""
        return {
            "tags": (self.tag,) if self.tag else (),
            "status": self.status,
            "decision": self.decision,
        }


@dataclass(frozen=True)
class LibrarySnapshot:
    """Everything the page shows, read in one go on a worker thread.

    The boundary this guards: the SQLite connection. It lives only inside
    :func:`load_snapshot`, so the UI thread never touches the database and
    a slow disk never freezes the window. ``collection`` is what **Send to
    Enrich and Deck** hands on: the listed papers with their citation links.

    Example: ``load_snapshot("thesis.db", "graph").stats.papers``.
    """

    path: str
    query: str
    stats: LibraryStats
    entries: tuple[LibraryEntry, ...]
    runs: tuple[LibraryRun, ...]
    relations: tuple[PaperRelation, ...]
    verdicts: Mapping[str, tuple[IdentifierVerdict, ...]]
    collection: PaperCollection
    shown: LibraryFilter = field(default_factory=LibraryFilter)
    tags: Mapping[str, int] = field(default_factory=dict)
    saved: tuple[SavedSearch, ...] = ()
    flow: PrismaFlow | None = None

    def paper_titles(self) -> dict[str, str]:
        """``dedup_key`` → title for every listed paper."""
        return {entry.paper.dedup_key(): entry.paper.title for entry in self.entries}


def load_snapshot(
    path: str, query: str = "", shown: LibraryFilter | None = None
) -> LibrarySnapshot:
    """Read a library file into a :class:`LibrarySnapshot`. Blocking.

    Raises ``FileNotFoundError`` (from ``Library(create=False)``) when there
    is no library at ``path``, which the page reports on its status line.
    """
    shown = shown or LibraryFilter()
    with Library(path, create=False) as library:
        entries = tuple(library.search(query, limit=None, **shown.criteria()))
        keys = {entry.paper.dedup_key() for entry in entries}
        relations = tuple(
            relation
            for relation in library.relations()
            if relation.source_key in keys or relation.target_key in keys
        )
        verdicts = {
            entry.paper.dedup_key(): _stored_verdicts(library, entry.paper)
            for entry in entries
        }
        return LibrarySnapshot(
            path=path,
            query=query,
            stats=library.stats(),
            entries=entries,
            runs=tuple(library.runs()),
            relations=relations,
            verdicts=verdicts,
            collection=library.collection(query, **shown.criteria()),
            shown=shown,
            tags=library.tags(),
            saved=tuple(library.saved_searches()),
            flow=prisma_flow(library),
        )


def _stored_verdicts(library: Library, paper: Paper) -> tuple[IdentifierVerdict, ...]:
    """The cached DOI and URL verdicts of ``paper``, keyed the way the export
    preflight stores them (a canonical DOI, an ``https`` URL)."""
    targets: list[tuple[str, str, str]] = []
    canonical = canonical_doi(paper.doi) if paper.doi else None
    if canonical:
        targets.append((KIND_DOI, paper.doi or canonical, canonical))
    if paper.url:
        url = paper.url.strip()
        https = "https://" + url[len("http://"):] if url.startswith("http://") else url
        targets.append((KIND_URL, url, https))
    found: list[IdentifierVerdict] = []
    for kind, shown, key in targets:
        stored = library.stored_verdict(kind, key)
        if stored is not None:
            verdict, when = stored
            found.append(
                IdentifierVerdict(kind, shown, verdict.status.value, when.date().isoformat())
            )
    return tuple(found)


@dataclass(frozen=True)
class _EditOutcome:
    """What a worker brought back: the edit's own result, the new state, and
    what turns the result into the status line."""

    value: object
    snapshot: LibrarySnapshot
    done: Callable[[object], str] | None = None


class LibraryPage(QWidget):
    """Browser and editor for a library file. See the module docstring."""

    #: The listed papers, sent on to Enrich and Deck like a search result.
    collection_ready = Signal(object)
    #: ``True`` while a library is being read on a worker thread.
    busy_changed = Signal(bool)

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._snapshot: LibrarySnapshot | None = None
        self._query_provider: Callable[[], Query | None] = lambda: None
        self._papers_model = QStandardItemModel(0, 8, self)
        self._runs_model = QStandardItemModel(0, 4, self)
        self._build_ui()

    # --- construction -----------------------------------------------------

    def _build_ui(self) -> None:
        language = self._ui_language
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 6, 0)
        controls_layout.setSpacing(12)

        file_card, file_layout = make_card(t("library.card_file", language), controls)
        path_row = QHBoxLayout()
        self._path_input = QLineEdit(self)
        self._path_input.setPlaceholderText(t("search.library_placeholder", language))
        self._path_input.returnPressed.connect(self._on_open_clicked)
        browse = QPushButton(t("search.library_browse", language), self)
        browse.clicked.connect(self._on_browse)
        path_row.addWidget(self._path_input, stretch=1)
        path_row.addWidget(browse)
        file_layout.addLayout(path_row)
        self._query_input = QLineEdit(self)
        self._query_input.setPlaceholderText(t("library.query_placeholder", language))
        self._query_input.setClearButtonEnabled(True)
        self._query_input.returnPressed.connect(self._on_open_clicked)
        file_layout.addWidget(self._query_input)
        controls_layout.addWidget(file_card)

        controls_layout.addWidget(self._build_filter_card(controls))

        overview_card, overview_layout = make_card(
            t("library.card_overview", language), controls
        )
        form = QFormLayout()
        overview_layout.addLayout(form)
        self._stat_labels: dict[str, QLabel] = {}
        for key in ("papers", "runs", "relations", "years", "sources", "checks"):
            value = QLabel(_NO_VALUE, overview_card)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(t(f"library.stat_{key}", language), value)
            self._stat_labels[key] = value
        # Short labels and values: keep them side by side down to 300 px.
        adapt_form_rows(overview_card, form, threshold=300)
        controls_layout.addWidget(overview_card)
        controls_layout.addStretch(1)

        footer = QWidget(self)
        buttons = QHBoxLayout(footer)
        buttons.setContentsMargins(0, 0, 6, 0)
        self._open_button = QPushButton(t("library.open_button", language), self)
        self._open_button.setProperty("primary", True)
        self._open_button.clicked.connect(self._on_open_clicked)
        self._send_button = QPushButton(t("library.send_button", language), self)
        self._send_button.setEnabled(False)
        self._send_button.clicked.connect(self._on_send_clicked)
        self._import_button = QPushButton(t("library.action_import", language), self)
        self._import_button.clicked.connect(self._on_import)
        self._duplicates_button = QPushButton(t("library.action_duplicates", language), self)
        self._duplicates_button.clicked.connect(self._on_duplicates)
        self._duplicates_button.setEnabled(False)
        buttons.addWidget(self._open_button, stretch=1)
        buttons.addWidget(self._import_button)
        buttons.addWidget(self._duplicates_button)
        buttons.addWidget(self._send_button)

        results = QWidget(self)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(6, 0, 0, 0)
        self._tabs = QTabWidget(results)
        self._tabs.setDocumentMode(True)
        # The style's own base line ignores the theme (a white rule in dark
        # mode); the stylesheet's pane border draws the line instead.
        self._tabs.tabBar().setDrawBase(False)
        self._tabs.addTab(self._build_papers_tab(), t("library.tab_papers", language))
        self._saved_tab = SavedSearchesTab(language, self)
        self._saved_tab.run_requested.connect(self._on_run_saved)
        self._saved_tab.delete_requested.connect(
            lambda name: self.run_edit(lambda library: library.delete_saved_search(name))
        )
        self._saved_tab.save_requested.connect(self._on_save_search)
        self._tabs.addTab(self._saved_tab, t("library.tab_saved", language))
        self._tabs.addTab(self._build_graph_tab(), t("library.tab_graph", language))
        self._review_tab = ReviewTab(language, self)
        self._review_tab.save_requested.connect(self._on_save_diagram)
        self._tabs.addTab(self._review_tab, t("library.tab_review", language))
        self._tabs.addTab(self._build_runs_tab(), t("library.tab_runs", language))
        results_layout.addWidget(self._tabs, stretch=1)
        self._status_label = QLabel("", self)
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        results_layout.addWidget(self._status_label)

        self._split = AdaptiveSplit(controls, results, footer=footer, parent=self)
        outer.addWidget(self._split)

    def _build_papers_tab(self) -> QWidget:
        language = self._ui_language
        self._papers_model.setHorizontalHeaderLabels([
            t("results.col_title", language),
            t("results.col_year", language),
            t("library.filter_status", language),
            t("library.col_tags", language),
            t("library.filter_decision", language),
            t("library.col_sources", language),
            t("library.col_seen", language),
            t("library.col_last_seen", language),
        ])
        self._papers_table = _table(self._papers_model, self)
        self._papers_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        header = self._papers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 320)
        self._papers_table.selectionModel().selectionChanged.connect(
            lambda *_: self._on_selection_changed()
        )
        self._detail = QTextBrowser(self)
        self._detail.setOpenLinks(False)
        self._detail.setPlaceholderText(t("library.detail_hint", language))
        split = QSplitter(Qt.Orientation.Vertical, self)
        split.setChildrenCollapsible(False)
        split.addWidget(self._papers_table)
        below = QTabWidget(self)
        below.setDocumentMode(True)
        below.tabBar().setDrawBase(False)
        self._editor = PaperEditor(language, below)
        self._editor.requested.connect(self.apply_edit)
        # The form scrolls on its own, so a short window does not squash it.
        form_scroll = QScrollArea(below)
        form_scroll.setWidget(self._editor)
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)
        below.addTab(form_scroll, t("library.tab_notes", language))
        below.addTab(self._detail, t("library.tab_details", language))
        corner = QWidget(below)
        actions = QHBoxLayout(corner)
        actions.setContentsMargins(0, 0, 0, 4)
        self._merge_button = QPushButton(t("library.action_merge", language), below)
        self._merge_button.clicked.connect(self._on_merge)
        self._delete_button = QPushButton(t("library.action_delete", language), below)
        self._delete_button.clicked.connect(self._on_delete)
        for button in (self._merge_button, self._delete_button):
            button.setObjectName("StatusButton")  # the compact look
            button.setEnabled(False)
            actions.addWidget(button)
        below.setCornerWidget(corner)
        split.addWidget(below)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        return split

    def _build_filter_card(self, parent: QWidget) -> QWidget:
        """Combos for tag, reading status and decision. Changing one reloads."""
        language = self._ui_language
        card, layout = make_card(t("library.card_filter", language), parent)
        form = QFormLayout()
        layout.addLayout(form)
        self._tag_filter = QComboBox(card)
        self._tag_filter.addItem(t("library.filter_any", language), "")
        self._status_filter = QComboBox(card)
        self._status_filter.addItem(t("library.filter_any", language), "")
        for status in READING_STATUSES:
            self._status_filter.addItem(t(f"library.status_{status}", language), status)
        self._decision_filter = QComboBox(card)
        self._decision_filter.addItem(t("library.filter_any", language), "")
        for decision in (*DECISIONS, "none"):
            self._decision_filter.addItem(t(f"library.decision_{decision}", language), decision)
        for key, combo in (
            ("library.filter_tag", self._tag_filter),
            ("library.filter_status", self._status_filter),
            ("library.filter_decision", self._decision_filter),
        ):
            # ``activated`` is the user's choice only, not a refill.
            combo.activated.connect(lambda _index: self._reload_if_open())
            form.addRow(t(key, language), combo)
        adapt_form_rows(card, form, threshold=300)
        return card

    def _build_graph_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        self._graph_hint = QLabel(t("library.graph_empty", self._ui_language), tab)
        self._graph_hint.setObjectName("Muted")
        self._graph_hint.setWordWrap(True)
        layout.addWidget(self._graph_hint)
        self._graph = CitationGraph(tab)
        self._graph.node_clicked.connect(self._on_graph_node)
        layout.addWidget(self._graph, stretch=1)
        return tab

    def _build_runs_tab(self) -> QWidget:
        language = self._ui_language
        self._runs_model.setHorizontalHeaderLabels([
            t("library.col_date", language),
            t("library.col_kind", language),
            t("library.col_keywords", language),
            t("library.col_papers", language),
        ])
        self._runs_table = _table(self._runs_model, self)
        self._runs_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        return self._runs_table

    # --- public ------------------------------------------------------------

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        self._split.apply_breakpoint(breakpoint)

    def split(self) -> AdaptiveSplit:
        return self._split

    def set_query_provider(self, provider: Callable[[], Query | None]) -> None:
        """Where a new saved search takes its query from (the Search page's form)."""
        self._query_provider = provider

    def shown_filter(self) -> LibraryFilter:
        return LibraryFilter(
            self._tag_filter.currentData() or "",
            self._status_filter.currentData() or "",
            self._decision_filter.currentData() or "",
        )

    def set_library_path(self, path: str) -> None:
        """Follow the library file named on the Search page."""
        self._path_input.setText(path.strip())

    def library_path(self) -> str:
        return self._path_input.text().strip()

    def snapshot(self) -> LibrarySnapshot | None:
        return self._snapshot

    def show_snapshot(self, snapshot: LibrarySnapshot) -> None:
        """Show an already-read library (a window rebuilt in another language)."""
        self._on_loaded(snapshot)

    def status_text(self) -> str:
        return self._status_label.text()

    def papers_model(self) -> QStandardItemModel:
        return self._papers_model

    def runs_model(self) -> QStandardItemModel:
        return self._runs_model

    def detail_text(self) -> str:
        return self._detail.toPlainText()

    def stat_text(self, key: str) -> str:
        return self._stat_labels[key].text()

    def select_paper(self, row: int) -> None:
        self._papers_table.selectRow(row)

    def save_form(self, store: QSettings) -> None:
        store.setValue(f"{_FORM_GROUP}/path", self._path_input.text())
        store.setValue(f"{_FORM_GROUP}/query", self._query_input.text())

    def restore_form(self, store: QSettings) -> None:
        self._path_input.setText(store.value(f"{_FORM_GROUP}/path", "", type=str))
        self._query_input.setText(store.value(f"{_FORM_GROUP}/query", "", type=str))

    # --- loading -------------------------------------------------------------

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("search.library_dialog_title", self._ui_language),
            self.library_path() or str(Path.cwd()),
            _LIBRARY_FILE_FILTER,
        )
        if path:
            self._path_input.setText(path)
            self._on_open_clicked()

    def _on_open_clicked(self) -> None:
        path = self.library_path()
        if not path:
            self._status_label.setText(t("search.error_no_library", self._ui_language))
            return
        query = self._query_input.text().strip()
        shown = self.shown_filter()
        self._set_working(True)
        worker = BlockingWorker(lambda: load_snapshot(path, query, shown))
        worker.signals.finished.connect(self._on_loaded)
        worker.signals.failed.connect(self._on_failed)
        QThreadPool.globalInstance().start(worker)

    def _reload_if_open(self) -> None:
        if self._snapshot is not None:
            self._on_open_clicked()

    def _set_working(self, working: bool) -> None:
        """Lock everything that would start a second read or write."""
        self.busy_changed.emit(working)
        opened = self._snapshot is not None and not working
        self._open_button.setEnabled(not working)
        self._import_button.setEnabled(not working)
        self._duplicates_button.setEnabled(opened)
        self._send_button.setEnabled(opened and bool(self._snapshot.entries))
        self._saved_tab.set_busy(working)
        self._editor.setEnabled(opened and bool(self.selected_entries()))
        self._refresh_actions(opened)

    def _on_failed(self, err: object) -> None:
        self._set_working(False)
        self._status_label.setText(t("library.error", self._ui_language, error=str(err)))

    def _on_loaded(self, result: object) -> None:
        if not isinstance(result, LibrarySnapshot):  # pragma: no cover - defensive
            self._on_failed(RuntimeError(f"unexpected result {type(result)!r}"))
            return
        selected = {entry.paper_id for entry in self.selected_entries()}
        self._snapshot = result
        self._show_stats(result.stats)
        self._fill_tags(result)
        self._fill_papers(result.entries)
        self._fill_runs(result.runs)
        self._saved_tab.show_searches(result.saved)
        self._fill_graph(result)
        if result.flow is not None:
            self._review_tab.show_flow(result.flow)
        self._detail.clear()
        self._select_ids(selected)
        self._set_working(False)
        self._status_label.setText(
            t(
                "library.status_loaded", self._ui_language,
                shown=len(result.entries), papers=result.stats.papers,
                runs=result.stats.runs, relations=result.stats.relations,
            )
        )

    def _show_stats(self, stats: LibraryStats) -> None:
        years = (
            f"{stats.year_min} – {stats.year_max}"
            if stats.year_min is not None and stats.year_max is not None
            else _NO_VALUE
        )
        values = {
            "papers": str(stats.papers),
            "runs": str(stats.runs),
            "relations": str(stats.relations),
            "years": years,
            "sources": _counts(stats.sources),
            "checks": _counts(stats.verifications),
        }
        for key, value in values.items():
            self._stat_labels[key].setText(value)

    def _fill_papers(self, entries: tuple[LibraryEntry, ...]) -> None:
        self._papers_model.removeRows(0, self._papers_model.rowCount())
        for entry in entries:
            year = entry.paper.year
            title = _item(entry.paper.title)
            title.setData(entry.paper.dedup_key(), Qt.ItemDataRole.UserRole)
            self._papers_model.appendRow([
                title,
                _item(str(year) if year is not None else _NO_VALUE, -1 if year is None else year),
                _item(t(f"library.status_{entry.status}", self._ui_language)),
                _item(", ".join(entry.tags)),
                _item(self._decision_text(entry)),
                _item(", ".join(entry.sources)),
                _item(str(entry.times_seen), entry.times_seen),
                _item(entry.last_seen[:10]),
            ])

    def _fill_runs(self, runs: tuple[LibraryRun, ...]) -> None:
        self._runs_model.removeRows(0, self._runs_model.rowCount())
        for run in runs:
            self._runs_model.appendRow([
                _item(run.started_at[:16].replace("T", " ")),
                _item(run.kind),
                _item(run.keywords),
                _item(str(run.papers), run.papers),
            ])

    # --- selection detail ------------------------------------------------------

    def selected_entries(self) -> list[LibraryEntry]:
        """The papers selected in the table, in its order."""
        if self._snapshot is None:
            return []
        by_key = {entry.paper.dedup_key(): entry for entry in self._snapshot.entries}
        rows = sorted(i.row() for i in self._papers_table.selectionModel().selectedRows())
        keys = (self._papers_model.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in rows)
        return [by_key[key] for key in keys if key in by_key]

    def _on_selection_changed(self) -> None:
        entries = self.selected_entries()
        self._editor.show_entries(entries)
        self._refresh_actions(self._open_button.isEnabled())
        if len(entries) == 1:
            self._detail.setHtml(self._detail_html(entries[0]))
            self._graph.select(entries[0].paper.dedup_key())
        else:
            self._detail.clear()

    def _refresh_actions(self, allowed: bool) -> None:
        count = len(self.selected_entries())
        self._delete_button.setEnabled(allowed and count > 0)
        self._merge_button.setEnabled(allowed and count > 1)

    def _select_ids(self, paper_ids: set[int]) -> None:
        """Select the papers again after a reload replaced the rows."""
        if not paper_ids or self._snapshot is None:
            self._on_selection_changed()
            return
        keys = {e.paper.dedup_key() for e in self._snapshot.entries if e.paper_id in paper_ids}
        self._select_keys(keys)

    def _select_keys(self, keys: set[str]) -> None:
        selection = self._papers_table.selectionModel()
        selection.clearSelection()
        for row in range(self._papers_model.rowCount()):
            item = self._papers_model.item(row, 0)
            if item.data(Qt.ItemDataRole.UserRole) in keys:
                selection.select(
                    item.index(),
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                self._papers_table.scrollTo(item.index())

    def _on_graph_node(self, key: str) -> None:
        self._select_keys({key})

    def _decision_text(self, entry: LibraryEntry) -> str:
        language = self._ui_language
        return ", ".join(
            f"{t(f'library.stage_{s.stage}', language)}: "
            f"{t(f'library.decision_{s.decision}', language)}"
            for s in entry.screening
        )

    def _fill_tags(self, snapshot: LibrarySnapshot) -> None:
        self._tag_filter.clear()
        self._tag_filter.addItem(t("library.filter_any", self._ui_language), "")
        for tag, count in snapshot.tags.items():
            self._tag_filter.addItem(f"{tag} ({count})", tag)
        if snapshot.shown.tag and self._tag_filter.findData(snapshot.shown.tag) < 0:
            # The last paper lost the tag: keep it listed, it is the filter in force.
            self._tag_filter.addItem(snapshot.shown.tag, snapshot.shown.tag)
        for combo, value in (
            (self._tag_filter, snapshot.shown.tag),
            (self._status_filter, snapshot.shown.status),
            (self._decision_filter, snapshot.shown.decision),
        ):
            combo.setCurrentIndex(max(0, combo.findData(value)))

    def _fill_graph(self, snapshot: LibrarySnapshot) -> None:
        nodes = [
            GraphNode(
                entry.paper.dedup_key(), entry.paper.title, entry.paper.year,
                entry.paper.citation_count,
            )
            for entry in snapshot.entries
        ]
        listed = {node.key for node in nodes}
        edges = [
            (relation.citing_key, relation.cited_key)
            for relation in snapshot.relations
            if relation.citing_key in listed and relation.cited_key in listed
        ]
        self._graph_hint.setVisible(not edges)
        self._graph.show_graph(nodes, edges)
        self._graph.fit()

    # --- editing ----------------------------------------------------------------

    def run_edit(
        self,
        edit: Callable[[Library], object],
        done: Callable[[object], str] | None = None,
        *,
        create: bool = False,
    ) -> None:
        """Apply ``edit`` to the open library on a worker and show the new state.

        ``done`` turns the edit's result into the status line. A failing edit
        changes nothing (each is one transaction) and its message is shown.
        """
        path = self.library_path()
        if not path:
            self._status_label.setText(t("search.error_no_library", self._ui_language))
            return
        query = self._query_input.text().strip()
        shown = self.shown_filter()

        def call() -> _EditOutcome:
            with Library(path, create=create) as library:
                value = edit(library)
            return _EditOutcome(value, load_snapshot(path, query, shown), done)

        self._set_working(True)
        worker = BlockingWorker(call)
        worker.signals.finished.connect(self._on_edited)
        worker.signals.failed.connect(self._on_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_edited(self, outcome: object) -> None:
        if not isinstance(outcome, _EditOutcome):  # pragma: no cover - defensive
            return
        self._on_loaded(outcome.snapshot)
        self._status_label.setText(
            outcome.done(outcome.value)
            if outcome.done
            else t("library.status_saved", self._ui_language)
        )

    def apply_edit(self, request: object) -> None:
        """Carry out an :class:`EditRequest` of the editor."""
        if isinstance(request, EditRequest):
            self.run_edit(request.apply)

    def _on_delete(self) -> None:
        ids = [entry.paper_id for entry in self.selected_entries()]
        if ids and self._confirmed(t("library.confirm_delete", self._ui_language, count=len(ids))):
            self.run_edit(
                lambda library: library.delete(ids),
                lambda count: t("library.status_deleted", self._ui_language, count=count),
            )

    def _on_merge(self) -> None:
        entries = self.selected_entries()
        if len(entries) < 2:
            return
        question = t(
            "library.confirm_merge", self._ui_language,
            count=len(entries), title=entries[0].paper.title,
        )
        if self._confirmed(question):
            self.merge([entry.paper_id for entry in entries])

    def merge(self, ids: object) -> None:
        """Fold the papers ``ids`` into the first one."""
        survivor, *others = list(ids)  # type: ignore[call-overload]
        self.run_edit(lambda library: library.merge(survivor, others))

    def _confirmed(self, question: str) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(question)
        # Plain text: the question quotes a title, which comes from a remote API.
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _on_import(self) -> None:
        file, _ = QFileDialog.getOpenFileName(
            self, t("library.action_import", self._ui_language), "", _BIBLIOGRAPHY_FILTER
        )
        if file:
            self.import_bibliography(file)

    def import_bibliography(self, file: str) -> None:
        """Add the papers of a ``.bib`` or ``.ris`` file, creating the library if needed."""

        def edit(library: Library) -> tuple[int, int, int]:
            result = read_bibliography(file)
            report = library.add_papers(
                result.papers, keywords=Path(file).name, kind="import"
            )
            return report.added, report.merged, len(result.skipped)

        def done(value: object) -> str:
            added, merged, skipped = value  # type: ignore[misc]
            return t(
                "library.status_imported", self._ui_language,
                added=added, merged=merged, skipped=skipped,
            )

        self.run_edit(edit, done, create=True)

    def _on_duplicates(self) -> None:
        self.run_edit(lambda library: library.duplicate_candidates(), self._show_duplicates)

    def _show_duplicates(self, groups: object) -> str:
        entries = {e.paper_id: e for e in (self._snapshot.entries if self._snapshot else ())}
        # A group is shown when the filter leaves at least two of it.
        shown = [
            [entries[i] for i in group if i in entries] for group in groups  # type: ignore[attr-defined]
        ]
        shown = [group for group in shown if len(group) > 1]
        self._duplicates = DuplicatesDialog(shown, self._ui_language, self)
        self._duplicates.merge_requested.connect(self.merge)
        self._duplicates.open()
        return "" if shown else t("library.duplicates_none", self._ui_language)

    def duplicates_dialog(self) -> DuplicatesDialog:
        return self._duplicates

    def _on_save_search(self, name: str) -> None:
        query = self._query_provider()
        if query is None:
            self._status_label.setText(t("search.error_empty_query", self._ui_language))
            return
        self.run_edit(lambda library: library.save_search(name, query), create=True)

    def _on_run_saved(self, name: str) -> None:
        """Run a saved search (network) and show the library with what it found."""
        path = self.library_path()
        query = self._query_input.text().strip()
        shown = self.shown_filter()

        async def call() -> _EditOutcome:
            from thesisagents.fetchers.http import shutdown_clients

            try:
                with Library(path, create=False) as library:
                    outcome = await run_saved_search(library, name)
            finally:
                await shutdown_clients()
            return _EditOutcome(outcome, load_snapshot(path, query, shown), self._saved_result)

        self._set_working(True)
        worker = AsyncWorker(call)
        worker.signals.finished.connect(self._on_edited)
        worker.signals.failed.connect(self._on_failed)
        QThreadPool.globalInstance().start(worker)

    def _saved_result(self, value: object) -> str:
        assert isinstance(value, SavedSearchOutcome)  # noqa: S101 # nosec B101  # set by call()
        # What is new is what the user came for, so it is selected.
        self._select_keys({key for p in value.new_papers for key in p.identity_keys()})
        self._tabs.setCurrentIndex(0)
        return t(
            "library.saved_result", self._ui_language,
            new=len(value.new_papers), found=len(value.collection.papers),
        )

    def _on_save_diagram(self) -> None:
        file, _ = QFileDialog.getSaveFileName(
            self, t("library.review_save", self._ui_language), "prisma.svg", "SVG (*.svg)"
        )
        if file:
            self.save_diagram(file)

    def save_diagram(self, file: str) -> None:
        """Write the PRISMA diagram, worded in the interface language."""
        if self._snapshot is None or self._snapshot.flow is None:
            return
        try:
            Path(file).write_text(
                prisma_svg(self._snapshot.flow, prisma_labels(self._ui_language)),
                encoding="utf-8",
            )
        except OSError as err:
            self._status_label.setText(t("library.error", self._ui_language, error=str(err)))
            return
        self._status_label.setText(t("library.status_saved", self._ui_language))

    # --- more accessors used by tests ---------------------------------------------

    def editor(self) -> PaperEditor:
        return self._editor

    def graph(self) -> CitationGraph:
        return self._graph

    def saved_tab(self) -> SavedSearchesTab:
        return self._saved_tab

    def review_tab(self) -> ReviewTab:
        return self._review_tab

    def filter_combo(self, name: str) -> QComboBox:
        """``tag`` / ``status`` / ``decision``."""
        return {
            "tag": self._tag_filter, "status": self._status_filter,
            "decision": self._decision_filter,
        }[name]

    def action_button(self, name: str) -> QPushButton:
        """``delete`` / ``merge`` / ``import`` / ``duplicates`` / ``send``."""
        return {
            "delete": self._delete_button, "merge": self._merge_button,
            "import": self._import_button, "duplicates": self._duplicates_button,
            "send": self._send_button,
        }[name]

    def _detail_html(self, entry: LibraryEntry) -> str:
        """The selected paper's links and verdicts. Every value is escaped:
        titles and identifiers come from remote APIs."""
        assert self._snapshot is not None  # noqa: S101 # nosec B101  # only called with a snapshot
        language = self._ui_language
        key = entry.paper.dedup_key()
        titles = self._snapshot.paper_titles()
        cites: list[str] = []
        cited_by: list[str] = []
        for relation in self._snapshot.relations:
            if relation.citing_key == key and relation.cited_key != key:
                cites.append(titles.get(relation.cited_key, relation.cited_key))
            elif relation.cited_key == key:
                cited_by.append(titles.get(relation.citing_key, relation.citing_key))
        verdicts = [
            f"{v.kind.upper()} {v.value}: {v.status} ({v.checked_at})"
            for v in self._snapshot.verdicts.get(key, ())
        ]
        parts = [f"<h3>{html.escape(entry.paper.title)}</h3>"]
        if entry.paper.authors:
            parts.append(f"<p>{html.escape(', '.join(entry.paper.authors))}</p>")
        for label_key, items in (
            ("library.detail_cites", sorted(set(cites))),
            ("library.detail_cited_by", sorted(set(cited_by))),
            ("library.detail_checks", verdicts),
        ):
            parts.append(f"<p><b>{html.escape(t(label_key, language, count=len(items)))}</b></p>")
            if items:
                rows = "".join(f"<li>{html.escape(item)}</li>" for item in items)
                parts.append(f"<ul>{rows}</ul>")
            else:
                parts.append(f"<p>{html.escape(t('library.detail_none', language))}</p>")
        return "".join(parts)

    # --- hand-off ------------------------------------------------------------------

    def _on_send_clicked(self) -> None:
        if self._snapshot is None or not self._snapshot.collection.papers:
            return
        collection = self._snapshot.collection
        self.collection_ready.emit(collection)
        self._status_label.setText(
            t("library.status_sent", self._ui_language, count=len(collection.papers))
        )


def _item(text: str, sort: object | None = None) -> QStandardItem:
    """A read-only cell showing ``text`` and sorting by ``sort`` (the text by default)."""
    item = QStandardItem(text)
    item.setData(text.casefold() if sort is None else sort, _SORT_ROLE)
    return item


def _table(model: QStandardItemModel, parent: QWidget) -> QTableView:
    model.setSortRole(_SORT_ROLE)
    table = QTableView(parent)
    table.setModel(model)
    table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setSortingEnabled(True)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
    return table


def _counts(counts: Mapping[str, int]) -> str:
    """``{"arxiv": 12, "openalex": 30}`` → ``"arxiv 12, openalex 30"``."""
    return ", ".join(f"{name} {count}" for name, count in counts.items()) or _NO_VALUE

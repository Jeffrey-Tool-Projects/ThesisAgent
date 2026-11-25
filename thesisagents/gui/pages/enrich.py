"""Enrich tab.

Takes the PaperCollection produced by the Search tab and walks every
paper through ``intelligence.fetch_and_extract`` (download + PDF text
extraction) + ``intelligence.summarise_paper`` (Anthropic call). The
result is a NEW PaperCollection whose ``papers[*].summary`` carries
the rich-tier fields so the Deck tab can render thesis-style decks.

Behaviour rules:

* The Enrich button is disabled until SearchPage emits
  ``collection_ready`` (or a collection is set programmatically by a
  test).
* The Anthropic API key requirement is checked at button-click time,
  not at page-construction time, so opening the tab without a key
  doesn't crash. The error directs the user to the Settings tab.
* Enrichment runs one paper at a time on a worker thread; the UI
  stays responsive and shows per-paper status (pending → ok / failed).
  Sequential (not parallel) because each Anthropic call already takes
  ~10 s and parallelism would just stress the user's rate limit.
* Failed papers don't kill the whole run — they keep the original
  un-enriched ``Paper`` in the output collection so downstream Deck
  rendering still works (falls back to lightweight tier per-paper).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.exceptions import ConfigError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary
from thesisagents.exporters.i18n import SUPPORTED_LANGUAGES as DECK_LANGUAGES
from thesisagents.gui.handoff import HandoffError, read_handoff, write_handoff
from thesisagents.gui.i18n import LANGUAGE_DISPLAY_NAMES, t
from thesisagents.gui.widgets.responsive import (
    AdaptiveSplit,
    Breakpoint,
    adapt_form_rows,
    make_card,
)
from thesisagents.gui.widgets.summary_editor import SummaryEditor
from thesisagents.gui.workers import AsyncWorker
from thesisagents.intelligence import providers

#: QSettings group the form is saved under when the window closes.
_FORM_GROUP = "form/enrich"
#: i18n key of the status shown when an action needs papers and the page
#: has none yet (the export, import and enrich buttons all check it).
_NO_COLLECTION_KEY = "enrich.error_no_collection"


class EnrichPage(QWidget):
    """Enrich the search collection with PDF-derived rich summaries."""

    # Re-emitted to downstream tabs (Deck) whenever an enrichment run
    # finishes — even partially — so they can render whatever survived.
    collection_ready = Signal(object)
    #: ``True`` when an enrichment run starts, ``False`` when its last paper
    #: is done. Drives the main window's progress indicator.
    busy_changed = Signal(bool)

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._collection: PaperCollection | None = None
        self._enriched_papers: list[Paper] = []
        self._pending_index: int = 0
        self._running = False
        self._stop_requested = False
        self._worker: AsyncWorker | None = None
        # A collection that arrived while a run was going (a new search, or
        # ticks changed on the Search page). Applied when the run ends:
        # swapping it in mid-run would point the run at the wrong rows.
        self._held: tuple[object] | None = None
        self._table_model = QStandardItemModel(0, 3, self)
        self._table_model.setHorizontalHeaderLabels([
            t("enrich.column_title", ui_language),
            t("enrich.column_pdf", ui_language),
            t("enrich.column_status", ui_language),
        ])
        self._build_ui()

    def _build_ui(self) -> None:
        """Settings card and Enrich button beside / above the per-paper table."""
        language = self._ui_language
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 6, 0)
        settings_card, settings_layout = make_card(
            t("enrich.settings_group", language), controls
        )
        form = QFormLayout()
        settings_layout.addLayout(form)

        self._language_combo = QComboBox(self)
        for code in DECK_LANGUAGES:
            display = LANGUAGE_DISPLAY_NAMES.get(code, code)
            self._language_combo.addItem(display, code)
        form.addRow(t("enrich.language_label", language), self._language_combo)

        self._model_input = QLineEdit(self)
        self.refresh_model()
        form.addRow(t("enrich.model_label", language), self._model_input)
        adapt_form_rows(settings_card, form)
        controls_layout.addWidget(settings_card)
        controls_layout.addWidget(self._build_agent_card(controls))
        controls_layout.addStretch(1)

        footer = QWidget(self)
        button_row = QHBoxLayout(footer)
        button_row.setContentsMargins(0, 0, 6, 0)
        self._enrich_button = QPushButton(t("enrich.enrich_button", language), self)
        self._enrich_button.setProperty("primary", True)
        self._enrich_button.setEnabled(False)
        self._enrich_button.clicked.connect(self._on_enrich_clicked)
        self._cancel_button = QPushButton(t("action.cancel", language), self)
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        button_row.addWidget(self._enrich_button, stretch=1)
        button_row.addWidget(self._cancel_button)

        results = QWidget(self)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(6, 0, 0, 0)
        self._table = QTableView(self)
        self._table.setModel(self._table_model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        results_layout.addWidget(self._table, stretch=1)
        edit_row = QHBoxLayout()
        edit_row.addStretch(1)
        self._edit_button = QPushButton(t("summary.button", language), self)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit_summary)
        edit_row.addWidget(self._edit_button)
        results_layout.addLayout(edit_row)
        self._table.doubleClicked.connect(lambda _index: self._on_edit_summary())
        self._table.selectionModel().selectionChanged.connect(
            lambda *_: self._refresh_edit_button()
        )

        self._status_label = QLabel(t("enrich.status_no_collection", language), self)
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        results_layout.addWidget(self._status_label)

        self._split = AdaptiveSplit(controls, results, footer=footer, parent=self)
        outer.addWidget(self._split)

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Re-arrange for the window size class (called by the main window)."""
        self._split.apply_breakpoint(breakpoint)

    def split(self) -> AdaptiveSplit:
        return self._split

    # --- public API -----------------------------------------------------

    def set_collection(self, collection: object) -> None:
        """Receive the latest collection from SearchPage.

        Called from a Qt signal, so the parameter is typed ``object``.
        ``None`` clears the page (used by tests to simulate the empty
        initial state). While a run is going the collection is held and
        applied when the run ends.
        """
        if self._running:
            self._held = (collection,)
            return
        if collection is None or not isinstance(collection, PaperCollection):
            self._collection = None
            self._enriched_papers = []
            self._table_model.removeRows(0, self._table_model.rowCount())
            self._enrich_button.setEnabled(False)
            self._set_agent_buttons(False)
            self._status_label.setText(
                t("enrich.status_no_collection", self._ui_language),
            )
            return
        self._collection = collection
        self._enriched_papers = []
        self._populate_table(collection.papers)
        self._enrich_button.setEnabled(bool(collection.papers))
        self._set_agent_buttons(bool(collection.papers))
        self._status_label.setText(
            t(
                "enrich.status_ready",
                self._ui_language,
                count=len(collection.papers),
            ),
        )

    def collection(self) -> PaperCollection | None:
        """Most recent enriched collection — or the input collection
        when no enrichment has run yet. Used by tests + the Deck tab."""
        if self._enriched_papers:
            assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation  # invariant
            return replace(  # NOSONAR dataclasses.replace returns the same dataclass type
                self._collection, papers=tuple(self._enriched_papers)
            )
        return self._collection

    def status_text(self) -> str:
        return self._status_label.text()

    def table_model(self) -> QStandardItemModel:
        return self._table_model

    def is_running(self) -> bool:
        return self._running

    # --- hand-off to an LLM agent (progress #27) ---------------------------

    def _build_agent_card(self, parent: QWidget) -> QWidget:
        """The no-API-key path: write the papers for an agent, read its summaries."""
        language = self._ui_language
        card, layout = make_card(t("enrich.card_agent", language), parent)
        hint = QLabel(t("enrich.agent_hint", language), card)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self._agent_export_button = QPushButton(t("enrich.agent_export_button", language), self)
        self._agent_export_button.clicked.connect(self._on_agent_export_clicked)
        self._agent_import_button = QPushButton(t("enrich.agent_import_button", language), self)
        self._agent_import_button.clicked.connect(self._on_agent_import_clicked)
        row.addWidget(self._agent_export_button)
        row.addWidget(self._agent_import_button)
        row.addStretch(1)
        layout.addLayout(row)
        self._set_agent_buttons(False)
        return card

    def _set_agent_buttons(self, enabled: bool) -> None:
        self._agent_export_button.setEnabled(enabled)
        self._agent_import_button.setEnabled(enabled)

    def _on_agent_export_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("enrich.agent_export_button", self._ui_language),
            str(Path.cwd() / "handoff.json"), "JSON (*.json)",
        )
        if path:
            self.export_for_agent(path)

    def export_for_agent(self, path: str) -> None:
        """Write the current papers (enriched ones keep their summary) for an agent."""
        collection = self.collection()
        if collection is None or not collection.papers:
            self._status_label.setText(t(_NO_COLLECTION_KEY, self._ui_language))
            return
        language = self._language_combo.currentData() or "en"
        try:
            count = write_handoff(collection, path, language=language)
        except OSError as err:
            self._status_label.setText(t("enrich.agent_error", self._ui_language, error=str(err)))
            return
        self._status_label.setText(
            t("enrich.agent_exported", self._ui_language, count=count, path=path)
        )

    def _on_agent_import_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("enrich.agent_import_button", self._ui_language),
            str(Path.cwd()), "JSON (*.json);;All files (*)",
        )
        if path:
            self.import_from_agent(path)

    def import_from_agent(self, path: str) -> None:
        """Attach an agent's summaries and send the result on to the Deck page."""
        collection = self.collection()
        if collection is None or not collection.papers:
            self._status_label.setText(t(_NO_COLLECTION_KEY, self._ui_language))
            return
        try:
            result = read_handoff(path, collection)
        except (HandoffError, OSError) as err:
            self._status_label.setText(t("enrich.agent_error", self._ui_language, error=str(err)))
            return
        self._collection = result.collection
        self._enriched_papers = []
        self._populate_table(result.collection.papers)
        for row, paper in enumerate(result.collection.papers):
            if paper.summary is not None:
                self._set_row_status(row, "enrich.row_done")
        self._status_label.setText(
            t(
                "enrich.agent_imported", self._ui_language,
                count=result.imported, unmatched=result.unmatched,
            )
        )
        self.collection_ready.emit(result.collection)

    def save_form(self, store: QSettings) -> None:
        """Write the summary language and model to ``store``."""
        store.setValue(f"{_FORM_GROUP}/language", self._language_combo.currentData() or "en")
        store.setValue(f"{_FORM_GROUP}/model", self._model_input.text())

    def restore_form(self, store: QSettings) -> None:
        """Fill the fields from ``store``; missing values keep the defaults."""
        language = store.value(f"{_FORM_GROUP}/language", "", type=str)
        index = self._language_combo.findData(language)
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        self._model_input.setText(store.value(f"{_FORM_GROUP}/model", "", type=str))

    # --- internals ------------------------------------------------------

    def _populate_table(self, papers: tuple[Paper, ...]) -> None:
        self._table_model.removeRows(0, self._table_model.rowCount())
        for paper in papers:
            title_item = QStandardItem(_truncate(paper.title, 80))
            readable = paper.pdf_url or _local_text(paper)
            pdf_item = QStandardItem("✓" if readable else "—")
            status_item = QStandardItem(
                t("enrich.row_pending", self._ui_language),
            )
            self._table_model.appendRow([title_item, pdf_item, status_item])

    def _set_row_status(self, row: int, message_key: str, **fmt: object) -> None:
        item = self._table_model.item(row, 2)
        if item is None:
            return
        item.setText(t(message_key, self._ui_language, **fmt))

    def _on_enrich_clicked(self) -> None:
        if self._collection is None or not self._collection.papers:
            self._status_label.setText(
                t(_NO_COLLECTION_KEY, self._ui_language),
            )
            return
        try:
            reason = providers.problem(self._model_settings())
        except ConfigError as err:
            reason = str(err)
        if reason:
            self._status_label.setText(
                t("enrich.error_no_key", self._ui_language, reason=reason),
            )
            return
        self._enriched_papers = []
        self._pending_index = 0
        self._running = True
        self._stop_requested = False
        self._enrich_button.setEnabled(False)
        self._set_agent_buttons(False)
        self._cancel_button.setVisible(True)
        self._cancel_button.setEnabled(True)
        self._refresh_edit_button()
        self.busy_changed.emit(True)
        self._status_label.setText(
            t(
                "enrich.status_running",
                self._ui_language,
                done=0,
                total=len(self._collection.papers),
            ),
        )
        self._enrich_next()

    def _selected_row(self) -> int:
        rows = self._table.selectionModel().selectedRows()
        return rows[0].row() if len(rows) == 1 else -1

    def _refresh_edit_button(self) -> None:
        self._edit_button.setEnabled(self._selected_row() >= 0 and not self._running)

    def _on_edit_summary(self) -> None:
        """Edit the selected paper's summary by hand, model or no model."""
        collection = self.collection()
        row = self._selected_row()
        if self._running or collection is None or not 0 <= row < len(collection.papers):
            return
        self._summary_editor = SummaryEditor(collection.papers[row], self._ui_language, self)
        self._summary_editor.saved.connect(lambda paper: self._on_summary_edited(row, paper))
        self._summary_editor.open()

    def summary_editor(self) -> SummaryEditor:
        return self._summary_editor

    def _on_summary_edited(self, row: int, paper: object) -> None:
        collection = self.collection()
        if not isinstance(paper, Paper) or collection is None:
            return
        papers = list(collection.papers)
        row = _row_of(papers, paper, row)
        if row < 0:
            # A search that ended while the editor was open replaced the list.
            self._status_label.setText(t("summary.paper_gone", self._ui_language))
            return
        papers[row] = paper
        self._collection = replace(  # NOSONAR dataclasses.replace returns the same dataclass type
            collection, papers=tuple(papers)
        )
        self._enriched_papers = []
        self._set_row_status(
            row, "enrich.row_done" if paper.summary is not None else "enrich.row_pending"
        )
        self._status_label.setText(t("library.status_saved", self._ui_language))
        self.collection_ready.emit(self._collection)

    def _model_settings(self) -> providers.LlmSettings:
        """The model this run would use: the one typed here, else Settings'."""
        return providers.resolve(model=self._model_input.text().strip() or None)

    def refresh_model(self) -> None:
        """Show the model now chosen in Settings.

        A misspelt ``THESISAGENTS_LLM_PROVIDER`` is reported when a run starts.
        Here it would stop the whole window from opening.
        """
        try:
            hint = providers.resolve().describes
        except ConfigError:
            hint = ""
        self._model_input.setPlaceholderText(hint)

    def _enrich_next(self) -> None:
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        idx = self._pending_index
        if self._stop_requested:
            self._finish_stopped()
            return
        if idx >= len(self._collection.papers):
            self._on_run_finished()
            return
        paper = self._collection.papers[idx]
        text = _local_text(paper)
        if not paper.pdf_url and not text:
            # No PDF URL means we can't reach the body text: keep the
            # original paper, mark the row, move on.
            self._enriched_papers.append(paper)
            self._set_row_status(idx, "enrich.row_skipped")
            self._pending_index += 1
            self._update_running_status()
            self._enrich_next()
            return
        language = self._language_combo.currentData() or "en"
        model = self._model_input.text().strip() or None

        async def coro() -> object:
            # Lazy import — the intelligence extra is optional.
            from thesisagents.intelligence.pdf import ExtractedPdf, fetch_and_extract
            from thesisagents.intelligence.summarise import summarise_paper

            if text:
                pages = int((paper.raw or {}).get("page_count") or 1)
                extracted = ExtractedPdf(paper.url, pages, len(text), text)
            else:
                extracted = await fetch_and_extract(paper.pdf_url)
            return summarise_paper(
                paper, extracted, language=language, model=model,
            )

        worker = AsyncWorker(coro)
        worker.signals.finished.connect(self._on_paper_finished)
        worker.signals.failed.connect(self._on_paper_failed)
        worker.signals.cancelled.connect(self._on_paper_cancelled)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _on_cancel_clicked(self) -> None:
        """Stop after the current paper (or during its PDF download)."""
        self._stop_requested = True
        self._cancel_button.setEnabled(False)
        if self._worker is not None:
            self._worker.cancel()

    def _on_paper_cancelled(self) -> None:
        """The current paper was stopped: keep its search record, then stop."""
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        self._finish_stopped()

    def _finish_stopped(self) -> None:
        """End a cancelled run: papers not reached keep their search record.

        The output still has every paper, so the Deck page renders the
        unreached ones in the lightweight tier, as it does for a failed one.
        """
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        papers = self._collection.papers
        for idx in range(self._pending_index, len(papers)):
            self._enriched_papers.append(papers[idx])
            self._set_row_status(idx, "enrich.row_cancelled")
        done = self._pending_index
        self._pending_index = len(papers)
        self._on_run_finished(stopped_after=done)

    def _on_paper_finished(self, summary: object) -> None:
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        if isinstance(summary, PaperSummary) and summary.is_empty():
            # As in the CLI: an answer with nothing in it is no summary, and it
            # must not replace one the paper already has.
            self._on_paper_failed(ValueError("the model returned an empty summary"))
            return
        idx = self._pending_index
        paper = self._collection.papers[idx]
        # Attach the new summary, keeping every other field.
        enriched = replace(paper, summary=summary)  # type: ignore[arg-type]
        self._enriched_papers.append(enriched)
        self._set_row_status(idx, "enrich.row_done")
        self._pending_index += 1
        self._update_running_status()
        self._enrich_next()

    def _on_paper_failed(self, err: object) -> None:
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        idx = self._pending_index
        paper = self._collection.papers[idx]
        # Failure → keep the original (un-enriched) paper so the
        # downstream collection still has every entry.
        self._enriched_papers.append(paper)
        self._set_row_status(
            idx, "enrich.row_failed", error=str(err)[:60],
        )
        self._pending_index += 1
        self._update_running_status()
        self._enrich_next()

    def _update_running_status(self) -> None:
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        total = len(self._collection.papers)
        done = self._pending_index
        self._status_label.setText(
            t("enrich.status_running", self._ui_language, done=done, total=total),
        )

    def _on_run_finished(self, stopped_after: int | None = None) -> None:
        assert self._collection is not None  # noqa: S101 # nosec B101  # state-machine invariant, not runtime validation
        total = len(self._collection.papers)
        successes = sum(
            1 for p in self._enriched_papers if p.summary is not None
        )
        self._running = False
        self._worker = None
        self._refresh_edit_button()
        self._enrich_button.setEnabled(True)
        self._set_agent_buttons(True)
        self._cancel_button.setVisible(False)
        self.busy_changed.emit(False)
        if stopped_after is None:
            message = t("enrich.status_done", self._ui_language, successes=successes, total=total)
        else:
            message = t(
                "enrich.status_cancelled", self._ui_language,
                done=stopped_after, total=total,
            )
        self._status_label.setText(message)
        result = self.collection()
        if result is not None:
            self.collection_ready.emit(result)
        if self._held is not None:
            (held,) = self._held
            self._held = None
            self.set_collection(held)


def _local_text(paper: Paper) -> str:
    """The text of a PDF read from disk, which has no address to fetch.

    Without it every paper of *Read local PDFs* was skipped here, although
    the CLI's ``--pdf --enrich`` summarises the same files.
    """
    return str((paper.raw or {}).get("extracted_text") or "")


def _row_of(papers: list[Paper], paper: Paper, row: int) -> int:
    """Where ``paper`` stands now: at ``row``, elsewhere, or nowhere (-1).

    The boundary this guards: a dialog that outlives the list it was opened
    from. Writing to the remembered row replaced another paper.
    """
    key = paper.dedup_key()
    if 0 <= row < len(papers) and papers[row].dedup_key() == key:
        return row
    return next((i for i, known in enumerate(papers) if known.dedup_key() == key), -1)


def _truncate(text: str, limit: int) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"

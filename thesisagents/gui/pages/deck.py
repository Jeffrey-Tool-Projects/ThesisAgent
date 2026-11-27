"""Deck tab.

Granular export controls for a PaperCollection — supplements the Search
tab's one-button Export by exposing every ExportOptions knob:

* Output directory + filename stem
* Per-format checkboxes (pptx / xlsx / bib / md / json / ris / csv / csl)
* Deck language (independent of UI language)
* Max-slides cap (per-paper)
* Include-abstract toggle
* Dark-mode toggle
* Verify-identifiers toggle (the export preflight, on by default)

The page accepts either the raw collection from SearchPage or the
enriched one from EnrichPage. ``set_collection`` is the only entry
point — the page does not call the search pipeline itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from thesisagents.core.exceptions import ConfigError, ExportError
from thesisagents.core.models import ExportOptions, PaperCollection
from thesisagents.exporters import export_collection
from thesisagents.exporters.i18n import SUPPORTED_LANGUAGES as DECK_LANGUAGES
from thesisagents.exporters.review import DeckReview, review_deck
from thesisagents.exporters.review import format_report as format_review
from thesisagents.exporters.template import TemplateValidationReport, validate_template
from thesisagents.exporters.template import format_report as format_template_report
from thesisagents.gui.enrichment import cli_provider_choices, prepare_cli_deck
from thesisagents.gui.i18n import LANGUAGE_DISPLAY_NAMES, t
from thesisagents.gui.pages.settings import saved_provider_settings, saved_vpn_access
from thesisagents.gui.pdf_stage import PdfStageReport, run_pdf_stage
from thesisagents.gui.widgets.deck_editor import DeckEditor
from thesisagents.gui.widgets.report_dialog import ReportDialog
from thesisagents.gui.widgets.responsive import (
    AdaptiveSplit,
    Breakpoint,
    ReflowGrid,
    adapt_form_rows,
    make_card,
)
from thesisagents.gui.workers import BlockingWorker
from thesisagents.library import Library

# Match thesisagents.exporters.__init__.SUPPORTED_FORMATS ordering.
_FORMAT_CHOICES: tuple[tuple[str, str], ...] = (
    ("pptx", "deck.format_pptx"),
    ("xlsx", "deck.format_xlsx"),
    ("bib", "deck.format_bib"),
    ("md", "deck.format_md"),
    ("json", "deck.format_json"),
    ("ris", "deck.format_ris"),
    ("csv", "deck.format_csv"),
    ("csl", "deck.format_csl"),
    ("docx", "deck.format_docx"),
    ("tex", "deck.format_tex"),
)
_DEFAULT_FORMATS: frozenset[str] = frozenset({"pptx", "xlsx", "bib"})
_DEFAULT_MAX_SLIDES = 25
#: QSettings group the form is saved under when the window closes.
_FORM_GROUP = "form/deck"


def _stored(store: QSettings, key: str, kind: type) -> object | None:
    """Return the saved form value ``key`` as ``kind``, or ``None`` when unsaved.

    Guards the first run: ``QSettings.value`` returns a default for a key
    that was never written, which would overwrite a field's built-in default.
    Checking ``contains`` first lets the caller tell "never saved" apart.

    Example: ``_stored(store, "max_slides", int)`` returns ``25`` after a save
    of 25, and ``None`` on a fresh profile.
    """
    full = f"{_FORM_GROUP}/{key}"
    return store.value(full, type=kind) if store.contains(full) else None


@dataclass(frozen=True)
class _ExportOutcome:
    """What the export worker hands back: the files written per format, and
    the PDF stage's counts when **Download the PDFs** was ticked."""

    written: dict[str, Path]
    pdfs: PdfStageReport | None = None


class DeckPage(QWidget):
    """Granular export controls for the active collection."""

    #: ``True`` when an export starts on a worker thread, ``False`` when it
    #: ends either way. Drives the main window's progress indicator.
    busy_changed = Signal(bool)
    saved_search_requested = Signal()

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._collection: PaperCollection | None = None
        self._collection_is_enriched: bool = False
        self._exporting = False
        self._last_written_dir: Path | None = None
        self._last_deck: Path | None = None
        self._last_report: ReportDialog | None = None
        self._library_path = ""
        self._files_model = QStandardItemModel(0, 2, self)
        self._files_model.setHorizontalHeaderLabels([
            t("deck.column_format", ui_language),
            t("deck.column_path", ui_language),
        ])
        self._build_ui()

    def _build_ui(self) -> None:
        """Output, format and option cards beside / above the written files."""
        language = self._ui_language
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 6, 0)
        controls_layout.setSpacing(12)

        # Output dir + filename + deck language
        output_card, output_layout = make_card(t("deck.output_group", language), controls)
        output_form = QFormLayout()
        output_layout.addLayout(output_form)

        dir_row = QWidget(self)
        dir_layout = QHBoxLayout(dir_row)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        self._out_dir_input = QLineEdit(self)
        self._out_dir_input.setText(str(Path.cwd() / "exports"))
        browse = QPushButton(t("deck.browse_button", language), self)
        browse.clicked.connect(self._on_browse_out_dir)
        dir_layout.addWidget(self._out_dir_input, stretch=1)
        dir_layout.addWidget(browse)
        output_form.addRow(t("deck.out_dir_label", language), dir_row)

        self._filename_stem_input = QLineEdit(self)
        self._filename_stem_input.setPlaceholderText(
            t("deck.filename_stem_placeholder", language),
        )
        output_form.addRow(t("deck.filename_stem_label", language), self._filename_stem_input)

        self._language_combo = QComboBox(self)
        for code in DECK_LANGUAGES:
            display = LANGUAGE_DISPLAY_NAMES.get(code, code)
            self._language_combo.addItem(display, code)
        output_form.addRow(t("deck.language_label", language), self._language_combo)
        self._cli_provider = QComboBox(self)
        self._cli_provider.addItem(t("deck.existing_summaries", language), "")
        for label, name in cli_provider_choices(language):
            self._cli_provider.addItem(label, name)
        output_form.addRow(t("deck.summary_source", language), self._cli_provider)
        adapt_form_rows(output_card, output_form)
        controls_layout.addWidget(output_card)

        # Format check boxes, re-flowed to the pane width
        format_card, format_layout = make_card(t("deck.format_group", language), controls)
        self._format_checks: dict[str, QCheckBox] = {}
        for fmt, label_key in _FORMAT_CHOICES:
            chk = QCheckBox(t(label_key, language))
            chk.setChecked(fmt in _DEFAULT_FORMATS)
            self._format_checks[fmt] = chk
        self._format_grid = ReflowGrid(list(self._format_checks.values()), parent=format_card)
        format_layout.addWidget(self._format_grid)
        controls_layout.addWidget(format_card)

        # Options
        options_card, options_layout = make_card(t("deck.options_group", language), controls)
        options_form = QFormLayout()
        options_layout.addLayout(options_form)
        self._max_slides_spin = QSpinBox(self)
        self._max_slides_spin.setRange(0, 200)
        self._max_slides_spin.setValue(_DEFAULT_MAX_SLIDES)
        self._max_slides_spin.setSpecialValueText(t("deck.unlimited", language))
        options_form.addRow(t("deck.max_slides_label", language), self._max_slides_spin)
        self._include_abstract_check = QCheckBox(t("deck.include_abstract_label", language), self)
        self._include_abstract_check.setChecked(True)
        options_form.addRow(self._include_abstract_check)
        # Default is the light navy-band deck; this checkbox is the
        # opt-IN toggle for dark mode (OLED / low-light venues).
        self._dark_mode_check = QCheckBox(t("deck.dark_mode_label", language), self)
        self._dark_mode_check.setChecked(False)
        options_form.addRow(self._dark_mode_check)
        # Export preflight: on by default. Unchecking it is the GUI form of
        # the CLI's --no-verify-identifiers, for a machine with no network.
        self._verify_identifiers_check = QCheckBox(
            t("deck.verify_identifiers_label", language), self,
        )
        self._verify_identifiers_check.setChecked(True)
        options_form.addRow(self._verify_identifiers_check)
        # The PDF download stage (the CLI's --export pdf). IEEE PDFs need the
        # institutional / VPN access declared in Settings, see gui/pdf_stage.py.
        self._download_pdfs_check = QCheckBox(t("deck.download_pdfs_label", language), self)
        self._download_pdfs_check.setChecked(False)
        options_form.addRow(self._download_pdfs_check)
        # Deck template: the GUI form of --pptx-template and
        # --pptx-template-config. Empty means the built-in design.
        self._template_input = self._file_row(
            options_form, "deck.template_label", "deck.template_placeholder",
            "deck.template_dialog_title", "PowerPoint (*.pptx *.potx);;All files (*)",
        )
        self._template_config_input = self._file_row(
            options_form, "deck.template_config_label", "deck.template_config_placeholder",
            "deck.template_config_dialog_title", "Config (*.toml *.json);;All files (*)",
        )
        # The Word document the literature review draft is written into.
        self._docx_template_input = self._file_row(
            options_form, "deck.docx_template_label", "deck.docx_template_placeholder",
            "deck.docx_template_label", "Word (*.docx);;All files (*)",
        )
        check_row = QHBoxLayout()
        self._check_template_button = QPushButton(t("deck.check_template_button", language), self)
        self._check_template_button.clicked.connect(self._on_check_template_clicked)
        check_row.addWidget(self._check_template_button)
        check_row.addStretch(1)
        options_form.addRow(check_row)
        adapt_form_rows(options_card, options_form)
        controls_layout.addWidget(options_card)
        controls_layout.addStretch(1)

        # Action row, pinned below the cards
        footer = QWidget(self)
        button_row = QHBoxLayout(footer)
        button_row.setContentsMargins(0, 0, 6, 0)
        self._export_button = QPushButton(t("deck.export_button", language), self)
        self._export_button.setProperty("primary", True)
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(self._on_export_clicked)
        self._open_folder_button = QPushButton(t("deck.open_folder_button", language), self)
        self._open_folder_button.setEnabled(False)
        self._open_folder_button.clicked.connect(self._on_open_folder_clicked)
        button_row.addWidget(self._export_button, stretch=1)
        button_row.addWidget(self._open_folder_button)

        # Written files
        results = QWidget(self)
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(6, 0, 0, 0)
        papers_row = QHBoxLayout()
        papers_row.addWidget(QLabel(t("library.tab_papers", language), results))
        papers_row.addStretch(1)
        self._source_button = QPushButton(t("deck.source_open", language), results)
        self._source_button.clicked.connect(self.saved_search_requested)
        papers_row.addWidget(self._source_button)
        results_layout.addLayout(papers_row)
        self._paper_titles = QListWidget(results)
        self._paper_titles.setAccessibleName(t("library.tab_papers", language))
        results_layout.addWidget(self._paper_titles, stretch=1)
        review_row = QHBoxLayout()
        self._review_button = QPushButton(t("deck.review_button", language), self)
        self._review_button.clicked.connect(self._on_review_clicked)
        review_row.addWidget(self._review_button)
        self._edit_button = QPushButton(t("slides.button", language), self)
        self._edit_button.clicked.connect(self._on_edit_clicked)
        review_row.addWidget(self._edit_button)
        review_row.addStretch(1)
        results_layout.addLayout(review_row)
        self._table = QTableView(self)
        self._table.setModel(self._files_model)
        self._table.setSelectionBehavior(QTableView.SelectRows)
        self._table.setEditTriggers(QTableView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        results_layout.addWidget(self._table, stretch=1)

        self._status_label = QLabel(t("deck.status_no_collection", language), self)
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        self._status_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        results_layout.addWidget(self._status_label)

        self._split = AdaptiveSplit(controls, results, footer=footer, parent=self)
        outer.addWidget(self._split)
        self._format_checks["pptx"].toggled.connect(self._cli_provider.setEnabled)
        self._format_checks["pptx"].toggled.connect(self._update_collection_status)
        self._cli_provider.currentIndexChanged.connect(self._update_collection_status)

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Re-arrange for the window size class (called by the main window)."""
        self._split.apply_breakpoint(breakpoint)

    def split(self) -> AdaptiveSplit:
        return self._split

    def format_grid(self) -> ReflowGrid:
        return self._format_grid

    # --- public API -----------------------------------------------------

    def set_collection(self, collection: object) -> None:
        self._paper_titles.clear()
        if collection is None or not isinstance(collection, PaperCollection):
            self._collection = None
            self._collection_is_enriched = False
            self._export_button.setEnabled(False)
            self._status_label.setText(
                t("deck.status_no_collection", self._ui_language),
            )
            return
        self._collection = collection
        self._paper_titles.addItems([paper.title for paper in collection.papers])
        # Heuristic: when any paper has a populated summary, the
        # collection has been through EnrichPage. Surface the distinction
        # because the user wants to know whether the exported deck will
        # be lightweight or thesis-style before clicking Export.
        self._collection_is_enriched = any(
            p.summary is not None for p in collection.papers
        )
        self._refresh_export_button()
        self._update_collection_status()

    def _update_collection_status(self) -> None:
        collection = self._collection
        if self._exporting or collection is None:
            return
        if self._cli_provider.currentData() and self._format_checks["pptx"].isChecked():
            self._status_label.setText(t(
                "deck.cli_ready", self._ui_language,
                name=self._cli_provider.currentText(), count=len(collection.papers),
            ))
            return
        status_key = (
            "deck.status_ready_enriched"
            if self._collection_is_enriched
            else "deck.status_ready_raw"
        )
        self._status_label.setText(
            t(status_key, self._ui_language, count=len(collection.papers)),
        )

    def collection(self) -> PaperCollection | None:
        return self._collection

    def set_source_enabled(self, enabled: bool) -> None:
        self._source_button.setEnabled(enabled)

    def set_source_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _refresh_export_button(self) -> None:
        self._export_button.setEnabled(
            bool(self._collection and self._collection.papers)
            and not self._exporting
        )

    def status_text(self) -> str:
        return self._status_label.text()

    def files_model(self) -> QStandardItemModel:
        return self._files_model

    def format_checkbox(self, fmt: str) -> QCheckBox:
        return self._format_checks[fmt]

    def cli_provider_combo(self) -> QComboBox:
        return self._cli_provider

    def verify_identifiers_checkbox(self) -> QCheckBox:
        return self._verify_identifiers_check

    def set_library_path(self, path: str) -> None:
        """Use the library file named on the Search tab as the identifier cache.

        Connected to ``SearchPage.library_path_changed``. With a path set, an
        export keeps its DOI / URL verdicts in that library, so identifiers
        verified by an earlier export are not checked again. Empty switches
        it off.
        """
        self._library_path = path.strip()

    def set_template_path(self, path: str) -> None:
        self._template_input.setText(path)

    def save_form(self, store: QSettings) -> None:
        """Write the output, format and option fields to ``store``.

        The filename stem is left out on purpose: it names one export, and a
        remembered stem would make the next export overwrite the last one.
        """
        values: dict[str, object] = {
            "out_dir": self._out_dir_input.text(),
            "language": self._language_combo.currentData() or "en",
            "cli_provider": self._cli_provider.currentData(),
            "formats": ",".join(self._selected_formats()),
            "max_slides": self._max_slides_spin.value(),
            "include_abstract": self._include_abstract_check.isChecked(),
            "dark_mode": self._dark_mode_check.isChecked(),
            "verify_identifiers": self._verify_identifiers_check.isChecked(),
            "download_pdfs": self._download_pdfs_check.isChecked(),
            "template": self._template_input.text(),
            "template_config": self._template_config_input.text(),
            "docx_template": self._docx_template_input.text(),
        }
        for key, value in values.items():
            store.setValue(f"{_FORM_GROUP}/{key}", value)

    def restore_form(self, store: QSettings) -> None:
        """Fill the fields from ``store``; missing values keep the defaults."""
        self._restore_paths(store)
        language = _stored(store, "language", str)
        if language is not None and self._language_combo.findData(language) >= 0:
            self._language_combo.setCurrentIndex(self._language_combo.findData(language))
        provider = _stored(store, "cli_provider", str)
        self._cli_provider.setCurrentIndex(max(0, self._cli_provider.findData(provider)))
        formats = _stored(store, "formats", str)
        if formats is not None:
            wanted = set(str(formats).split(","))
            for fmt, check in self._format_checks.items():
                check.setChecked(fmt in wanted)
        max_slides = _stored(store, "max_slides", int)
        if max_slides is not None:
            self._max_slides_spin.setValue(int(max_slides))
        self._restore_flags(store)

    def _restore_paths(self, store: QSettings) -> None:
        """Restore the output folder and template path fields from ``store``.

        Guards the output folder: an empty saved value is skipped, since it
        would leave Export with nowhere to write. Empty template paths are
        restored, because no template is a valid choice.
        """
        for key, field in (
            ("out_dir", self._out_dir_input),
            ("template", self._template_input),
            ("template_config", self._template_config_input),
            ("docx_template", self._docx_template_input),
        ):
            text = _stored(store, key, str)
            if text is not None and (text or key != "out_dir"):
                field.setText(str(text))

    def _restore_flags(self, store: QSettings) -> None:
        """Restore the four option check boxes from ``store``.

        Guards against a missing key resetting a box: only a stored value
        changes it, so a first run keeps the defaults built in ``__init__``.
        """
        for key, check in (
            ("include_abstract", self._include_abstract_check),
            ("dark_mode", self._dark_mode_check),
            ("verify_identifiers", self._verify_identifiers_check),
            ("download_pdfs", self._download_pdfs_check),
        ):
            flag = _stored(store, key, bool)
            if flag is not None:
                check.setChecked(bool(flag))

    def set_docx_template_path(self, path: str) -> None:
        self._docx_template_input.setText(path)

    def set_template_config_path(self, path: str) -> None:
        self._template_config_input.setText(path)

    # --- internals ------------------------------------------------------

    def _file_row(
        self, form: QFormLayout, label_key: str, placeholder_key: str,
        dialog_title_key: str, file_filter: str,
    ) -> QLineEdit:
        """Add a "path + Browse" row to ``form`` and return its line edit."""
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit(self)
        field.setPlaceholderText(t(placeholder_key, self._ui_language))
        browse = QPushButton(t("deck.browse_button", self._ui_language), self)

        def choose() -> None:
            path, _ = QFileDialog.getOpenFileName(
                self, t(dialog_title_key, self._ui_language),
                field.text() or str(Path.cwd()), file_filter,
            )
            if path:
                field.setText(path)

        browse.clicked.connect(choose)
        layout.addWidget(field, stretch=1)
        layout.addWidget(browse)
        form.addRow(t(label_key, self._ui_language), row)
        return field

    def _on_browse_out_dir(self) -> None:
        start = self._out_dir_input.text() or str(Path.cwd())
        path = QFileDialog.getExistingDirectory(
            self, t("deck.out_dir_dialog_title", self._ui_language), start,
        )
        if path:
            self._out_dir_input.setText(path)

    def _selected_formats(self) -> tuple[str, ...]:
        return tuple(
            fmt for fmt, _label in _FORMAT_CHOICES
            if self._format_checks[fmt].isChecked()
        )

    def _export_blocker(
        self, formats: tuple[str, ...], download_pdfs: bool, out_dir: str
    ) -> str | None:
        """Return the i18n key of the reason Export cannot start, or ``None``.

        Guards the worker start: no papers, nothing to produce (no format and
        no PDF download) or no output folder each stop the run with a status
        line before any thread is spawned. Checked in that order, so the
        first missing input is the one reported.

        Example: with papers loaded, ``self._export_blocker((), False, "out")``
        returns ``"deck.error_no_formats"``.
        """
        if self._collection is None or not self._collection.papers:
            return "deck.error_no_collection"
        if not formats and not download_pdfs:
            return "deck.error_no_formats"
        if not out_dir:
            return "deck.error_no_out_dir"
        return None

    def _export_options(self, formats: tuple[str, ...], out_dir: str) -> ExportOptions:
        """Build the :class:`ExportOptions` of one run from the form fields.

        Guards the PDFs-only run: ``ExportOptions`` needs at least one format,
        so an empty ``formats`` is passed as ``("json",)``, which that run
        never writes. Raises ``ValueError`` when ``ExportOptions`` refuses the
        combination (a template config with no template).

        Example: ``self._export_options(("pptx",), "exports")`` returns options
        whose ``formats`` is ``("pptx",)``.
        """
        return ExportOptions(
            formats=formats or ("json",),
            out_dir=out_dir,
            filename_stem=self._filename_stem_input.text().strip() or None,
            include_abstract=self._include_abstract_check.isChecked(),
            language=self._language_combo.currentData() or "en",
            max_slides_per_paper=self._max_slides_spin.value(),
            dark_mode=self._dark_mode_check.isChecked(),
            verify_identifiers=self._verify_identifiers_check.isChecked(),
            pptx_template=self._template_input.text().strip() or None,
            docx_template=self._docx_template_input.text().strip() or None,
            pptx_template_config=self._template_config_input.text().strip() or None,
        )

    def _on_export_clicked(self) -> None:
        if self._exporting or not self.isEnabled():
            return
        formats = self._selected_formats()
        download_pdfs = self._download_pdfs_check.isChecked()
        out_dir = self._out_dir_input.text().strip()
        blocker = self._export_blocker(formats, download_pdfs, out_dir)
        if blocker is not None:
            self._status_label.setText(t(blocker, self._ui_language))
            return
        try:
            options = self._export_options(formats, out_dir)
            provider = self._cli_provider.currentData() if "pptx" in formats else ""
            settings = saved_provider_settings(provider) if provider else None
        except (ConfigError, ValueError) as err:
            # A template config with no template: say so here, the options
            # object refuses the combination before any worker starts.
            self._on_export_failed(err)
            return
        collection = self._collection
        self._exporting = True
        self._export_button.setEnabled(False)
        self._open_folder_button.setEnabled(False)
        self._files_model.removeRows(0, self._files_model.rowCount())
        self._status_label.setText(t("deck.status_running", self._ui_language))
        self.busy_changed.emit(True)

        library_path = self._library_path
        vpn_access = saved_vpn_access()
        ui_language = self._ui_language

        def call() -> _ExportOutcome:
            prepared = (
                asyncio.run(prepare_cli_deck(
                    collection, settings, options.language,
                    ui_language=ui_language, vpn_access=vpn_access,
                ))
                if settings is not None else collection
            )
            written: dict[str, Path] = {}
            if formats and not library_path:
                written = export_collection(prepared, options)
            elif formats:
                with Library(library_path) as library:
                    written = export_collection(
                        prepared, options, verification_cache=library.verification_cache()
                    )
            pdfs = (
                run_pdf_stage(collection, out_dir, vpn_access=vpn_access)
                if download_pdfs else None
            )
            return _ExportOutcome(dict(written), pdfs)

        worker = BlockingWorker(call)
        worker.signals.finished.connect(self._on_export_finished)
        worker.signals.failed.connect(self._on_export_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_export_finished(self, result: object) -> None:
        self._exporting = False
        self.busy_changed.emit(False)
        self._refresh_export_button()
        if isinstance(result, _ExportOutcome):
            outcome = result
        else:
            outcome = _ExportOutcome(result if isinstance(result, dict) else {})
        written = outcome.written
        if not written and outcome.pdfs is None:
            self._status_label.setText(
                t("deck.error_no_output", self._ui_language),
            )
            return
        folder: Path | None = None
        for fmt, path in written.items():
            self._files_model.appendRow([
                QStandardItem(fmt),
                QStandardItem(str(path)),
            ])
            folder = Path(path).parent
        if outcome.pdfs is not None:
            self._files_model.appendRow([
                QStandardItem("pdf"), QStandardItem(str(outcome.pdfs.folder)),
            ])
            # A PDFs-only run has no other file: Open folder shows the PDFs.
            folder = folder or outcome.pdfs.folder
        if folder is not None:
            self._last_written_dir = folder
            self._open_folder_button.setEnabled(True)
        deck = written.get("pptx")
        self._last_deck = Path(deck) if isinstance(deck, (str, Path)) else None
        self._status_label.setText(self._done_status(outcome))

    def _done_status(self, outcome: _ExportOutcome) -> str:
        """Files written, then the PDF counts and any IEEE papers held back."""
        language = self._ui_language
        parts = []
        if outcome.written:
            parts.append(t("deck.status_done", language, count=len(outcome.written)))
        pdfs = outcome.pdfs
        if pdfs is not None:
            parts.append(t("deck.pdfs_summary", language, saved=pdfs.saved, skipped=pdfs.skipped))
            if pdfs.via_browser:
                parts.append(t("deck.pdfs_via_browser", language, count=pdfs.via_browser))
            if pdfs.without_browser:
                parts.append(t("deck.pdfs_no_browser", language, count=pdfs.without_browser))
            if pdfs.browser_failed:
                parts.append(t("deck.pdfs_browser_failed", language, count=pdfs.browser_failed))
            if pdfs.held:
                parts.append(t("deck.pdfs_ieee_held", language, count=pdfs.held))
        return " ".join(parts)

    def output_dir(self) -> str:
        """The export folder typed on this page (the Search page copies
        local PDFs into its ``pdfs`` subfolder)."""
        return self._out_dir_input.text().strip()

    def download_pdfs_checkbox(self) -> QCheckBox:
        return self._download_pdfs_check

    def _on_export_failed(self, err: object) -> None:
        self._exporting = False
        self.busy_changed.emit(False)
        self._refresh_export_button()
        self._status_label.setText(
            t("deck.error_generic", self._ui_language, error=str(err)),
        )

    # --- template check and deck review (progress #23) --------------------

    def _on_check_template_clicked(self) -> None:
        """Validate the chosen template (and config) without exporting.

        The same check ``thesisagents validate-template`` runs, and the one an
        export runs first. Doing it here costs a second instead of a whole
        search-and-export round trip.
        """
        template = self._template_input.text().strip()
        if not template:
            self._status_label.setText(t("deck.error_no_template", self._ui_language))
            return
        config = self._template_config_input.text().strip() or None
        dark = self._dark_mode_check.isChecked()
        self._run_check(lambda: validate_template(template, config, dark_mode=dark))

    def _on_review_clicked(self) -> None:
        """Audit a finished deck: overflow, colour contracts, section completeness."""
        start = self._last_deck or self._last_written_dir or Path(self._out_dir_input.text())
        path, _ = QFileDialog.getOpenFileName(
            self, t("deck.review_dialog_title", self._ui_language),
            str(start), "PowerPoint (*.pptx);;All files (*)",
        )
        if path:
            self.review_deck_file(path)

    def _on_edit_clicked(self) -> None:
        """Edit the deck selected in the list, or one the user picks."""
        path = self._selected_deck()
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, t("slides.button", self._ui_language),
                self.output_dir() or str(Path.cwd()), "PowerPoint (*.pptx)",
            )
        if path:
            self.edit_deck_file(path)

    def _selected_deck(self) -> str:
        rows = self._table.selectionModel().selectedRows(1)
        path = str(rows[0].data() or "") if len(rows) == 1 else ""
        return path if path.lower().endswith(".pptx") and Path(path).is_file() else ""

    def edit_deck_file(self, path: str) -> None:
        """Open the slide editor on ``path``."""
        try:
            self._deck_editor = DeckEditor(path, self._ui_language, self)
        except (ExportError, OSError) as err:
            self._status_label.setText(t("deck.check_failed", self._ui_language, error=str(err)))
            return
        self._deck_editor.open()

    def deck_editor(self) -> DeckEditor:
        return self._deck_editor

    def review_deck_file(self, path: str) -> None:
        """Review ``path`` on a worker thread and show the report."""
        self._run_check(lambda: review_deck(path))

    def _run_check(self, call) -> None:
        self._check_template_button.setEnabled(False)
        self._review_button.setEnabled(False)
        self.busy_changed.emit(True)
        worker = BlockingWorker(call)
        worker.signals.finished.connect(self._on_check_finished)
        worker.signals.failed.connect(self._on_check_failed)
        QThreadPool.globalInstance().start(worker)

    def _end_check(self) -> None:
        self._check_template_button.setEnabled(True)
        self._review_button.setEnabled(True)
        self.busy_changed.emit(False)

    def _on_check_failed(self, err: object) -> None:
        self._end_check()
        self._status_label.setText(t("deck.check_failed", self._ui_language, error=str(err)))

    def _on_check_finished(self, result: object) -> None:
        """One-line verdict on the status line, the full report in a dialog."""
        self._end_check()
        language = self._ui_language
        if isinstance(result, TemplateValidationReport):
            title = t("deck.report_template_title", language)
            text = format_template_report(result)
            verdict = (
                t("deck.template_ok", language)
                if result.ok
                else t("deck.template_not_usable", language, errors=len(result.errors))
            )
        elif isinstance(result, DeckReview):
            title = t("deck.report_review_title", language)
            text = format_review(result)
            problems = len(result.overflow) + len(result.hard_contrast) + len(
                result.missing_sections
            )
            verdict = (
                t("deck.review_pass", language)
                if result.ok
                else t("deck.review_fail", language, problems=problems)
            )
        else:  # pragma: no cover - defensive
            self._on_check_failed(RuntimeError(f"unexpected result {type(result)!r}"))
            return
        self._status_label.setText(verdict)
        self._last_report = ReportDialog(
            title, text,
            copy_label=t("action.copy", language), close_label=t("action.close", language),
            parent=self,
        )
        self._last_report.open()

    def last_report(self) -> ReportDialog | None:
        """The report dialog last opened (tests read its text)."""
        return self._last_report

    def _on_open_folder_clicked(self) -> None:
        if self._last_written_dir is None:
            return
        # QDesktopServices is the cross-platform "open in file manager"
        # — Windows Explorer, macOS Finder, xdg-open on Linux. Subprocess
        # would be more controllable but also leaks the host OS into the
        # GUI layer; this is the right abstraction.
        url = QUrl.fromLocalFile(str(self._last_written_dir))
        QDesktopServices.openUrl(url)



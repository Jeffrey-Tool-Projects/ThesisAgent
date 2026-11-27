"""``QAbstractTableModel`` exposing a ``PaperCollection`` to a ``QTableView``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Signal

from thesisagents.core.diagnostics import PruningAction, SearchDiagnostics
from thesisagents.core.models import Paper, PaperCollection
from thesisagents.gui.enrichment import SummaryChanges, apply_summary_changes
from thesisagents.gui.i18n import t

_COLUMN_KEYS: Final[tuple[str, ...]] = (
    "results.col_title",
    "results.col_authors",
    "results.col_year",
    "results.col_source",
    "results.col_doi",
    "results.col_citations",
    "results.col_suggestion",
)
_SUGGESTION_COLUMN: Final[int] = _COLUMN_KEYS.index("results.col_suggestion")
_SUGGESTION_KEYS: Final[dict[PruningAction, str]] = {
    PruningAction.KEEP: "results.suggestion_keep",
    PruningAction.REVIEW: "results.suggestion_review",
    PruningAction.PRUNE: "results.suggestion_prune",
}
_NO_VALUE: Final[str] = "—"
#: Role holding a value that sorts correctly: numbers for year and
#: citations (a missing value sorts first), case-folded text otherwise.
#: Display values cannot be compared directly, a year column mixes ``2024``
#: with the ``"—"`` placeholder.
SORT_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole) + 1
_NUMERIC_COLUMNS: Final[frozenset[int]] = frozenset({2, 5})


class PapersTableModel(QAbstractTableModel):
    """Read-only view of ``PaperCollection.papers``.

    The model holds a tuple, not a list, mirroring the dataclass'
    immutability — to "update" the model the caller assigns a new
    collection via :meth:`set_collection`, which fires a layout reset
    so the table redraws.

    The last column shows the advisory pruning recommendation the search
    recorded for each paper (keep / review / prune), and hovering any cell of a
    row shows why: the score breakdown and the rule that triggered the advice.
    A collection without diagnostics (one loaded from elsewhere than a search)
    shows a dash there and no tooltip.
    """

    #: Emitted when a check box in the title column changes.
    checks_changed = Signal()

    def __init__(self, language: str = "en", parent=None) -> None:
        super().__init__(parent)
        self.collection: PaperCollection | None = None
        self._checked: list[bool] = []
        self._diagnostics: SearchDiagnostics | None = None
        self._language = language

    def set_collection(self, collection: PaperCollection | None) -> None:
        self.beginResetModel()
        self.collection = collection
        self._diagnostics = collection.diagnostics if collection else None
        # A fresh result starts with every paper ticked, so a user who never
        # touches the boxes sends the whole result on, as before.
        self._checked = [True] * len(self.papers())
        self.endResetModel()
        self.checks_changed.emit()

    def set_language(self, language: str) -> None:
        self._language = language
        # Force header redraw with the new language.
        self.headerDataChanged.emit(
            Qt.Horizontal, 0, self.columnCount() - 1
        )

    def papers(self) -> tuple[Paper, ...]:
        return self.collection.papers if self.collection is not None else ()

    def update_summaries(self, changes: SummaryChanges) -> None:
        """Keep row order and checks when Enrich updates a summary."""
        if self.collection is not None:
            self.collection = apply_summary_changes(self.collection, changes)

    # --- the subset sent on (check boxes in the title column) ---------

    def checked_papers(self) -> tuple[Paper, ...]:
        """The ticked papers, in result order: what Enrich, Deck and Export get."""
        return tuple(p for p, ticked in zip(self.papers(), self._checked, strict=True) if ticked)

    def checked_count(self) -> int:
        return sum(self._checked)

    def unchecked_rows(self) -> list[int]:
        """Rows whose box is not ticked (to carry ticks over to a rebuilt window)."""
        return [row for row, ticked in enumerate(self._checked) if not ticked]

    def set_checked(self, row: int, checked: bool) -> None:
        if 0 <= row < len(self._checked) and self._checked[row] != checked:
            self._checked[row] = checked
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.CheckStateRole])
            self.checks_changed.emit()

    def set_all_checked(self, checked: bool, rows: list[int] | None = None) -> None:
        """Tick or untick ``rows`` (all rows when ``None``) in one change."""
        targets = range(len(self._checked)) if rows is None else rows
        changed = False
        for row in targets:
            if 0 <= row < len(self._checked) and self._checked[row] != checked:
                self._checked[row] = checked
                changed = True
        if changed and self.papers():
            self.dataChanged.emit(
                self.index(0, 0), self.index(len(self.papers()) - 1, 0),
                [Qt.ItemDataRole.CheckStateRole],
            )
            self.checks_changed.emit()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if index.isValid() and index.column() == 0:
            return base | Qt.ItemFlag.ItemIsUserCheckable
        return base

    def setData(self, index: QModelIndex, value: object, role: int = Qt.EditRole) -> bool:  # noqa: N802 - Qt override
        if role != Qt.ItemDataRole.CheckStateRole or not index.isValid() or index.column() != 0:
            return False
        state = value.value if hasattr(value, "value") else value
        self.set_checked(index.row(), state == Qt.CheckState.Checked.value)
        return True

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008  # Qt override
        if parent.isValid():
            return 0
        return len(self.papers())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, B008  # Qt override
        if parent.isValid():
            return 0
        return len(_COLUMN_KEYS)

    def headerData(  # noqa: N802  # Qt override
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ) -> object:
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <= section < len(_COLUMN_KEYS):
            return t(_COLUMN_KEYS[section], self._language)
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid() or not (0 <= index.row() < len(self.papers())):
            return None
        paper = self.papers()[index.row()]
        if role == Qt.ToolTipRole:
            return self._explanation(paper)
        if role == Qt.ItemDataRole.CheckStateRole and index.column() == 0:
            ticked = self._checked[index.row()]
            return Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked
        if role == SORT_ROLE:
            return self._sort_key(paper, index.column())
        if role != Qt.DisplayRole:
            return None
        return self._display(paper, index.column())

    def _display(self, paper: Paper, column: int) -> object:
        if column == _SUGGESTION_COLUMN:
            return self._suggestion(paper)
        values: tuple[object, ...] = (
            paper.title,
            ", ".join(paper.authors[:3]) + (", …" if len(paper.authors) > 3 else ""),
            paper.year if paper.year is not None else _NO_VALUE,
            paper.source,
            paper.doi or _NO_VALUE,
            paper.citation_count if paper.citation_count is not None else _NO_VALUE,
        )
        return values[column] if 0 <= column < len(values) else None

    def _sort_key(self, paper: Paper, column: int) -> object:
        if column in _NUMERIC_COLUMNS:
            value = paper.year if column == 2 else paper.citation_count
            return -1 if value is None else value
        shown = self._display(paper, column)
        return "" if shown in (None, _NO_VALUE) else str(shown).casefold()

    def _suggestion(self, paper: Paper) -> str:
        """Localised keep / review / prune label, or a dash when none was recorded."""
        if self._diagnostics is None:
            return _NO_VALUE
        advice = self._diagnostics.recommendation_for(paper.dedup_key())
        if advice is None:
            return _NO_VALUE
        return t(_SUGGESTION_KEYS[advice.action], self._language)

    def _explanation(self, paper: Paper) -> str | None:
        """Tooltip text: the score split, its reasons, then the advice's reasons.

        The sentences come from ``ranking.py`` / ``pruning.py`` and are English
        only, like the CLI's ``--diagnostics`` output: they quote query terms
        and thresholds, which would not survive a table of translations.
        """
        if self._diagnostics is None:
            return None
        key = paper.dedup_key()
        score = self._diagnostics.score_for(key)
        advice = self._diagnostics.recommendation_for(key)
        if score is None:
            return None
        lines = [
            f"total {score.total:.2f} = relevance {score.relevance:.2f} "
            f"+ recency {score.recency:.2f} + citations {score.citation:.2f}",
            *(f"• {reason}" for reason in score.reasons),
        ]
        if advice is not None:
            lines.append(f"→ {advice.action.value}")
            lines.extend(f"• {reason}" for reason in advice.reasons)
        return "\n".join(lines)


class PaperFilterProxy(QSortFilterProxyModel):
    """Sorts the results table and hides rows that do not match a filter.

    The boundary this guards: filtering is a *view*. A hidden paper keeps its
    check box state and is still sent on when ticked, so typing in the filter
    box can never silently drop a paper from an export.

    ``set_text`` matches, case-insensitively, against the title, authors,
    venue and DOI. ``set_source`` keeps one source (``None`` keeps all).

    Example::

        proxy = PaperFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_text("transformer")
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._text = ""
        self._source: str | None = None
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)

    def set_text(self, text: str) -> None:
        self._refilter(lambda: setattr(self, "_text", text.strip().casefold()))

    def set_source(self, source: str | None) -> None:
        self._refilter(lambda: setattr(self, "_source", source or None))

    def _refilter(self, change: Callable[[], None]) -> None:
        """Apply ``change`` to the filter and re-run it.

        Qt 6.10 deprecates ``invalidateFilter()`` for the begin / end pair,
        which the project's oldest supported PySide6 (6.7) does not have.
        """
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
            change()
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:  # pragma: no cover - PySide6 < 6.9
            change()
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802 - Qt override
        model = self.sourceModel()
        if not isinstance(model, PapersTableModel):
            return True
        papers = model.papers()
        if not 0 <= source_row < len(papers):
            return False
        paper = papers[source_row]
        if self._source is not None and paper.source != self._source:
            return False
        if not self._text:
            return True
        haystack = " ".join(
            (paper.title, " ".join(paper.authors), paper.venue or "", paper.doi or "")
        ).casefold()
        return all(word in haystack for word in self._text.split())

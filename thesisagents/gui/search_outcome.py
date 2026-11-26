"""What a search worker brings back, and the status line that tells it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from thesisagents.core.diagnostics import SourceStatus
from thesisagents.core.models import PaperCollection
from thesisagents.gui.i18n import t
from thesisagents.library import AddReport

_SOURCE_STATUS_KEYS: dict[SourceStatus, str] = {
    SourceStatus.FAILED: "search.source_failed",
    SourceStatus.RATE_LIMITED: "search.source_rate_limited",
    SourceStatus.DISABLED: "search.source_disabled",
}


@dataclass(frozen=True)
class SearchOutcome:
    """What a search worker hands back to the UI thread besides the papers.

    The boundary this guards: the worker thread. Everything the status line
    needs travels in this one frozen object through the ``finished`` signal,
    so the worker never touches a widget or a page attribute.

    ``discovered`` is the number of papers the snowball added (``None`` when
    it was off), ``library`` what merging into the library changed, and
    ``library_total`` the size of the library when the papers came from it.

    Example: ``SearchOutcome(collection, discovered=3)`` after a search with
    the snowball on.
    """

    collection: PaperCollection
    discovered: int | None = None
    library: AddReport | None = None
    library_total: int | None = None
    #: Export folder the local PDFs were copied into (``None`` for a search).
    local_folder: str | None = None


def finished_status(
    collection: PaperCollection, outcome: SearchOutcome | None, language: str
) -> str:
    """The status line after a run: counts, sources, snowball, library."""
    if outcome is not None and outcome.local_folder is not None:
        return t(
            "search.local_done", language,
            count=len(collection.papers),
            folder=str(Path(outcome.local_folder) / "pdfs"),
        )
    if outcome is not None and outcome.library_total is not None:
        return t(
            "search.library_found", language,
            count=len(collection.papers), total=outcome.library_total,
        )
    parts = [t("search.status_done", language, count=len(collection.papers))]
    summary = source_summary(collection, language)
    if summary:
        parts.append(t("search.sources_summary", language, summary=summary))
    if outcome is not None and outcome.discovered is not None:
        parts.append(t("search.snowball_summary", language, count=outcome.discovered))
    if outcome is not None and outcome.library is not None:
        parts.append(
            t(
                "search.library_added", language,
                added=outcome.library.added, merged=outcome.library.merged,
            )
        )
    return " ".join(parts)


def source_summary(collection: PaperCollection, language: str) -> str:
    """What each source returned, as ``"arxiv 23, openalex 25, ieee (failed)"``.

    Why it is on the status line: a source that fails is skipped without
    stopping the search, so "Found 3 papers" alone cannot tell a narrow
    topic from a search that lost most of its sources. Empty when the
    collection carries no per-source counts.
    """
    diagnostics = collection.diagnostics
    if diagnostics is None:
        return ""
    parts: list[str] = []
    for stat in diagnostics.source_stats:
        label_key = _SOURCE_STATUS_KEYS.get(stat.status)
        if label_key is None:
            parts.append(f"{stat.source} {stat.returned}")
        else:
            parts.append(f"{stat.source} ({t(label_key, language)})")
    return ", ".join(parts)

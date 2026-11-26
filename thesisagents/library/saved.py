"""Saved searches: run a query again and see only what is new.

A saved search is a name and a query in the library file. Running it adds
what it finds to the library like any search, and reports the papers the
library did not hold before. The first run reports everything.

Example::

    with Library("thesis.db") as library:
        library.save_search("transformers", Query("transformer", ("arxiv",)))
        outcome = await run_saved_search(library, "transformers")
        outcome.new_papers
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from thesisagents.core.exceptions import LibraryError
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.library.schema import transaction

_MAX_NAME_LENGTH: Final[int] = 80
#: ``runs.kind`` of a saved search, so the history tells it from a one-off.
RUN_SAVED: Final[str] = "saved"


@dataclass(frozen=True, slots=True)
class SavedSearch:
    """One saved query and when it last ran. ``last_new`` is None before that."""

    name: str
    query: Query
    created_at: str
    last_run_at: str | None = None
    last_new: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "query": query_to_dict(self.query),
            "created_at": self.created_at,
            "last_run_at": self.last_run_at,
            "last_new": self.last_new,
        }


@dataclass(frozen=True, slots=True)
class SavedSearchOutcome:
    """What a run found: everything, and the papers that were not here before."""

    name: str
    collection: PaperCollection
    new_papers: tuple[Paper, ...]


def query_to_dict(query: Query) -> dict[str, Any]:
    """A query as plain JSON values, the form the library stores."""
    return {
        "keywords": query.keywords,
        "sources": list(query.sources),
        "max_results": query.max_results,
        "year_from": query.year_from,
        "year_to": query.year_to,
        "min_citations": query.min_citations,
        "top_tier_only": query.top_tier_only,
    }


def query_from_dict(record: dict[str, Any]) -> Query:
    """The inverse of :func:`query_to_dict`. ``ValueError`` when it is no query."""
    try:
        fields = dict(record)
        fields["sources"] = tuple(fields["sources"])
        return Query(**fields)
    except (KeyError, TypeError) as err:
        raise ValueError(f"not a stored query: {err}") from err


class SavedSearchMixin:
    """The methods of :class:`~thesisagents.library.store.Library` for saved searches."""

    _conn: sqlite3.Connection
    _lock: threading.RLock

    def _stamp(self) -> str:
        raise NotImplementedError

    def save_search(self, name: str, query: Query) -> None:
        """Save ``query`` under ``name``, replacing one saved there."""
        name = " ".join(name.split())
        if not name or len(name) > _MAX_NAME_LENGTH:
            raise ValueError(f"a name needs 1 to {_MAX_NAME_LENGTH} characters")
        with self._lock, transaction(self._conn):
            self._conn.execute(
                "INSERT INTO saved_searches (name, query, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT (name) DO UPDATE SET query = excluded.query, "
                "created_at = excluded.created_at, last_run_at = NULL, last_new = NULL",
                (name, json.dumps(query_to_dict(query), ensure_ascii=False), self._stamp()),
            )

    def saved_searches(self) -> list[SavedSearch]:
        """Every saved search, by name."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, query, created_at, last_run_at, last_new "
                "FROM saved_searches ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [
            SavedSearch(name, query_from_dict(json.loads(query)), created, run, new)
            for name, query, created, run, new in rows
        ]

    def saved_search(self, name: str) -> SavedSearch:
        wanted = " ".join(name.split())
        stored = self.saved_searches()
        # The exact spelling first: SQLite compares only ASCII without case,
        # so "École" and "école" can both be saved.
        for saved in stored:
            if saved.name == wanted:
                return saved
        for saved in stored:
            if saved.name.casefold() == wanted.casefold():
                return saved
        raise LibraryError(f"no saved search called {name!r}")

    def delete_saved_search(self, name: str) -> None:
        """Forget the search. The papers it found stay."""
        saved = self.saved_search(name)
        with self._lock, transaction(self._conn):
            self._conn.execute("DELETE FROM saved_searches WHERE name = ?", (saved.name,))

    def record_saved_run(self, name: str, new: int) -> None:
        with self._lock, transaction(self._conn):
            self._conn.execute(
                "UPDATE saved_searches SET last_run_at = ?, last_new = ? WHERE name = ?",
                (self._stamp(), new, name),
            )


async def run_saved_search(
    library: Any,
    name: str,
    search: Callable[[Query], Awaitable[PaperCollection]] | None = None,
) -> SavedSearchOutcome:
    """Run the saved search, add what it finds, report what is new.

    ``search`` defaults to ``run_search``. What is new is decided against the
    library as it was before this run, with the matching an import uses, so a
    paper found under another DOI or spelling does not count as new.
    """
    if search is None:
        from thesisagents.core.pipeline import run_search

        search = run_search
    saved = library.saved_search(name)
    collection = await search(saved.query)
    new = tuple(paper for paper in collection.papers if not library.holds(paper))
    library.add_collection(collection, kind=RUN_SAVED)
    library.record_saved_run(saved.name, len(new))
    return SavedSearchOutcome(saved.name, collection, new)

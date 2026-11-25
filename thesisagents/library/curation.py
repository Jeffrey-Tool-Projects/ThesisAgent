"""What the reader adds to a library: tags, notes, reading status, screening.

The search side of a library (``store.py``) records what sources returned.
This module records what a person decided about it, and keeps the two apart:
importing the same search again never touches a tag, a note or a decision.

Papers are named by ``LibraryEntry.paper_id``, the row number, which is
short enough to type on a command line. Merging two papers keeps the
surviving row's number, and deleting one retires its number.

Example::

    with Library("thesis.db") as library:
        library.add_tags([3, 7], ["chapter 2"])
        library.set_reading_status([3], READING_DONE)
        library.screen([7], DECISION_EXCLUDE, reason="not peer reviewed")
        for group in library.duplicate_candidates():
            library.merge(group[0], group[1:])
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from thesisagents.core.dedup import merge_papers
from thesisagents.core.exceptions import LibraryError
from thesisagents.core.models import Paper
from thesisagents.library.schema import transaction

READING_UNREAD: Final[str] = "unread"
READING_NOW: Final[str] = "reading"
READING_DONE: Final[str] = "read"
READING_STATUSES: Final[tuple[str, ...]] = (READING_UNREAD, READING_NOW, READING_DONE)

DECISION_INCLUDE: Final[str] = "include"
DECISION_MAYBE: Final[str] = "maybe"
DECISION_EXCLUDE: Final[str] = "exclude"
DECISIONS: Final[tuple[str, ...]] = (DECISION_INCLUDE, DECISION_MAYBE, DECISION_EXCLUDE)

#: The two rounds of a systematic review: by title and abstract, then by
#: reading the paper.
STAGE_ABSTRACT: Final[str] = "title_abstract"
STAGE_FULL_TEXT: Final[str] = "full_text"
STAGES: Final[tuple[str, ...]] = (STAGE_ABSTRACT, STAGE_FULL_TEXT)

_MAX_TAG_LENGTH: Final[int] = 60
_MAX_NOTE_LENGTH: Final[int] = 100_000
#: Titles whose words overlap at least this much are suggested as one paper.
_DUPLICATE_OVERLAP: Final[float] = 0.85
_SHORTEST_TITLE: Final[int] = 3
_WORD = re.compile(r"\w+")


@dataclass(frozen=True, slots=True)
class Screening:
    """One decision of a systematic review, with the reason for it."""

    stage: str
    decision: str
    reason: str
    decided_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "decision": self.decision,
            "reason": self.reason,
            "decided_at": self.decided_at,
        }


@dataclass(frozen=True, slots=True)
class Annotation:
    """Everything a reader recorded about one paper."""

    status: str = READING_UNREAD
    note: str = ""
    tags: tuple[str, ...] = ()
    screening: tuple[Screening, ...] = ()

    def decision(self, stage: str) -> str:
        """The decision at ``stage``, empty when there is none."""
        return next((s.decision for s in self.screening if s.stage == stage), "")


def normalise_tag(tag: str) -> str:
    """A tag without surrounding or doubled spaces. Commas separate tags, so none is kept.

    >>> normalise_tag("  chapter   2 ")
    'chapter 2'
    """
    cleaned = " ".join(tag.replace(",", " ").split())
    if not cleaned:
        raise ValueError("a tag must contain text")
    if len(cleaned) > _MAX_TAG_LENGTH:
        raise ValueError(f"a tag can have at most {_MAX_TAG_LENGTH} characters")
    return cleaned


class CurationMixin:
    """The methods of :class:`~thesisagents.library.store.Library` that edit it by hand."""

    _conn: sqlite3.Connection
    _lock: threading.RLock

    # ---- what the store provides ----------------------------------------

    def _stamp(self) -> str:
        raise NotImplementedError

    def _load(self, paper_id: int) -> Paper:
        raise NotImplementedError

    def _absorb(self, absorbed: int, survivor: int) -> None:
        raise NotImplementedError

    def _claim_keys(self, paper_id: int, paper: Paper) -> None:
        raise NotImplementedError

    # ---- annotations -------------------------------------------------------

    def annotations(self) -> dict[int, Annotation]:
        """Every recorded annotation by paper id (papers without one are absent)."""
        with self._lock:
            plain = {
                int(paper_id): (status, note)
                for paper_id, status, note in self._conn.execute(
                    "SELECT paper_id, status, note FROM annotations"
                )
            }
            tags: dict[int, list[str]] = {}
            for paper_id, tag in self._conn.execute(
                "SELECT paper_id, tag FROM tags ORDER BY tag COLLATE NOCASE"
            ):
                tags.setdefault(int(paper_id), []).append(tag)
            screening: dict[int, list[Screening]] = {}
            for paper_id, *values in self._conn.execute(
                "SELECT paper_id, stage, decision, reason, decided_at "
                "FROM screening ORDER BY stage DESC"
            ):
                screening.setdefault(int(paper_id), []).append(Screening(*values))
        return {
            paper_id: Annotation(
                status=plain.get(paper_id, (READING_UNREAD, ""))[0],
                note=plain.get(paper_id, (READING_UNREAD, ""))[1],
                tags=tuple(tags.get(paper_id, ())),
                screening=tuple(screening.get(paper_id, ())),
            )
            for paper_id in plain.keys() | tags.keys() | screening.keys()
        }

    def tags(self) -> dict[str, int]:
        """Every tag in use and how many papers carry it."""
        with self._lock:
            return dict(
                self._conn.execute(
                    "SELECT tag, count(*) FROM tags GROUP BY tag ORDER BY tag COLLATE NOCASE"
                ).fetchall()
            )

    def add_tags(self, paper_ids: Iterable[int], tags: Iterable[str]) -> None:
        """Give every paper every tag. A tag it already has (in any case) is kept."""
        ids = self._existing(paper_ids)
        names = [normalise_tag(tag) for tag in tags]
        with self._lock, transaction(self._conn):
            self._conn.executemany(
                "INSERT OR IGNORE INTO tags (paper_id, tag) VALUES (?, ?)",
                [(paper_id, name) for paper_id in ids for name in names],
            )

    def remove_tags(self, paper_ids: Iterable[int], tags: Iterable[str]) -> None:
        """Take the tags off the papers. A tag a paper does not have is skipped."""
        ids = self._existing(paper_ids)
        names = [normalise_tag(tag) for tag in tags]
        with self._lock, transaction(self._conn):
            self._conn.executemany(
                "DELETE FROM tags WHERE paper_id = ? AND tag = ?",
                [(paper_id, name) for paper_id in ids for name in names],
            )

    def set_reading_status(self, paper_ids: Iterable[int], status: str) -> None:
        if status not in READING_STATUSES:
            raise ValueError(f"reading status must be one of {', '.join(READING_STATUSES)}")
        self._annotate(paper_ids, "status", status)

    def set_note(self, paper_id: int, note: str) -> None:
        """Replace the note of one paper. An empty one removes it."""
        if len(note) > _MAX_NOTE_LENGTH:
            raise ValueError(f"a note can have at most {_MAX_NOTE_LENGTH} characters")
        self._annotate([paper_id], "note", note.strip())

    def _annotate(self, paper_ids: Iterable[int], column: str, value: str) -> None:
        # ``column`` is one of two names above, never input.
        ids = self._existing(paper_ids)
        with self._lock, transaction(self._conn):
            self._conn.executemany(
                f"INSERT INTO annotations (paper_id, {column}, updated_at) VALUES (?, ?, ?) "  # noqa: S608  # nosec B608  # fixed column names
                f"ON CONFLICT (paper_id) DO UPDATE SET {column} = excluded.{column}, "
                "updated_at = excluded.updated_at",
                [(paper_id, value, self._stamp()) for paper_id in ids],
            )

    # ---- screening -----------------------------------------------------------

    def screen(
        self,
        paper_ids: Iterable[int],
        decision: str,
        *,
        reason: str = "",
        stage: str = STAGE_ABSTRACT,
    ) -> None:
        """Record a decision at one stage, replacing an earlier one there.

        An empty ``decision`` takes it back. A reason is required to exclude
        after reading the full text, which PRISMA asks to be reported.
        """
        if stage not in STAGES:
            raise ValueError(f"stage must be one of {', '.join(STAGES)}")
        if decision and decision not in DECISIONS:
            raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
        reason = " ".join(reason.split())
        if decision == DECISION_EXCLUDE and stage == STAGE_FULL_TEXT and not reason:
            raise ValueError("excluding a paper after reading it needs a reason")
        ids = self._existing(paper_ids)
        with self._lock, transaction(self._conn):
            for paper_id in ids:
                self._conn.execute(
                    "DELETE FROM screening WHERE paper_id = ? AND stage = ?", (paper_id, stage)
                )
                if decision:
                    self._conn.execute(
                        "INSERT INTO screening (paper_id, stage, decision, reason, decided_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (paper_id, stage, decision, reason, self._stamp()),
                    )

    # ---- deleting and merging --------------------------------------------------

    def delete(self, paper_ids: Iterable[int]) -> int:
        """Remove papers with everything recorded about them, return how many.

        A later search may add them again. To keep a paper out of a review,
        exclude it with :meth:`screen` instead.
        """
        ids = self._existing(paper_ids)
        with self._lock, transaction(self._conn):
            self._conn.executemany("DELETE FROM papers WHERE id = ?", [(i,) for i in ids])
        return len(ids)

    def merge(self, survivor: int, others: Iterable[int]) -> None:
        """Fold ``others`` into ``survivor``: fields, sightings, links, annotations.

        The survivor's own fields win, missing ones are filled in. Tags are
        joined, notes are put one after the other.

        Example: a preprint and its journal version that carry different DOIs
        are two papers to an import. ``merge(journal_id, [preprint_id])``
        makes them one, and both identifiers find it from then on.
        """
        ids = self._existing([survivor, *others])
        absorbed = [paper_id for paper_id in ids if paper_id != survivor]
        if not absorbed:
            raise ValueError("merging needs at least two different papers")
        with self._lock, transaction(self._conn):
            stored = self._load(survivor)
            for paper_id in absorbed:
                stored = merge_papers(stored, self._load(paper_id))
                self._absorb(paper_id, survivor)
            self._conn.execute(
                "UPDATE papers SET record = ?, title = ?, year = ? WHERE id = ?",
                (
                    json.dumps(stored.to_dict(), ensure_ascii=False, sort_keys=True),
                    stored.title,
                    stored.year,
                    survivor,
                ),
            )
            self._claim_keys(survivor, stored)

    def _move_annotations(self, absorbed: int, survivor: int) -> None:
        """Carry the reader's records over when one row is folded into another."""
        conn = self._conn
        conn.execute(
            "INSERT OR IGNORE INTO tags (paper_id, tag) SELECT ?, tag FROM tags "
            "WHERE paper_id = ?",
            (survivor, absorbed),
        )
        conn.execute(
            "INSERT OR IGNORE INTO screening (paper_id, stage, decision, reason, decided_at) "
            "SELECT ?, stage, decision, reason, decided_at FROM screening WHERE paper_id = ?",
            (survivor, absorbed),
        )
        rows = dict(
            (int(paper_id), (status, note))
            for paper_id, status, note in conn.execute(
                "SELECT paper_id, status, note FROM annotations WHERE paper_id IN (?, ?)",
                (survivor, absorbed),
            )
        )
        if absorbed not in rows:
            return
        status, note = rows.get(survivor, (READING_UNREAD, ""))
        other_status, other_note = rows[absorbed]
        # The further of the two: a paper read under one name has been read.
        status = max(status, other_status, key=READING_STATUSES.index)
        notes = [text for text in (note, other_note) if text]
        conn.execute(
            "INSERT INTO annotations (paper_id, status, note, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (paper_id) DO UPDATE SET status = excluded.status, "
            "note = excluded.note, updated_at = excluded.updated_at",
            (survivor, status, "\n\n".join(dict.fromkeys(notes)), self._stamp()),
        )

    def duplicate_candidates(self) -> list[tuple[int, ...]]:
        """Groups of papers that look like one, for a person to decide on.

        Imports already merge what shares a DOI, an arXiv ID or title, author
        and year. What is left are near misses: a preprint and its journal
        version, a title with and without its subtitle. Titles are compared
        by their words, so this needs no network.
        """
        with self._lock:
            rows = self._conn.execute("SELECT id, title FROM papers ORDER BY id").fetchall()
        words = [(int(i), frozenset(_WORD.findall(title.casefold()))) for i, title in rows]
        words = [(i, w) for i, w in words if len(w) >= _SHORTEST_TITLE]
        by_word: dict[str, list[int]] = {}
        for index, (_paper_id, bag) in enumerate(words):
            for word in bag:
                by_word.setdefault(word, []).append(index)
        parent = list(range(len(words)))

        def root(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for index, (_paper_id, bag) in enumerate(words):
            # Only papers sharing the rarest word are compared.
            rarest = min(bag, key=lambda word: len(by_word[word]))
            for other in by_word[rarest]:
                if other != index and _overlap(bag, words[other][1]) >= _DUPLICATE_OVERLAP:
                    parent[root(max(index, other))] = root(min(index, other))
        groups: dict[int, list[int]] = {}
        for index, (paper_id, _bag) in enumerate(words):
            groups.setdefault(root(index), []).append(paper_id)
        return [tuple(group) for group in groups.values() if len(group) > 1]

    # ---- internals ----------------------------------------------------------------

    def _existing(self, paper_ids: Iterable[int]) -> list[int]:
        """The ids without repeats, or an error that names the ones not here."""
        ids = list(dict.fromkeys(int(paper_id) for paper_id in paper_ids))
        with self._lock:
            missing = [
                paper_id
                for paper_id in ids
                if self._conn.execute(
                    "SELECT 1 FROM papers WHERE id = ?", (paper_id,)
                ).fetchone() is None
            ]
        if missing:
            raise LibraryError(
                "no paper with id " + ", ".join(str(i) for i in missing) + " in the library"
            )
        return ids


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """Shared words over all words of the two titles."""
    return len(a & b) / len(a | b)


def matches_filter(
    annotation: Annotation,
    *,
    tags: Sequence[str] = (),
    status: str = "",
    decision: str = "",
    stage: str = STAGE_ABSTRACT,
) -> bool:
    """Whether a paper passes the reader's filter. An empty criterion passes all.

    ``decision="none"`` asks for the papers still without one at ``stage``.
    """
    own = {tag.casefold() for tag in annotation.tags}
    if any(tag.casefold() not in own for tag in tags):
        return False
    if status and annotation.status != status:
        return False
    if decision:
        return (annotation.decision(stage) or "none") == decision
    return True


def screening_by_reason(
    annotations: Mapping[int, Annotation], stage: str
) -> dict[str, int]:
    """How many papers were excluded at ``stage`` for each reason."""
    counts: dict[str, int] = {}
    for annotation in annotations.values():
        for entry in annotation.screening:
            if entry.stage == stage and entry.decision == DECISION_EXCLUDE:
                counts[entry.reason] = counts.get(entry.reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))

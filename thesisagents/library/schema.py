"""Schema of the literature library and how it changes between versions.

The version lives in SQLite's own ``PRAGMA user_version``, and
``PRAGMA application_id`` marks the file as a ThesisAgents library. Opening a
library goes through :func:`prepare`, which leaves the database in exactly one
of three states: brought up to :data:`SCHEMA_VERSION`, already there, or
rejected with a ``LibraryError`` that says why.

Changing the schema means appending one function to :data:`MIGRATIONS`. The
function at index ``n`` upgrades a database from version ``n`` to ``n + 1``,
so the list is also the history. Never edit a migration that has shipped:
libraries in the field have already run it.

Tables (version 1)
------------------
``papers``         one row per distinct paper: its ``Paper.to_dict()`` record
                   (bibliographic fields, field provenance, summary), and when
                   it was first and last seen.
``identity_keys``  every key a paper is known by (DOI, arXiv ID, title hash),
                   pointing at its row. This is what makes a repeated import a
                   merge instead of a duplicate.
``runs``           one row per import: when, what kind, the query, and what
                   each source returned.
``observations``   which run saw which paper, through which source, at what
                   rank, with what score and pruning recommendation.
``relations``      citation links between two stored papers, with the
                   provider and depth that found them.
``verifications``  the export preflight's verdict per DOI / URL, so an
                   identifier checked last week is not looked up again.

Added in version 2 (what the reader records, see ``curation.py``)
-----------------------------------------------------------------
``annotations``    reading status and note of a paper.
``tags``           the tags of a paper, one row each, compared without case.
``screening``      the decision of a systematic review per paper and stage.
``saved_searches`` named queries that can be run again (``saved.py``).

Version 3 adds no table. It stores the identity keys of every paper once
more, because the way they are formed changed: titles in other scripts keep
their letters, and a DOI is one whether or not it is written as a link.

Version 4 rebuilds ``papers`` with ``AUTOINCREMENT``, so the id of a deleted
paper is never given to another one. The rows keep their ids and every other
table keeps its rows.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from thesisagents.core.exceptions import LibraryError, ThesisAgentsError
from thesisagents.core.models import Paper

#: "THAG" in ASCII. Lets a library be told from any other SQLite file.
APPLICATION_ID: int = 0x54484147
SCHEMA_VERSION: int = 4


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One all-or-nothing write to the library.

    The boundary this guards: every write that touches more than one row (an
    import, a merge of two stored papers, a schema migration). The failure it
    prevents is a half-applied change, for example a paper row without its
    identity keys, which a later import could no longer recognise.

    ``BEGIN IMMEDIATE`` takes the write lock up front, so a second writer
    waits (up to the connection's busy timeout) instead of failing halfway
    through with "database is locked". Connections are opened in autocommit
    mode, which is why the transaction is spelled out here.

    Example::

        with transaction(conn):
            conn.execute("INSERT INTO runs ...")
            conn.execute("INSERT INTO observations ...")

    Inside another transaction it joins that one, so several edits can be
    made one (``Library.together``).
    """
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    body_finished = False
    try:
        yield conn
        body_finished = True
    finally:
        # ``finally`` also runs when the caller leaves early (an exception in
        # the ``with`` body, or the generator being closed), so no exit path
        # leaves the write lock held.
        conn.execute("COMMIT" if body_finished else "ROLLBACK")


_VERSION_1: tuple[str, ...] = (
    """
    CREATE TABLE papers (
        id INTEGER PRIMARY KEY,
        record TEXT NOT NULL,
        title TEXT NOT NULL,
        year INTEGER,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE identity_keys (
        key TEXT PRIMARY KEY,
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX identity_keys_paper ON identity_keys(paper_id)",
    """
    CREATE TABLE runs (
        id INTEGER PRIMARY KEY,
        started_at TEXT NOT NULL,
        kind TEXT NOT NULL,
        keywords TEXT NOT NULL,
        query TEXT NOT NULL,
        source_stats TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE observations (
        run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        rank INTEGER,
        score TEXT,
        recommendation TEXT,
        PRIMARY KEY (run_id, paper_id)
    )
    """,
    "CREATE INDEX observations_paper ON observations(paper_id)",
    """
    CREATE TABLE relations (
        source_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        target_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        relation TEXT NOT NULL,
        provider TEXT NOT NULL,
        depth INTEGER NOT NULL,
        run_id INTEGER REFERENCES runs(id) ON DELETE SET NULL,
        PRIMARY KEY (source_id, target_id, relation)
    )
    """,
    "CREATE INDEX relations_target ON relations(target_id)",
    """
    CREATE TABLE verifications (
        kind TEXT NOT NULL,
        value TEXT NOT NULL,
        status TEXT NOT NULL,
        resolved_url TEXT,
        detail TEXT NOT NULL,
        checked_at TEXT NOT NULL,
        PRIMARY KEY (kind, value)
    )
    """,
)


def _create_version_1(conn: sqlite3.Connection) -> None:
    # One statement per execute(): ``executescript`` commits any open
    # transaction first, which would take the migration out of the
    # transaction that makes it all-or-nothing.
    for statement in _VERSION_1:
        conn.execute(statement)


_VERSION_2: tuple[str, ...] = (
    """
    CREATE TABLE annotations (
        paper_id INTEGER PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
        status TEXT NOT NULL DEFAULT 'unread',
        note TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE tags (
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        tag TEXT NOT NULL COLLATE NOCASE,
        PRIMARY KEY (paper_id, tag)
    )
    """,
    "CREATE INDEX tags_tag ON tags(tag)",
    """
    CREATE TABLE screening (
        paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
        stage TEXT NOT NULL,
        decision TEXT NOT NULL,
        reason TEXT NOT NULL,
        decided_at TEXT NOT NULL,
        PRIMARY KEY (paper_id, stage)
    )
    """,
    """
    CREATE TABLE saved_searches (
        name TEXT PRIMARY KEY COLLATE NOCASE,
        query TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_run_at TEXT,
        last_new INTEGER
    )
    """,
)


def _add_version_2(conn: sqlite3.Connection) -> None:
    for statement in _VERSION_2:
        conn.execute(statement)


def _add_version_3(conn: sqlite3.Connection) -> None:
    """Give every paper the identity keys it would get today, beside the old ones.

    The failure this prevents: a paper with a Chinese title and no DOI was
    stored under a key made of the title's ASCII letters. Importing the same
    file again would store it once more. A key another paper owns is left
    with its owner, and a record that cannot be read keeps its old keys.
    """
    for paper_id, record in conn.execute("SELECT id, record FROM papers").fetchall():
        try:
            keys = Paper.from_dict(json.loads(record)).identity_keys()
        except (ThesisAgentsError, ValueError, KeyError, TypeError, AttributeError):
            continue
        conn.executemany(
            "INSERT OR IGNORE INTO identity_keys (key, paper_id) VALUES (?, ?)",
            [(key, paper_id) for key in keys],
        )


_VERSION_4: tuple[str, ...] = (
    """
    CREATE TABLE papers_v4 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record TEXT NOT NULL,
        title TEXT NOT NULL,
        year INTEGER,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL
    )
    """,
    "INSERT INTO papers_v4 (id, record, title, year, first_seen, last_seen) "
    "SELECT id, record, title, year, first_seen, last_seen FROM papers",
    "DROP TABLE papers",
    # The other tables name ``papers`` in their REFERENCES clauses, and after
    # the rename that name is this table again.
    "ALTER TABLE papers_v4 RENAME TO papers",
)


def _add_version_4(conn: sqlite3.Connection) -> None:
    """Rebuild ``papers`` so that an id, once given out, is never given again.

    The failure this prevents: ``INTEGER PRIMARY KEY`` hands out the highest
    id plus one, so after the paper with the highest id was deleted, the next
    import got its id. A note, tag or deletion sent with the old id (a CLI
    command typed from an earlier listing, an MCP agent holding a search
    result) then landed on another paper. ``AUTOINCREMENT`` keeps the highest
    id ever used in ``sqlite_sequence`` and never goes below it.

    SQLite cannot add ``AUTOINCREMENT`` to an existing table, so the table is
    copied with its ids into a new one, the old one dropped and the new one
    renamed (the order SQLite's documentation gives for changing a table).
    Dropping ``papers`` with foreign keys enforced would delete every row
    that refers to it, which is why :func:`prepare` turns enforcement off
    for an upgrade and this function refuses to run with it on. An id that
    was deleted before the upgrade and was higher than every id left is not
    known to the file any more, so it can still be given out once.
    """
    if conn.execute("PRAGMA foreign_keys").fetchone()[0]:
        raise LibraryError(
            "the library cannot be upgraded while foreign keys are enforced: "
            "rebuilding the papers table would delete what refers to it"
        )
    for statement in _VERSION_4:
        conn.execute(statement)


#: ``MIGRATIONS[n]`` upgrades a database from version ``n`` to ``n + 1``.
MIGRATIONS: tuple[Callable[[sqlite3.Connection], None], ...] = (
    _create_version_1,
    _add_version_2,
    _add_version_3,
    _add_version_4,
)


def prepare(conn: sqlite3.Connection, path: str) -> int:
    """Bring ``conn`` to the current schema, or refuse it. Returns the version.

    The boundary this guards: the first read of a file the user pointed at.
    The failure it prevents is reading or writing a database whose tables do
    not mean what this code assumes, either because the file is something
    else entirely or because a newer ThesisAgents changed the layout.

    Each migration runs in one transaction together with the version bump
    (SQLite's schema changes and both PRAGMAs are transactional), so an
    upgrade that fails halfway leaves the previous version intact. ``conn``
    must be in autocommit mode (``isolation_level=None``).

    Foreign keys are not enforced while migrations run, and enforcement is
    restored afterwards. A migration that rebuilds a table drops the old one,
    and with enforcement on that drop deletes every row referring to it.
    PRAGMA foreign_keys has no effect inside a transaction, so it is set
    here, before each migration's transaction begins.

    Example: a fresh file ends at version 4. A file that says version 9 raises
    ``LibraryError`` naming both numbers.
    """
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        application = conn.execute("PRAGMA application_id").fetchone()[0]
        tables = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]
    except sqlite3.DatabaseError as err:
        raise LibraryError(
            f"{path} is not an SQLite database ({err}). Point --library at "
            "another file. A new file is created when the path does not exist."
        ) from err
    if version == 0 and tables:
        raise LibraryError(
            f"{path} is an SQLite database, but not a ThesisAgents library "
            "(it has tables and no library schema version). Point --library "
            "at another file."
        )
    if version and application != APPLICATION_ID:
        raise LibraryError(
            f"{path} is an SQLite database of another application "
            f"(application_id {application}). Point --library at another file."
        )
    if version > SCHEMA_VERSION:
        raise LibraryError(
            f"{path} has library schema version {version}, and this "
            f"ThesisAgents understands up to version {SCHEMA_VERSION}. It was "
            "written by a newer release: upgrade ThesisAgents, or point "
            "--library at another file."
        )
    if version >= SCHEMA_VERSION:
        return version
    enforced = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        return _migrate(conn, version)
    finally:
        if enforced:
            conn.execute("PRAGMA foreign_keys = ON")


def _migrate(conn: sqlite3.Connection, version: int) -> int:
    """Run the migrations from ``version`` on, each in its own transaction."""
    while version < SCHEMA_VERSION:
        with transaction(conn):
            # Read again under the write lock: another process may have
            # upgraded the file while this one waited, and creating the
            # same tables twice fails.
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version >= SCHEMA_VERSION:
                break
            MIGRATIONS[version](conn)
            version += 1
            # PRAGMA values cannot be bound as parameters. Both are integers
            # defined in this module, never user input.
            conn.execute(f"PRAGMA application_id = {APPLICATION_ID:d}")
            conn.execute(f"PRAGMA user_version = {version:d}")
    return version

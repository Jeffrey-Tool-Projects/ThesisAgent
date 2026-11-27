"""``thesisagents library``: what a reader does with a literature library.

The ``--library…`` flags of the main command fill a library and read it back.
This subcommand edits it: tags, notes, reading status, screening, duplicates,
importing a bibliography, saved searches and the PRISMA flow.

Example::

    thesisagents library thesis.db list --tag "chapter 2"
    thesisagents library thesis.db tag 3 7 --add "chapter 2"
    thesisagents library thesis.db screen 7 exclude --reason "not peer reviewed"
    thesisagents library thesis.db prisma --svg prisma.svg
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from thesisagents.core.bib_import import read_bibliography
from thesisagents.core.constants import DEFAULT_SOURCES
from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Query
from thesisagents.core.query import normalize_query
from thesisagents.library import (
    DECISIONS,
    READING_STATUSES,
    STAGES,
    Library,
    LibraryEntry,
    prisma_flow,
    prisma_svg,
    run_saved_search,
)

_STAGE_HELP = "Screening stage (default: title_abstract)."


def build_parser() -> argparse.ArgumentParser:
    """The parser of ``thesisagents library``."""
    parser = argparse.ArgumentParser(
        prog="thesisagents library",
        description="Edit a literature library: tags, notes, screening, duplicates, imports.",
    )
    parser.add_argument("library", help="The library file (see --library of the main command).")
    actions = parser.add_subparsers(dest="action", required=True)

    listing = actions.add_parser("list", help="List papers, optionally filtered.")
    listing.add_argument("query", nargs="?", default="", help="Words to look for.")
    listing.add_argument("--tag", action="append", default=[], help="Only papers with this tag.")
    listing.add_argument("--status", choices=READING_STATUSES, default="")
    listing.add_argument("--decision", choices=(*DECISIONS, "none"), default="")
    listing.add_argument("--stage", choices=STAGES, default=STAGES[0], help=_STAGE_HELP)
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--json", action="store_true", help="Print JSON.")

    show = actions.add_parser("show", help="Show one paper with everything recorded.")
    show.add_argument("id", type=int)

    tag = actions.add_parser("tag", help="Add and remove tags.")
    tag.add_argument("ids", type=int, nargs="+")
    tag.add_argument("--add", action="append", default=[], metavar="TAG")
    tag.add_argument("--remove", action="append", default=[], metavar="TAG")

    note = actions.add_parser("note", help="Replace a paper's note (empty text removes it).")
    note.add_argument("id", type=int)
    note.add_argument("text")

    status = actions.add_parser("status", help="Set the reading status.")
    status.add_argument("status", choices=READING_STATUSES)
    status.add_argument("ids", type=int, nargs="+")

    screen = actions.add_parser("screen", help="Record a screening decision.")
    screen.add_argument("ids", type=int, nargs="+")
    screen.add_argument("decision", choices=(*DECISIONS, "undo"))
    screen.add_argument("--reason", default="")
    screen.add_argument("--stage", choices=STAGES, default=STAGES[0], help=_STAGE_HELP)

    delete = actions.add_parser("delete", help="Remove papers from the library.")
    delete.add_argument("ids", type=int, nargs="+")
    delete.add_argument("--yes", action="store_true", help="Do not ask.")

    actions.add_parser("duplicates", help="List papers that look like one.")
    merge = actions.add_parser("merge", help="Fold papers into the first one.")
    merge.add_argument("ids", type=int, nargs="+")

    importing = actions.add_parser("import", help="Add the papers of a .bib or .ris file.")
    importing.add_argument("file")
    importing.add_argument("--tag", action="append", default=[], help="Tag what was imported.")

    save = actions.add_parser("save-search", help="Save a query to run again.")
    save.add_argument("name")
    save.add_argument("query")
    save.add_argument("--source", default=",".join(DEFAULT_SOURCES), help="Comma separated.")
    save.add_argument("--max", type=int, default=25)
    save.add_argument("--year-from", type=int)
    save.add_argument("--year-to", type=int)
    actions.add_parser("searches", help="List saved searches.")
    run = actions.add_parser("run-search", help="Run a saved search, print what is new.")
    run.add_argument("name")
    drop = actions.add_parser("delete-search", help="Forget a saved search.")
    drop.add_argument("name")

    prisma = actions.add_parser("prisma", help="Print the PRISMA flow.")
    prisma.add_argument("--svg", metavar="FILE", help="Also draw it into an SVG file.")
    return parser


def main(argv: Sequence[str]) -> int:
    """Run ``thesisagents library ARGV``. Returns the exit code."""
    args = build_parser().parse_args(list(argv))
    # Only an import may create the file. A mistyped path says so elsewhere.
    create = args.action in {"import", "save-search"}
    try:
        with Library(args.library, create=create) as library:
            return _ACTIONS[args.action](library, args)
    except (ThesisAgentsError, ValueError, OSError, sqlite3.Error) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


# --- actions -----------------------------------------------------------------


def _list(library: Library, args: argparse.Namespace) -> int:
    entries = library.search(
        normalize_query(args.query) if args.query.strip() else "",
        limit=args.limit, tags=args.tag, status=args.status,
        decision=args.decision, stage=args.stage,
    )
    if args.json:
        print(json.dumps([entry.to_dict() for entry in entries], ensure_ascii=False, indent=2))
        return 0
    for entry in entries:
        print(_line(entry))
    print(f"{len(entries)} paper(s)")
    return 0


def _line(entry: LibraryEntry) -> str:
    author = entry.paper.authors[0] if entry.paper.authors else "?"
    extra = [entry.status] + [f"#{tag}" for tag in entry.tags]
    extra += [f"{s.stage}:{s.decision}" for s in entry.screening]
    return (
        f"  [{entry.paper_id:>4}] ({entry.paper.year or 'n.d.'}) {author}: "
        f"{entry.paper.title}  {{{', '.join(extra)}}}"
    )


def _show(library: Library, args: argparse.Namespace) -> int:
    for entry in library.entries():
        if entry.paper_id == args.id:
            print(_line(entry))
            for label, value in (
                ("DOI", entry.paper.doi), ("URL", entry.paper.url), ("Venue", entry.paper.venue),
                ("Sources", ", ".join(entry.sources)), ("Note", entry.note),
                ("Abstract", entry.paper.abstract),
            ):
                if value:
                    print(f"  {label}: {value}")
            for decision in entry.screening:
                print(f"  {decision.stage}: {decision.decision} {decision.reason}".rstrip())
            return 0
    print(f"error: no paper with id {args.id}", file=sys.stderr)
    return 2


def _tag(library: Library, args: argparse.Namespace) -> int:
    if not args.add and not args.remove:
        raise ValueError("give at least one --add or --remove")
    if args.add:
        library.add_tags(args.ids, args.add)
    if args.remove:
        library.remove_tags(args.ids, args.remove)
    return _done(args.ids)


def _note(library: Library, args: argparse.Namespace) -> int:
    library.set_note(args.id, args.text)
    return _done([args.id])


def _status(library: Library, args: argparse.Namespace) -> int:
    library.set_reading_status(args.ids, args.status)
    return _done(args.ids)


def _screen(library: Library, args: argparse.Namespace) -> int:
    decision = "" if args.decision == "undo" else args.decision
    library.screen(args.ids, decision, reason=args.reason, stage=args.stage)
    return _done(args.ids)


def _delete(library: Library, args: argparse.Namespace) -> int:
    if not args.yes and not _confirmed(f"Delete {len(args.ids)} paper(s) from the library?"):
        print("Nothing deleted.")
        return 1
    print(f"{library.delete(args.ids)} paper(s) deleted")
    return 0


def _confirmed(question: str) -> bool:
    try:
        return input(f"{question} [y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def _duplicates(library: Library, _args: argparse.Namespace) -> int:
    titles = {entry.paper_id: _line(entry) for entry in library.entries()}
    groups = library.duplicate_candidates()
    for group in groups:
        for paper_id in group:
            print(titles[paper_id])
        print(f"  merge with: thesisagents library … merge {' '.join(map(str, group))}\n")
    print(f"{len(groups)} group(s)")
    return 0


def _merge(library: Library, args: argparse.Namespace) -> int:
    library.merge(args.ids[0], args.ids[1:])
    return _done(args.ids[:1])


def _import(library: Library, args: argparse.Namespace) -> int:
    result = read_bibliography(args.file)
    if result.papers:
        # One change: a refused tag must not leave the papers and the run
        # record behind, where a second try would count the run twice.
        with library.together():
            report = library.add_papers(
                result.papers, keywords=Path(args.file).name, kind="import"
            )
            if args.tag:
                library.add_tags(library.ids_of(result.papers), args.tag)
        print(f"{report.added} added, {report.merged} already in the library")
    for reason in result.skipped:
        print(f"skipped, {reason}", file=sys.stderr)
    return 0 if result.papers else 2


def _save_search(library: Library, args: argparse.Namespace) -> int:
    sources = tuple(name.strip() for name in args.source.split(",") if name.strip())
    library.save_search(
        args.name,
        Query(
            keywords=normalize_query(args.query), sources=sources, max_results=args.max,
            year_from=args.year_from, year_to=args.year_to,
        ),
    )
    print(f"saved {args.name!r}")
    return 0


def _searches(library: Library, _args: argparse.Namespace) -> int:
    for saved in library.saved_searches():
        last = (saved.last_run_at or "never run")[:16].replace("T", " ")
        new = "" if saved.last_new is None else f", {saved.last_new} new"
        print(f"  {saved.name}: {saved.query.keywords} ({last}{new})")
    return 0


def _run_search(library: Library, args: argparse.Namespace) -> int:
    outcome = asyncio.run(_run_and_close(library, args.name))
    for paper in outcome.new_papers:
        author = paper.authors[0] if paper.authors else "?"
        print(f"  ({paper.year or 'n.d.'}) {author}: {paper.title}  {paper.url}")
    print(f"{len(outcome.new_papers)} new of {len(outcome.collection.papers)} found")
    return 0


async def _run_and_close(library: Library, name: str):
    from thesisagents.fetchers.http import shutdown_clients

    try:
        return await run_saved_search(library, name)
    finally:
        await shutdown_clients()


def _delete_search(library: Library, args: argparse.Namespace) -> int:
    library.delete_saved_search(args.name)
    print(f"deleted {args.name!r}")
    return 0


def _prisma(library: Library, args: argparse.Namespace) -> int:
    if args.svg and Path(args.svg).suffix.lower() != ".svg":
        # The file is overwritten, so a mistyped path must not be the library.
        raise ValueError(f"--svg needs a path that ends with .svg, not {args.svg}")
    flow = prisma_flow(library)
    print(json.dumps(flow.to_dict(), ensure_ascii=False, indent=2))
    if args.svg:
        target = Path(args.svg)
        try:
            target.write_text(prisma_svg(flow), encoding="utf-8")
        except OSError as err:
            raise ThesisAgentsError(f"cannot write {target}: {err}") from err
        print(f"drawn to {target.resolve()}", file=sys.stderr)
    return 0


def _done(ids: Sequence[int]) -> int:
    print(f"{len(ids)} paper(s) updated")
    return 0


_ACTIONS: dict[str, Callable[[Library, argparse.Namespace], int]] = {
    "list": _list,
    "show": _show,
    "tag": _tag,
    "note": _note,
    "status": _status,
    "screen": _screen,
    "delete": _delete,
    "duplicates": _duplicates,
    "merge": _merge,
    "import": _import,
    "save-search": _save_search,
    "searches": _searches,
    "run-search": _run_search,
    "delete-search": _delete_search,
    "prisma": _prisma,
}

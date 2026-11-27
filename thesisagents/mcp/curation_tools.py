"""MCP tools that edit a literature library.

``library_tools.py`` fills a library and reads it. These tools record what
was decided about the papers: tags, notes, reading status, screening,
duplicates, plus importing a bibliography, saved searches and the PRISMA
flow. Papers are named by the ``paper_id`` that ``library_search`` returns.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from thesisagents.core.bib_import import read_bibliography
from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Query
from thesisagents.core.query import normalize_query
from thesisagents.library import Library, prisma_flow, prisma_svg, run_saved_search

_SAVED_ACTIONS = ("list", "save", "run", "delete")


def register_curation_tools(tool: Callable[[Callable[..., Any]], Any]) -> None:
    """Register the tools through ``tool`` (``server._tool(server)``)."""
    _register_update(tool)
    _register_editing(tool)
    _register_duplicates(tool)
    _register_review(tool)


def _register_update(tool: Callable[[Callable[..., Any]], Any]) -> None:
    @tool
    def library_update(
        library: str,
        paper_ids: list[int],
        add_tags: list[str] | None = None,
        remove_tags: list[str] | None = None,
        status: str | None = None,
        note: str | None = None,
        decision: str | None = None,
        reason: str = "",
        stage: str = "title_abstract",
    ) -> dict[str, Any]:
        """Record what a reader decided about papers of a library.

        Every argument left out is left alone. ``status`` is ``unread``,
        ``reading`` or ``read``. ``note`` replaces the note and applies to one
        paper at a time. ``decision`` is a screening decision (``include``,
        ``maybe``, ``exclude``, or an empty string to take one back) at
        ``stage`` ``title_abstract`` or ``full_text``. Excluding at
        ``full_text`` needs a ``reason``.

        Screening is a judgement the user is responsible for: propose
        decisions and apply them when the user agrees.
        """
        if note is not None and len(paper_ids) != 1:
            raise ThesisAgentsError("a note applies to exactly one paper")
        try:
            with Library(library, create=False) as store:
                with store.together():
                    store.add_tags(paper_ids, add_tags or ())
                    store.remove_tags(paper_ids, remove_tags or ())
                    if status is not None:
                        store.set_reading_status(paper_ids, status)
                    if note is not None:
                        store.set_note(paper_ids[0], note)
                    if decision is not None:
                        store.screen(paper_ids, decision, reason=reason, stage=stage)
                wanted = set(paper_ids)
                return {
                    "papers": [
                        {"title": e.paper.title, **_record(e.to_dict())}
                        for e in store.entries()
                        if e.paper_id in wanted
                    ],
                    "tags": store.tags(),
                }
        except ValueError as err:
            raise ThesisAgentsError(str(err)) from err


def _register_editing(tool: Callable[[Callable[..., Any]], Any]) -> None:
    @tool
    def library_delete(library: str, paper_ids: list[int]) -> dict[str, Any]:
        """Remove papers and everything recorded about them from a library.

        This cannot be undone, so ask the user first. To keep a paper out of
        a review, exclude it with ``library_update`` instead: the decision
        survives the next search, a deletion does not.
        """
        with Library(library, create=False) as store:
            return {"deleted": store.delete(paper_ids), "total": len(store)}

    @tool
    def library_import(library: str, file: str, tags: list[str] | None = None) -> dict[str, Any]:
        """Add the papers of a BibTeX (.bib) or RIS (.ris) file to a library.

        For taking over a Zotero, Mendeley, EndNote or JabRef collection. A
        paper already held is updated, not duplicated. ``skipped`` says why a
        record was left out. ``tags`` are put on every imported paper. When
        a tag is refused, nothing of the file is imported.
        """
        result = read_bibliography(file)
        if not result.papers:
            raise ThesisAgentsError("no usable record: " + "; ".join(result.skipped[:5]))
        with Library(library) as store:
            # One change: a refused tag must not leave the papers and the run
            # record behind, where a second try would count the run twice.
            try:
                with store.together():
                    report = store.add_papers(result.papers, keywords=file, kind="import")
                    if tags:
                        store.add_tags(store.ids_of(result.papers), tags)
            except ValueError as err:
                raise ThesisAgentsError(str(err)) from err
            return {**report.to_dict(), "skipped": list(result.skipped)}


def _register_duplicates(tool: Callable[[Callable[..., Any]], Any]) -> None:
    @tool
    def library_duplicates(library: str) -> dict[str, Any]:
        """Groups of papers in a library that look like one.

        Imports already merge what shares an identifier. These are near
        misses, such as a preprint and its journal version. Compare them
        before calling ``library_merge``: similar titles can be two papers.
        """
        with Library(library, create=False) as store:
            by_id = {e.paper_id: e.paper for e in store.entries()}
            return {
                "groups": [
                    [
                        {
                            "paper_id": i, "title": by_id[i].title, "year": by_id[i].year,
                            "authors": list(by_id[i].authors[:3]), "doi": by_id[i].doi,
                            "venue": by_id[i].venue,
                        }
                        for i in group
                    ]
                    for group in store.duplicate_candidates()
                ]
            }

    @tool
    def library_merge(library: str, survivor: int, others: list[int]) -> dict[str, Any]:
        """Fold papers into one. The survivor's fields win, gaps are filled.

        Tags, notes and decisions are joined. This cannot be undone.
        """
        try:
            with Library(library, create=False) as store:
                store.merge(survivor, others)
                entry = next(e for e in store.entries() if e.paper_id == survivor)
                return {"paper": entry.to_dict(), "total": len(store)}
        except ValueError as err:
            raise ThesisAgentsError(str(err)) from err


def _register_review(tool: Callable[[Callable[..., Any]], Any]) -> None:
    @tool
    async def library_saved_search(
        library: str,
        action: str = "list",
        name: str = "",
        keywords: str = "",
        sources: list[str] | None = None,
        max_results: int = 25,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict[str, Any]:
        """Save a search in a library, and run it again to see only what is new.

        ``action`` is ``list``, ``save`` (with ``name`` and ``keywords``),
        ``run`` or ``delete`` (with ``name``). ``run`` adds what it finds and
        returns the papers the library did not hold before. The VPN rule of
        ``search`` applies to ``sources`` too.
        """
        if action not in _SAVED_ACTIONS:
            raise ThesisAgentsError(f"action must be one of {', '.join(_SAVED_ACTIONS)}")
        try:
            with Library(library, create=action == "save") as store:
                if action == "save":
                    from thesisagents.core.constants import DEFAULT_SOURCES

                    store.save_search(
                        name,
                        Query(
                            keywords=normalize_query(keywords),
                            sources=tuple(sources or DEFAULT_SOURCES),
                            max_results=max_results, year_from=year_from, year_to=year_to,
                        ),
                    )
                elif action == "delete":
                    store.delete_saved_search(name)
                elif action == "run":
                    outcome = await run_saved_search(store, name)
                    return {
                        "name": outcome.name,
                        "found": len(outcome.collection.papers),
                        "new": [paper.to_dict() for paper in outcome.new_papers],
                    }
                return {"searches": [s.to_dict() for s in store.saved_searches()]}
        except ValueError as err:
            raise ThesisAgentsError(str(err)) from err

    @tool
    def library_prisma(library: str, svg_path: str | None = None) -> dict[str, Any]:
        """The PRISMA 2020 flow of a library: found, screened, included.

        Counts what was recorded, nothing is estimated. ``svg_path`` also
        draws the diagram into that file, which must end with ``.svg``.
        """
        with Library(library, create=False) as store:
            flow = prisma_flow(store)
        result = flow.to_dict()
        if svg_path:
            _write_svg(svg_path, prisma_svg(flow))
            result["svg"] = svg_path
        return result


def _write_svg(path: str, drawing: str) -> None:
    """Write ``drawing``, into a path that ends with ``.svg`` only.

    The boundary this guards: the file is overwritten without asking, and a
    mixed-up argument must not be the library itself.

    Example: ``_write_svg("thesis.db", drawing)`` raises.
    """
    target = Path(path)
    if target.suffix.lower() != ".svg":
        raise ThesisAgentsError(f"cannot write {path}: it does not end with .svg")
    try:
        target.write_text(drawing, encoding="utf-8")
    except OSError as err:
        raise ThesisAgentsError(f"cannot write {path}: {err}") from err


def _record(entry: dict[str, Any]) -> dict[str, Any]:
    """What the reader recorded, without the paper's abstract and summary."""
    return {
        key: entry[key]
        for key in ("paper_id", "tags", "status", "note", "screening")
    }

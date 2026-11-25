"""Make the relevance judgements a search benchmark needs.

A benchmark is worth as much as the person who judged it, so this tool does
the rest: it runs the queries once, keeps what came back, and shows one paper
at a time to grade. Papers are shown in random order and without their rank
or source, because a judge who sees rank 1 tends to agree with it. Every
grade is saved at once, so judging can stop and go on later.

The file it writes is the one ``search_quality`` evaluates, with the papers'
titles and abstracts beside the judgements.

Example::

    py -m thesisagents.evaluation.judge collect bench.json --queries queries.txt
    py -m thesisagents.evaluation.judge grade bench.json
    py -m thesisagents.evaluation.search_quality bench.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Final

from thesisagents.core.constants import DEFAULT_SOURCES
from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.core.query import normalize_query

GRADES: Final[tuple[str, ...]] = ("0", "1", "2")
_ABSTRACT_CHARS: Final[int] = 1200


def paper_identifier(paper: Paper) -> str:
    """The id a benchmark names a paper by: DOI, arXiv id, else the title key."""
    if paper.doi:
        return paper.doi.lower().strip()
    if paper.arxiv_id:
        return paper.arxiv_key() or ""
    return paper.title_key()


def query_identifier(keywords: str) -> str:
    """``"LLM code review"`` as ``"llm-code-review"``."""
    return re.sub(r"[^\w]+", "-", keywords.casefold()).strip("-") or "query"


async def collect(
    payload: dict[str, Any],
    keywords: Sequence[str],
    *,
    sources: Sequence[str],
    max_results: int,
    search: Callable[[Query], Awaitable[PaperCollection]],
) -> dict[str, Any]:
    """Run every query and put what it returned into ``payload``.

    Running again refreshes the ranking and keeps the judgements: they belong
    to the query, not to one ranking of it.
    """
    queries = {entry["id"]: entry for entry in payload.setdefault("queries", [])}
    papers = payload.setdefault("papers", {})
    for text in keywords:
        normalised = normalize_query(text)
        collection = await search(
            Query(keywords=normalised, sources=tuple(sources), max_results=max_results)
        )
        identifier = query_identifier(normalised)
        entry = queries.get(identifier)
        if entry is None:
            entry = {"id": identifier, "relevance": {}}
            queries[identifier] = entry
            payload["queries"].append(entry)
        entry["keywords"] = normalised
        entry["retrieved"] = list(
            dict.fromkeys(paper_identifier(paper) for paper in collection.papers)
        )
        for paper in collection.papers:
            papers[paper_identifier(paper)] = {
                "title": paper.title,
                "year": paper.year,
                "authors": list(paper.authors[:3]),
                "abstract": paper.abstract[:_ABSTRACT_CHARS],
            }
    return payload


def unjudged(payload: dict[str, Any], seed: int = 0) -> list[tuple[dict[str, Any], str]]:
    """``(query, paper id)`` pairs without a grade, query by query, papers shuffled.

    The same seed gives the same order, so going on later continues where the
    judge stopped.
    """
    pairs: list[tuple[dict[str, Any], str]] = []
    for entry in payload.get("queries", []):
        open_ids = [i for i in entry["retrieved"] if i not in entry["relevance"]]
        # A stable order per query: the papers left do not move when one is graded.
        order = random.Random(f"{seed}:{entry['id']}")  # noqa: S311  # nosec B311  # shuffling, not security
        ranked = sorted(entry["retrieved"])
        order.shuffle(ranked)
        pairs += [(entry, i) for i in ranked if i in set(open_ids)]
    return pairs


def grade(
    payload: dict[str, Any],
    *,
    ask: Callable[[str], str],
    show: Callable[[str], None],
    save: Callable[[dict[str, Any]], None],
    seed: int = 0,
) -> int:
    """Ask for a grade for every open pair. Returns how many were given.

    ``s`` skips a paper for now, ``u`` takes the last grade back, ``q`` stops.
    """
    given: list[tuple[dict[str, Any], str]] = []
    pending = unjudged(payload, seed)
    position = 0
    while position < len(pending):
        entry, identifier = pending[position]
        show(_card(payload, entry, identifier, position + 1, len(pending)))
        answer = ask("0 not relevant, 1 relevant, 2 cornerstone, s skip, u undo, q quit > ")
        answer = answer.strip().lower()
        if answer == "q":
            break
        if answer == "u" and given:
            last_entry, last = given.pop()
            del last_entry["relevance"][last]
            save(payload)
            position = pending.index((last_entry, last))
        elif answer == "s":
            position += 1
        elif answer in GRADES:
            entry["relevance"][identifier] = int(answer)
            given.append((entry, identifier))
            save(payload)
            position += 1
    return len(given)


def _card(
    payload: dict[str, Any], entry: dict[str, Any], identifier: str, number: int, total: int
) -> str:
    paper = payload.get("papers", {}).get(identifier, {})
    authors = ", ".join(paper.get("authors", ()))
    return (
        f"\n[{number}/{total}]  QUERY: {entry.get('keywords', entry['id'])}\n"
        f"{paper.get('title', identifier)}\n{authors} ({paper.get('year') or 'n.d.'})\n\n"
        f"{paper.get('abstract') or '(no abstract)'}\n"
    )


# --- files and command line ---------------------------------------------------


def load(path: Path, *, must_exist: bool) -> dict[str, Any]:
    if not path.exists() and not must_exist:
        return {"queries": [], "papers": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        # The three things the tool relies on, named when they are missing.
        for entry in payload["queries"]:
            entry["id"], entry["retrieved"], entry["relevance"]  # noqa: B018
            if not isinstance(entry["relevance"], dict):
                raise TypeError("relevance is not a mapping of id to grade")
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise ThesisAgentsError(f"{path} is not a benchmark file: {err!r}") from err
    return payload


def store(path: Path, payload: dict[str, Any]) -> None:
    """Write the file whole or not at all: a grade is work that cannot be redone."""
    temporary = path.with_name(f".{path.name}.saving")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thesisagents.evaluation.judge", description="Judge search results by hand."
    )
    actions = parser.add_subparsers(dest="action", required=True)
    collecting = actions.add_parser("collect", help="Run queries and keep what came back.")
    collecting.add_argument("benchmark")
    collecting.add_argument("--queries", required=True, help="A text file, one query per line.")
    collecting.add_argument("--source", default=",".join(DEFAULT_SOURCES))
    collecting.add_argument("--max", type=int, default=25)
    grading = actions.add_parser("grade", help="Grade papers one by one.")
    grading.add_argument("benchmark")
    grading.add_argument("--seed", type=int, default=0, help="Order in which papers are shown.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.benchmark)
    try:
        if args.action == "collect":
            return _collect(path, args)
        payload = load(path, must_exist=True)
        count = grade(
            payload, ask=input, show=print, save=lambda p: store(path, p), seed=args.seed
        )
    except EOFError:
        print("no terminal to ask on", file=sys.stderr)
        return 2
    except (ThesisAgentsError, ValueError, OSError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print(f"{count} graded, {len(unjudged(payload))} to go")
    return 0


def _collect(path: Path, args: argparse.Namespace) -> int:
    from thesisagents.core.pipeline import run_search
    from thesisagents.fetchers.http import shutdown_clients

    lines = Path(args.queries).read_text(encoding="utf-8").splitlines()
    keywords = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    sources = [name.strip() for name in args.source.split(",") if name.strip()]

    async def run() -> dict[str, Any]:
        try:
            return await collect(
                load(path, must_exist=False), keywords,
                sources=sources, max_results=args.max, search=run_search,
            )
        finally:
            await shutdown_clients()

    payload = asyncio.run(run())
    store(path, payload)
    print(f"{len(keywords)} queries, {len(unjudged(payload))} papers to grade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

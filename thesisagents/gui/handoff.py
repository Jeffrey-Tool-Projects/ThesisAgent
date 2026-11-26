"""Hand enrichment to an LLM agent and take its summaries back (``progress.md`` #27).

The boundary this guards: the Enrich page without an Anthropic API key.
Before this module the page only said "set ANTHROPIC_API_KEY", although the
project's main no-key flow is the LLM-as-agent path, where an MCP-aware LLM
reads each PDF and authors the ``PaperSummary`` itself (the
``paper-summary-author`` subagent). The GUI had no way to give such an agent
the papers or to take its work back.

The hand-off is one JSON file:

* :func:`write_handoff` writes the papers (with their PDF links), the deck
  language, an empty summary showing every field, and plain instructions;
* the agent fills ``papers[i].paper.summary`` in place and saves the file;
* :func:`read_handoff` reads it back and attaches each summary to the paper
  with the same ``key`` (``Paper.dedup_key()``), so a reordered or shortened
  file still lands on the right papers.

Example::

    write_handoff(collection, "handoff.json", language="zh-tw")
    # ... the agent fills in the summaries ...
    result = read_handoff("handoff.json", collection)
    result.collection.papers[0].summary.research_question
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary

HANDOFF_FORMAT: Final[str] = "thesisagents-agent-handoff"
HANDOFF_VERSION: Final[int] = 1
#: A hand-off file bigger than this is refused before it is parsed. Fifty
#: rich summaries come to well under 2 MB, so 20 MB only stops a wrong file.
MAX_HANDOFF_BYTES: Final[int] = 20 * 1024 * 1024

INSTRUCTIONS: Final[str] = (
    "For each entry in `papers`, read the paper (its `pdf_url`, or `url` when there is no "
    "PDF) and fill `paper.summary` with a thesis-structured summary in the language given "
    "in `language`. `summary_template` lists every field: pain_points -> 1.2 motivation, "
    "research_question -> 1.3, contributions_detailed (at most 4) -> 1.5, technique_table "
    "-> 2.3, system_flow -> 3.1, method_sections -> 3.2-3.4, headline_metrics and "
    "evaluation_sections -> 4.4-4.5, core_observation -> 5.1, limitations -> 5.3, "
    "future_work -> 5.4. Leave `key` and every other paper field unchanged, keep "
    "`summary` null for a paper you could not read, and save the file under any name. "
    "Then use 'Import summaries' on the Enrich page of ThesisAgents."
)


class HandoffError(ValueError):
    """A hand-off file that is not one, or not one this version can read."""


@dataclass(frozen=True)
class HandoffResult:
    """What :func:`read_handoff` attached.

    ``imported`` papers got a summary from the file. ``unmatched`` entries
    named a key that is not in the collection (a file from another search).
    """

    collection: PaperCollection
    imported: int
    unmatched: int


def write_handoff(collection: PaperCollection, path: str | Path, *, language: str) -> int:
    """Write ``collection`` as a hand-off file at ``path``; return the paper count.

    Papers that already have a summary keep it in the file, so an agent can
    see what is done and the import does not lose it.
    """
    template = replace(collection.papers[0], summary=PaperSummary(language=language)) if (
        collection.papers
    ) else None
    document: dict[str, Any] = {
        "format": HANDOFF_FORMAT,
        "version": HANDOFF_VERSION,
        "language": language,
        "query": collection.query.keywords,
        "instructions": INSTRUCTIONS,
        "summary_template": template.to_dict()["summary"] if template else None,
        "papers": [
            {"key": paper.dedup_key(), "paper": paper.to_dict()} for paper in collection.papers
        ],
    }
    Path(path).write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(collection.papers)


def read_handoff(path: str | Path, collection: PaperCollection) -> HandoffResult:
    """Attach the summaries in the hand-off file at ``path`` to ``collection``.

    Raises :class:`HandoffError` for a file that is too big, not JSON, not a
    hand-off, from a newer version, or with a summary that cannot be read.
    A paper with no summary in the file keeps the one it had.
    """
    document = _load_document(Path(path))
    known = {paper.dedup_key() for paper in collection.papers}
    summaries, unmatched = _summaries(document, known)
    papers = tuple(
        replace(paper, summary=summaries[paper.dedup_key()])
        if paper.dedup_key() in summaries
        else paper
        for paper in collection.papers
    )
    return HandoffResult(replace(collection, papers=papers), len(summaries), unmatched)


def _load_document(target: Path) -> dict[str, Any]:
    """Read and check the envelope: size, JSON, format name, version."""
    if target.stat().st_size > MAX_HANDOFF_BYTES:
        raise HandoffError(f"{target.name} is larger than {MAX_HANDOFF_BYTES // 2**20} MB")
    try:
        # "-sig": an editor on Windows may have put a byte order mark in front.
        document = json.loads(target.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as err:
        raise HandoffError(f"{target.name} is not a JSON file: {err}") from err
    except RecursionError as err:
        # A file nested thousands of levels deep: not something an agent writes.
        raise HandoffError(f"{target.name} is nested too deeply to read") from err
    if not isinstance(document, dict) or document.get("format") != HANDOFF_FORMAT:
        raise HandoffError(f"{target.name} is not a ThesisAgents hand-off file")
    if document.get("version") != HANDOFF_VERSION:
        raise HandoffError(f"hand-off version {document.get('version')!r} is not supported")
    return document


def _summaries(
    document: dict[str, Any], known: set[str]
) -> tuple[dict[str, PaperSummary], int]:
    """``key`` → summary for every filled-in entry of a known paper, plus the
    number of entries whose key is not in the collection."""
    summaries: dict[str, PaperSummary] = {}
    unmatched = 0
    entries = document.get("papers") or []
    if not isinstance(entries, list):
        raise HandoffError("`papers` must be a list")
    for entry in entries:
        key, paper = _checked_entry(entry)
        if key not in known:
            unmatched += 1
            continue
        summary = _entry_summary(key, paper)
        if summary is not None:
            summaries[key] = summary
    return summaries, unmatched


def _checked_entry(entry: object) -> tuple[str, dict[str, Any]]:
    """Return ``(key, paper)`` of one ``papers`` entry, or refuse its shape.

    Guards the untrusted file: an entry that is not an object, has no text
    ``key`` or no ``paper`` object raises :class:`HandoffError` instead of a
    ``KeyError`` / ``TypeError`` further down.

    Example: ``_checked_entry({"key": "doi:10.1/x", "paper": {}})`` returns
    ``("doi:10.1/x", {})``, ``_checked_entry([])`` raises.
    """
    if (
        not isinstance(entry, dict)
        or not isinstance(entry.get("key"), str)
        or not isinstance(entry.get("paper"), dict)
    ):
        raise HandoffError("every entry in `papers` needs a text `key` and a `paper` object")
    return entry["key"], entry["paper"]


def _entry_summary(key: str, paper: dict[str, Any]) -> PaperSummary | None:
    """Parse the summary of one entry's ``paper`` object, or ``None`` when empty.

    Guards the untrusted file: a summary that is not an object, or one the
    model cannot read, raises :class:`HandoffError` with the entry's ``key``
    instead of letting a traceback escape a Qt slot.

    Example: ``_entry_summary("k", {"summary": None})`` returns ``None``,
    ``_entry_summary("k", {"summary": "text"})`` raises.
    """
    raw = paper.get("summary")
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise HandoffError(f"the summary for {key} must be an object")
    try:
        return Paper.from_dict(paper).summary
    # The file is untrusted: any shape the model cannot read is a refusal
    # with a reason, never a traceback out of a Qt slot.
    except (ThesisAgentsError, KeyError, TypeError, ValueError, AttributeError) as err:
        raise HandoffError(f"the summary for {key} cannot be read: {err}") from err

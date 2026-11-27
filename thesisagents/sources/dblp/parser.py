"""Parse DBLP `publ/api` JSON hits into `Paper` instances.

DBLP returns very compact bibliographic data — no abstracts and no citation
counts. We populate the `Paper` with what's available and leave the rest as
the model defaults; downstream rank-by-citation falls back gracefully when
the count is missing.
"""

from __future__ import annotations

import re
from typing import Any

from thesisagents.core.models import Paper
from thesisagents.utils.markup import plain_text

_SOURCE = "dblp"
#: The number DBLP puts behind a name several people share ("Wei Wang 0001").
#: It is not part of the name, and as its last word it became the surname.
_HOMONYM_NUMBER_RE = re.compile(r"\s+\d{4}$")


def parse_hit(hit: dict[str, Any]) -> Paper:
    """Map one entry from ``result.hits.hit[].info`` to a ``Paper``."""
    info = hit.get("info") or {}
    title = _text(info.get("title")).rstrip(".")
    authors = tuple(_authors(info.get("authors") or {}))
    year = _to_int(info.get("year"))
    venue = _text(info.get("venue")) or None
    doi = _text(info.get("doi")) or None
    url = _text(info.get("ee")) or _text(info.get("url"))
    if not url and doi:
        url = f"https://doi.org/{doi}"
    source_id = (hit.get("@id") or info.get("key") or doi or url).strip()
    return Paper(
        source=_SOURCE,
        source_id=source_id,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract="",
        url=url,
        doi=doi,
        raw=hit,
    )


def _authors(authors_block: dict[str, Any]) -> list[str]:
    raw = authors_block.get("author")
    if raw is None:
        return []
    items = raw if isinstance(raw, list) else [raw]
    names: list[str] = []
    for item in items:
        text = _HOMONYM_NUMBER_RE.sub("", _text(item))
        if text:
            names.append(text)
    return names


def _text(value: Any) -> str:
    """One text out of a DBLP value.

    The boundary this guards: a field is a string, an object with ``text``,
    or a list of either when a record has several (two venues). A list read
    as a string failed the whole source for one record.

    Example: ``_text(["ICSE", "FSE"]) == "ICSE, FSE"``.
    """
    if isinstance(value, list):
        return ", ".join(text for text in map(_text, value) if text)
    if isinstance(value, dict):
        value = value.get("text")
    return plain_text(str(value)) if value is not None else ""


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

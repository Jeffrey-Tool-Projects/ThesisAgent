"""Parse IEEE Xplore REST search JSON and per-document metadata blobs."""

from __future__ import annotations

import json
import re
from typing import Any

from thesisagents.core.exceptions import ParseError
from thesisagents.core.models import Paper
from thesisagents.utils.markup import plain_text

_SOURCE = "ieee"
_DOC_URL = "https://ieeexplore.ieee.org/document/{arnumber}"
#: Where the blob starts: the assignment, up to its opening brace. The JSON
#: object itself is read by ``json.JSONDecoder.raw_decode``, which finds its
#: real end in one pass. A lazy ``\{.*?\};`` scan backtracked over the whole
#: page and stopped early at a ``};`` inside a string value.
_BLOB_START_RE = re.compile(r"xplGlobal\.document\.metadata\s*=\s*(?=\{)")
_JSON_DECODER = json.JSONDecoder()


def parse_metadata_blob(html_text: str) -> Paper:
    """Extract a Paper from a document-page ``xplGlobal.document.metadata`` JS blob."""
    match = _BLOB_START_RE.search(html_text)
    if not match:
        raise ParseError(_SOURCE, "xplGlobal.document.metadata blob not found")
    try:
        meta, _ = _JSON_DECODER.raw_decode(html_text, match.end())
    except json.JSONDecodeError as err:
        raise ParseError(_SOURCE, f"metadata blob is not JSON: {err}") from err
    return _paper_from_blob(meta)


def parse_search_record(record: dict[str, Any]) -> Paper:
    """Map one entry from /rest/search ``records`` to a Paper."""
    arnumber = str(record.get("articleNumber") or "")
    title = _clean_html(record.get("articleTitle") or "")
    abstract = _clean_html(record.get("abstract") or "")
    authors = tuple(
        _author_name(a)
        for a in (record.get("authors") or [])
        if _author_name(a)
    )
    year = _to_int(record.get("publicationYear"))
    venue = record.get("publicationTitle") or None
    doi = record.get("doi") or None
    citation_count = _to_int(record.get("citationCount"))
    pdf_path = record.get("pdfUrl") or None
    pdf_url = _absolutise(pdf_path)
    return Paper(
        source=_SOURCE,
        source_id=arnumber,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        url=_DOC_URL.format(arnumber=arnumber) if arnumber else "",
        doi=doi,
        citation_count=citation_count,
        pdf_url=pdf_url,
        raw=record,
    )


def parse_api_record(record: dict[str, Any]) -> Paper:
    """Map one entry from the official IEEE Xplore API ``articles`` list.

    The API response uses snake_case keys (``article_number``, ``pdf_url``,
    ``publication_year``) and nests authors under ``authors.authors``, so
    we can't reuse ``parse_search_record``. The ``pdf_url`` field is the
    direct PDF for documents inside the API key's subscription scope.
    """
    arnumber = str(record.get("article_number") or "")
    title = _clean_html(record.get("title") or "")
    abstract = _clean_html(record.get("abstract") or "")
    authors_block = record.get("authors") or {}
    authors_list = (
        authors_block.get("authors") if isinstance(authors_block, dict) else []
    ) or []
    authors = tuple(
        _api_author_name(a) for a in authors_list if _api_author_name(a)
    )
    year = _to_int(record.get("publication_year"))
    venue = record.get("publication_title") or None
    doi = record.get("doi") or None
    citation_count = _to_int(record.get("citing_paper_count"))
    pdf_url = _absolutise(record.get("pdf_url") or None)
    html_url = record.get("html_url") or (
        _DOC_URL.format(arnumber=arnumber) if arnumber else ""
    )
    return Paper(
        source=_SOURCE,
        source_id=arnumber,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        url=html_url,
        doi=doi,
        citation_count=citation_count,
        pdf_url=pdf_url,
        raw=record,
    )


def _api_author_name(author: dict[str, Any]) -> str:
    """Extract a display name from an API ``authors.authors[i]`` entry."""
    if not isinstance(author, dict):
        return ""
    for key in ("full_name", "preferred_name"):
        value = author.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    given = (author.get("first_name") or "").strip()
    family = (author.get("last_name") or "").strip()
    if given and family:
        return f"{given} {family}"
    return family or given


def _paper_from_blob(meta: dict[str, Any]) -> Paper:
    arnumber = str(meta.get("articleNumber") or "")
    title = _clean_html(meta.get("title") or meta.get("displayDocTitle") or "")
    abstract = _clean_html(meta.get("abstract") or "")
    authors = tuple(
        _author_name(a)
        for a in (meta.get("authors") or [])
        if _author_name(a)
    )
    year = _to_int(meta.get("publicationYear"))
    venue = (
        meta.get("publicationTitle")
        or meta.get("displayPublicationTitle")
        or None
    )
    doi = meta.get("doi") or None
    pdf_path = meta.get("pdfUrl") or None
    return Paper(
        source=_SOURCE,
        source_id=arnumber,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        url=_DOC_URL.format(arnumber=arnumber) if arnumber else "",
        doi=doi,
        pdf_url=_absolutise(pdf_path),
        raw=meta,
    )


def _author_name(author: dict[str, Any]) -> str:
    for key in ("preferredName", "name", "fullName"):
        value = author.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    given = (author.get("firstName") or "").strip()
    family = (author.get("lastName") or "").strip()
    if given and family:
        return f"{given} {family}"
    return family or given


def _clean_html(value: str) -> str:
    return plain_text(value)


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _absolutise(path: str | None) -> str | None:
    if not path:
        return None
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith("/"):
        return f"https://ieeexplore.ieee.org{path}"
    return path

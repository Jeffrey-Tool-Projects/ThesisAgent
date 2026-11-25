"""Parse OpenAIRE Graph `researchProducts` records into ``Paper`` instances.

OpenAIRE's value over OpenAlex is its strong coverage of European OA
repositories and pre-print servers. We pick the first ``instances[].urls[]``
entry as the canonical landing URL, and look for a PDF URL among the
instances with ``accessRight`` of ``OPEN`` or with a ``.pdf`` suffix.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from thesisagents.core.models import Paper
from thesisagents.utils.markup import plain_text

_SOURCE = "openaire"
_ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([\w.\-/]+)", re.IGNORECASE)


#: A link to the file names it ``1706.03762v5.pdf``, which is not the id.
_ARXIV_FILE_SUFFIX = re.compile(r"(?:v\d+)?(?:\.pdf)?$", re.IGNORECASE)


def parse_product(record: dict[str, Any]) -> Paper:
    """Map one ``results[]`` entry to a ``Paper``."""
    title = plain_text(record.get("mainTitle") or record.get("title"))
    authors = tuple(_authors(record.get("authors") or []))
    year = _year(record.get("publicationDate") or "")
    venue = _venue(record)
    abstract = _abstract(record.get("descriptions") or [])
    doi = _doi(record.get("pids") or [])
    arxiv_id = _arxiv_id(record)
    url = _landing_url(record.get("instances") or [])
    if not url and doi:
        url = f"https://doi.org/{doi}"
    pdf_url = _pdf_url(record.get("instances") or [])
    source_id = (record.get("id") or doi or url or "").strip()
    return Paper(
        source=_SOURCE,
        source_id=source_id,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        abstract=abstract,
        url=url,
        doi=doi,
        arxiv_id=arxiv_id,
        pdf_url=pdf_url,
        raw=record,
    )


def _authors(entries: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("fullName") or entry.get("name") or "").strip()
        if name:
            # OpenAIRE stores "Last, First"; normalise to "First Last"
            # only when there's exactly one comma so we don't mangle
            # cases like "Last, First, Middle".
            if name.count(",") == 1:
                family, given = (part.strip() for part in name.split(","))
                if family and given:
                    name = f"{given} {family}"
            names.append(name)
    return names


def _year(publication_date: str) -> int | None:
    if not publication_date:
        return None
    head = publication_date.strip()[:4]
    try:
        return int(head)
    except ValueError:
        return None


def _venue(record: dict[str, Any]) -> str | None:
    container = (record.get("container") or {})
    name = (container.get("name") or "").strip()
    if name:
        return name
    journal = (record.get("journal") or {})
    name = (journal.get("name") or "").strip()
    return name or None


def _abstract(descriptions: list[dict[str, Any]]) -> str:
    for entry in descriptions:
        if isinstance(entry, dict):
            value = plain_text(entry.get("value"))
            if value:
                return value
        elif isinstance(entry, str) and entry.strip():
            return plain_text(entry)
    return ""


def _pid_value(pids: list[dict[str, Any]], scheme: str) -> str | None:
    """Return the first non-empty ``value`` among ``pids`` whose scheme is ``scheme``.

    Guards the identifier lookups against OpenAIRE's loose ``pids`` list: an
    entry that is not a dict, has no scheme, or has a blank value is
    skipped, and the scheme compares case-insensitively.

    Example: ``_pid_value([{"scheme": "DOI", "value": " 10.1/x "}], "doi")``
    returns ``"10.1/x"``.
    """
    for entry in pids:
        if not isinstance(entry, dict):
            continue
        entry_scheme = (entry.get("scheme") or "").lower()
        value = (entry.get("value") or "").strip()
        if entry_scheme == scheme and value:
            return value
    return None


def _instance_urls(instances: list[dict[str, Any]]) -> Iterator[tuple[str, bool]]:
    """Yield each non-empty URL of ``instances`` with whether its instance is open access.

    Guards the URL lookups against a ``None`` instance, a missing or null
    ``urls`` list, and blank URLs, all of which OpenAIRE returns. URLs come
    in record order, lazily, so a caller that returns on the first hit
    never reads the rest.

    Example: ``list(_instance_urls([{"accessRight": "OPEN", "urls": ["",
    "https://a/x.pdf"]}, None]))`` is ``[("https://a/x.pdf", True)]``.
    """
    for instance in instances:
        data = instance or {}
        is_open = _access(data.get("accessRight")) == "OPEN"
        for url in data.get("urls") or []:
            if url:
                yield url, is_open


def _access(value: Any) -> str:
    """The access right in capitals: ``v2`` sends an object, ``v1`` sent its label.

    Example: ``_access({"code": "c_abf2", "label": "Open"}) == "OPEN"``.
    """
    if isinstance(value, dict):
        value = value.get("label")
    return str(value or "").upper()


def _doi(pids: list[dict[str, Any]]) -> str | None:
    return _pid_value(pids, "doi")


def _arxiv_id(record: dict[str, Any]) -> str | None:
    from_pid = _pid_value(record.get("pids") or [], "arxiv")
    if from_pid:
        return from_pid
    for url, _ in _instance_urls(record.get("instances") or []):
        match = _ARXIV_RE.search(url)
        if match:
            return _ARXIV_FILE_SUFFIX.sub("", match.group(1))
    return None


def _landing_url(instances: list[dict[str, Any]]) -> str:
    return next((url for url, _ in _instance_urls(instances)), "")


def _pdf_url(instances: list[dict[str, Any]]) -> str | None:
    open_url: str | None = None
    any_pdf: str | None = None
    for url, is_open in _instance_urls(instances):
        if not url.lower().endswith(".pdf"):
            if is_open and open_url is None:
                open_url = url
            continue
        if is_open:
            return url
        any_pdf = any_pdf or url
    return any_pdf or open_url

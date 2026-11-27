"""Reopen the Papers and Query sheets of an exported search."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from openpyxl import load_workbook

from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.identifiers import IdentifierKind, parse_identifier
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.core.pdf_download import owned_pdf_paths
from thesisagents.intelligence.pdf import extract_pdf_file
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)


def read_search_workbook(path: Path) -> PaperCollection:
    """Read saved paper metadata and reuse PDFs recorded by the same export."""
    with closing(load_workbook(path, read_only=True, data_only=True)) as workbook:
        if "Papers" not in workbook.sheetnames:
            raise ValueError("The workbook has no Papers sheet.")
        rows = workbook["Papers"].values
        headers = next(rows, ())
        if not {"Title", "URL", "Indexed via"}.issubset(headers):
            raise ValueError("The Papers sheet needs Title, URL and Indexed via columns.")
        papers = []
        for row in rows:
            fields = dict(zip(headers, row, strict=True))
            if _text(fields.get("Title")).strip():
                papers.append(_read_paper(fields))
        if not papers:
            raise ValueError("The Papers sheet has no paper titles.")
        meta = {}
        if "Query" in workbook.sheetnames:
            meta = dict(workbook["Query"].iter_rows(max_col=2, values_only=True))
    sources = tuple(
        part.strip() for part in _text(meta.get("Sources")).split(",") if part.strip()
    )
    max_results = _integer(meta, "Max per source")
    query = Query(
        keywords=_text(meta.get("Query keywords")) or path.stem,
        sources=sources or tuple(dict.fromkeys(paper.source for paper in papers)),
        max_results=Query.clamp_max_results(len(papers)) if max_results is None else max_results,
        year_from=_integer(meta, "Year from"),
        year_to=_integer(meta, "Year to"),
        min_citations=_integer(meta, "Min citations"),
    )
    owned = owned_pdf_paths(path.parent)
    return PaperCollection(query, tuple(_with_pdf_text(p, owned) for p in papers))


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _integer(row: dict, column: str) -> int | None:
    value = _text(row.get(column)).strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as err:
        raise ValueError(f"{column} must be a whole number, got {value!r}.") from err


def _authors(row: dict) -> tuple[str, ...]:
    displayed = _text(row.get("Authors"))
    if not displayed:
        return ()
    encoded = row.get("Author names (JSON)")
    if isinstance(encoded, str):
        try:
            names = json.loads(encoded)
        except (ValueError, RecursionError):
            names = None
        if (isinstance(names, list) and all(isinstance(name, str) for name in names)
                and ", ".join(names) == displayed):
            return tuple(names)
    # Older files use the same comma for "Family, Given" and between names.
    parts = displayed.split(", ")
    return tuple(parts) if all(len(part.split()) > 1 for part in parts) else (displayed,)


def _read_paper(row: dict) -> Paper:
    url = _text(row["URL"])
    try:
        identifier = parse_identifier(url)
    except ValueError:
        identifier = None
    arxiv_id = identifier.value if identifier and identifier.kind is IdentifierKind.ARXIV else None
    title = _text(row["Title"])
    pdf_url = _text(row.get("PDF"))
    doi = _text(row.get("DOI")) or None
    return Paper(
        source=_text(row["Indexed via"]) or "xlsx",
        source_id=arxiv_id or doi or url or title,
        title=title, authors=_authors(row),
        year=_integer(row, "Year"), venue=_text(row.get("Source")) or None,
        abstract=_text(row.get("Abstract")),
        url=url, doi=doi, arxiv_id=arxiv_id,
        citation_count=_integer(row, "Citations"),
        pdf_url=pdf_url if pdf_url.startswith(("https://", "http://")) else None,
    )


def _with_pdf_text(paper: Paper, owned: dict[str, Path]) -> Paper:
    local = owned.get(paper.dedup_key())
    if local is None:
        return paper
    try:
        pdf = extract_pdf_file(local, url=paper.pdf_url or paper.url, source=paper.source)
    except ThesisAgentsError as err:
        _LOG.warning("Could not read the saved PDF for %s: %s", paper.title, err)
        return paper
    return replace(paper, raw={"extracted_text": pdf.text, "page_count": pdf.page_count})

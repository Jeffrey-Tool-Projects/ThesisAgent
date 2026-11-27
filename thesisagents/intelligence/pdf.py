"""Fetch a paper's PDF and extract its text.

A remote PDF is fetched by :func:`thesisagents.core.pdf_download.fetch_pdf_to`,
the downloader's own routing: visible Chrome for a paywalled publisher host,
the shared HTTPS-only client (TLS and local-network guardrails, streamed size
cap) for an open one. A PDF already on disk is read by
:func:`extract_pdf_file` without any request. Output is plain text, joined
per page, capped at ``MAX_PDF_CHARS`` so a malicious 1000-page PDF cannot
blow out the LLM context window.
"""

from __future__ import annotations

import asyncio
import io
import tempfile
from dataclasses import dataclass
from pathlib import Path

from thesisagents.core.exceptions import (
    FetchError,
    ParseError,
    SourceUnavailableError,
    ThesisAgentsError,
)
from thesisagents.core.pdf_download import fetch_pdf_to
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

MAX_PDF_BYTES: int = 20_000_000   # 20 MB hard cap on the downloaded file
MAX_PDF_PAGES: int = 60           # truncate at 60 pages — far past every paper we'd care about
MAX_PDF_CHARS: int = 80_000       # keep the extracted text below this many chars


@dataclass(frozen=True, slots=True)
class ExtractedPdf:
    """Result of a successful fetch + extract."""

    url: str
    page_count: int
    chars: int
    text: str


async def fetch_and_extract(pdf_url: str, source: str = "intelligence") -> ExtractedPdf:
    """Download ``pdf_url`` and return its concatenated text.

    The fetch goes through the downloader's publisher routing, so a
    paywalled publisher PDF is fetched by visible Chrome rather than by a
    plain request the publisher refuses. The bytes land in a temporary
    folder that is removed afterwards.

    Raises ``FetchError`` subclasses on network / status problems and
    ``ParseError`` when the bytes don't decode as a PDF.
    """
    if not pdf_url:
        raise ParseError(source, "no pdf_url supplied")
    with tempfile.TemporaryDirectory(prefix="thesisagents_text_") as tmp:
        target = Path(tmp) / "paper.pdf"
        result = await fetch_pdf_to(pdf_url, target, source=source, max_bytes=MAX_PDF_BYTES)
        if result.path is None:
            raise _fetch_error(source, result.skipped_reason or "")
        return await asyncio.to_thread(extract_pdf_file, result.path, url=pdf_url, source=source)


def extract_pdf_file(path: Path, *, url: str, source: str = "local") -> ExtractedPdf:
    """Extract the text of a PDF already on disk, ``url`` naming where it came from.

    The boundary this guards: a summary used to fetch the PDF again over
    plain HTTP even when the run had downloaded it (through Chrome, for a
    publisher that refuses plain requests). Reading the saved file needs no
    request at all. Files over ``MAX_PDF_BYTES`` are refused before they are
    read, so a large browser download cannot fill memory.

    Raises ``ParseError`` for an unreadable, oversized or non-PDF file.
    Example: ``extract_pdf_file(Path("pdfs/vaswani2017attention.pdf"),
    url="https://arxiv.org/pdf/1706.03762")``.
    """
    try:
        size = path.stat().st_size
        if size > MAX_PDF_BYTES:
            raise ParseError(source, f"PDF exceeds {MAX_PDF_BYTES:,} byte cap ({size:,} bytes)")
        body = path.read_bytes()
    except OSError as err:
        raise ParseError(source, f"cannot read the PDF {path}: {err}") from err
    text, page_count = _extract_text(body, source)
    if len(text) > MAX_PDF_CHARS:
        text = text[:MAX_PDF_CHARS]
    _LOG.info("PDF extracted: url=%s pages=%d chars=%d", url, page_count, len(text))
    return ExtractedPdf(url=url, page_count=page_count, chars=len(text), text=text)


def _fetch_error(source: str, reason: str) -> ThesisAgentsError:
    """The exception for a ``PdfDownloadResult.skipped_reason``.

    Keeps the classes callers relied on before the fetch was shared: 429 is
    a ``FetchError``, network errors and 5xx are ``SourceUnavailableError``,
    other 4xx, an oversized body and a non-PDF reply are ``ParseError``.
    Example: ``_fetch_error("arxiv", "http_503")`` is a ``SourceUnavailableError``.
    """
    if reason == "network_error":
        return SourceUnavailableError(source, "network error while fetching the PDF")
    status = int(reason[5:]) if reason.startswith("http_") and reason[5:].isdigit() else 0
    if status == 429:
        return FetchError(source, "PDF host rate-limited the request")
    if status >= 500:
        return SourceUnavailableError(source, f"server error {status}")
    if status >= 400:
        return ParseError(source, f"PDF host returned {status}")
    if reason == "too_large":
        return ParseError(source, f"PDF exceeds {MAX_PDF_BYTES:,} byte cap")
    return ParseError(source, f"response is not a PDF ({reason or 'unknown reason'})")


def _extract_text(body: bytes, source: str) -> tuple[str, int]:
    try:
        from pypdf import PdfReader  # imported lazily so the dep is truly optional
    except ImportError as err:
        raise ParseError(
            source,
            "pypdf is not installed; run `pip install thesisagents[intelligence]`",
        ) from err
    try:
        # Reading the page list is what fails for an encrypted file. Outside
        # the ``try`` its error ended the enrichment of every other paper.
        pages = list(PdfReader(io.BytesIO(body)).pages)[:MAX_PDF_PAGES]
    except Exception as err:
        raise ParseError(source, f"pypdf could not open the file: {err}") from err
    chunks: list[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception as err:    # noqa: BLE001  # pypdf raises various sub-exceptions
            _LOG.debug("pypdf failed on a page: %s", err)
            continue
        if text.strip():
            chunks.append(text)
    if not chunks:
        raise ParseError(source, "pypdf extracted zero text from the PDF")
    joined = "\n\n".join(chunks)
    return _normalise(joined), len(pages)


def _normalise(text: str) -> str:
    """Collapse runs of whitespace and stray PDF line-wrap artefacts."""
    # rejoin hard-wrapped lines: "exam-\nple" → "example"
    text = text.replace("-\n", "")
    # collapse single newlines inside paragraphs to spaces; keep blank lines
    out_lines: list[str] = []
    current: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped:
            current.append(stripped)
        else:
            if current:
                out_lines.append(" ".join(current))
                current = []
    if current:
        out_lines.append(" ".join(current))
    return "\n\n".join(out_lines)

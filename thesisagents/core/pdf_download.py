"""Download paper PDFs alongside the exported artefacts.

Reuses the shared per-source HTTPS-only client, so the same TLS and
local-network guardrails apply as for search traffic. The sources' token
buckets do not: they pace API calls, and a PDF sits on some other host. What
keeps this stage polite is a cap on parallel downloads and a smaller one per
host.
Failures (missing pdf_url, network errors, wrong content-type) are logged
and skipped — the rest of the export workflow is unaffected.

Every PDF request also sends browser-style headers (real Mozilla
User-Agent, ``Accept``, ``Accept-Language``, and a ``Referer`` derived
from the paper's landing-page URL) because many publishers return 403 to
the project's default API-style UA. When the env var
``THESISAGENTS_PDF_COOKIES_FILE`` points at a Netscape ``cookies.txt``
file, matching cookies are attached on top.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin, urlparse

from thesisagents.core.models import Paper, PaperCollection
from thesisagents.core.pdf_cookies import cookies_for_url
from thesisagents.fetchers.http import get_client
from thesisagents.utils.logging import get_logger
from thesisagents.utils.path_safety import ensure_export_dir, safe_filename

_LOG = get_logger(__name__)

_PDF_SUBDIR: str = "pdfs"
_MAX_PDF_BYTES: int = 50_000_000
_MAX_FILENAME_LENGTH: int = 80

#: Cap on simultaneously-downloading PDFs. Several sources can hand back PDF
#: URLs on the SAME host under different source clients, so the cap is global.
#: 4 keeps the stage brisk.
_DOWNLOAD_CONCURRENCY: int = 4
#: Of those, how many may run against one host (arxiv.org, a repository). A
#: burst against a single host looks like a scrape and risks an IP block.
_PER_HOST_CONCURRENCY: int = 2

#: Real browser User-Agent — many publisher CDNs (Elsevier, IEEE Xplore,
#: Springer) return 403 to non-browser UAs even for open-access PDFs.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)


#: How a PDF was fetched, recorded in ``PdfDownloadResult.route``. The
#: browser routes exist because the Browser Automation rule (``CLAUDE.md``,
#: ``compliance-auditor``) says a paywalled publisher PDF goes through
#: visible Chrome, and that a request that skipped it must be surfaced rather
#: than trusted. Before these were recorded, a missing browser (selenium not
#: installed, or ``THESISAGENTS_DISABLE_WEBRUNNER=1``) sent paywalled URLs to
#: plain httpx with no log line, and a GUI user could not tell it happened.
ROUTE_ON_DISK = "on_disk"
ROUTE_BROWSER = "browser"
ROUTE_DIRECT = "direct"
ROUTE_DIRECT_BROWSER_FAILED = "direct_after_browser_failed"
ROUTE_DIRECT_NO_BROWSER = "direct_without_browser"


@dataclass(frozen=True, slots=True)
class PdfDownloadResult:
    """Outcome of one download attempt.

    ``route`` says how the PDF was (or was not) fetched: ``on_disk`` (already
    there), ``browser`` (visible Chrome), ``direct`` (an ordinary HTTPS
    request to an open host), ``direct_after_browser_failed`` and
    ``direct_without_browser`` (a paywalled publisher URL that went to a
    direct request because the browser failed or was unavailable, which the
    publisher usually refuses). Empty when nothing was requested (no
    ``pdf_url``, or the attempt raised).

    Example: ``PdfDownloadResult("vaswani2017attention", path, None, "browser")``.
    """

    paper_key: str
    path: Path | None
    skipped_reason: str | None
    route: str = ""


async def download_pdfs(
    collection: PaperCollection,
    out_dir: str | Path,
    *,
    concurrency: int = _DOWNLOAD_CONCURRENCY,
) -> list[PdfDownloadResult]:
    """Download every paper's PDF into ``{out_dir}/pdfs/``.

    Returns a result per paper so callers can summarise failures. Papers
    without a ``pdf_url`` are skipped with reason ``no_pdf_url``. A semaphore
    caps how many downloads run at once (``concurrency``, default
    ``_DOWNLOAD_CONCURRENCY``) so a large collection doesn't hammer a single
    publisher CDN with one request per paper simultaneously, and at most
    ``_PER_HOST_CONCURRENCY`` of them run against the same host.
    """
    root = ensure_export_dir(out_dir)
    pdf_dir = ensure_export_dir(root / _PDF_SUBDIR)
    sem = asyncio.Semaphore(max(1, concurrency))

    per_host: dict[str, asyncio.Semaphore] = {}

    async def _bounded(paper: Paper) -> PdfDownloadResult:
        host = urlparse(paper.pdf_url or "").hostname or ""
        host_sem = per_host.setdefault(host, asyncio.Semaphore(_PER_HOST_CONCURRENCY))
        # The host's slot first: a paper that waits for a busy host must not
        # hold one of the global slots meanwhile.
        async with host_sem, sem:
            return await _download_one(paper, pdf_dir)

    # ``return_exceptions=True``: a download is per-paper best-effort, and the
    # soft failures (404, wrong content-type, oversized body) are already turned
    # into ``PdfDownloadResult`` values. What is left is the hard kind —
    # ``OSError`` from a full disk or a path the filesystem rejects, say — and
    # letting one of those propagate out of ``gather`` would throw away every
    # PDF the other tasks had already written to disk. Each failed slot becomes
    # a skipped result carrying the exception type as its reason instead.
    outcomes = await asyncio.gather(
        *(_bounded(paper) for paper in collection.papers),
        return_exceptions=True,
    )
    results: list[PdfDownloadResult] = []
    for paper, outcome in zip(collection.papers, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            reason = f"error_{type(outcome).__name__}"
            _LOG.warning(
                "pdf download raised for %s: %s: %s",
                paper.source_id, type(outcome).__name__, outcome,
            )
            results.append(
                PdfDownloadResult(
                    paper_key=_safe_key(paper), path=None, skipped_reason=reason
                )
            )
        else:
            results.append(outcome)
    return results


def _safe_key(paper: Paper) -> str:
    """``bibtex_key()`` that can't itself fail the error-reporting path.

    Used only when building a failure result — if the paper is malformed
    enough that key derivation raises, the report falls back to the source id
    so the caller still learns which paper failed.
    """
    try:
        return paper.bibtex_key()
    except Exception:  # noqa: BLE001 — reporting must not raise
        return paper.source_id or "unknown"


async def _download_one(paper: Paper, pdf_dir: Path) -> PdfDownloadResult:
    key = paper.bibtex_key()
    if not paper.pdf_url:
        _LOG.info("skip pdf for %s: no pdf_url", key)
        return PdfDownloadResult(paper_key=key, path=None, skipped_reason="no_pdf_url")
    target = pdf_dir / f"{safe_filename(key)[:_MAX_FILENAME_LENGTH]}.pdf"
    if target.exists() and target.stat().st_size > 0:
        _LOG.info("pdf already on disk for %s: %s", key, target)
        return PdfDownloadResult(
            paper_key=key, path=target, skipped_reason=None, route=ROUTE_ON_DISK
        )
    # For paywalled publisher CDNs (IEEE, ACM, Springer, Elsevier, ...)
    # httpx-style requests reliably 403. Route those through WebRunner
    # (real visible Chrome) so the session cookie / TLS handshake / JS
    # fingerprint match what the publisher expects.
    from thesisagents.fetchers import webrunner_pdf

    route = ROUTE_DIRECT
    if webrunner_pdf.should_use_webrunner(paper.pdf_url):
        if webrunner_pdf.is_available():
            _LOG.info("pdf via WebRunner for %s: %s", key, paper.pdf_url)
            ok = await webrunner_pdf.download_via_browser(paper.pdf_url, target)
            if ok:
                return PdfDownloadResult(
                    paper_key=key, path=target, skipped_reason=None, route=ROUTE_BROWSER
                )
            _LOG.warning(
                "pdf for %s: the browser could not fetch the publisher PDF %s; "
                "trying a direct request, which the publisher usually refuses",
                key, paper.pdf_url,
            )
            route = ROUTE_DIRECT_BROWSER_FAILED
        else:
            _LOG.warning(
                "pdf for %s: %s is a publisher page that needs the browser, but browser "
                "automation is unavailable (selenium not installed, or "
                "THESISAGENTS_DISABLE_WEBRUNNER=1); trying a direct request, which the "
                "publisher usually refuses",
                key, paper.pdf_url,
            )
            route = ROUTE_DIRECT_NO_BROWSER
    result = await _fetch_and_validate(paper, target, key)
    return replace(  # NOSONAR dataclasses.replace returns the same dataclass type
        result, route=result.route or route
    )


async def _fetch_and_validate(
    paper: Paper, target: Path, key: str
) -> PdfDownloadResult:
    """Fetch ``paper.pdf_url`` and persist the PDF bytes.

    Handles the three soft failure modes: HTTP 4xx/5xx, oversized body,
    HTML-instead-of-PDF. The last is recoverable when the HTML carries
    a ``<meta name="citation_pdf_url">`` tag (Google Scholar's
    metadata convention, populated by most publisher landing pages and
    every OJS / DSpace / EPrints install) — we extract the tag, follow
    it once, and re-validate.
    """
    client = await get_client(paper.source)
    fetched = await _request_pdf(client, paper, paper.pdf_url)
    if isinstance(fetched, PdfDownloadResult):
        # _request_pdf carries the failure reason but doesn't know the key.
        return PdfDownloadResult(
            paper_key=key, path=fetched.path, skipped_reason=fetched.skipped_reason
        )
    body, content_type = fetched
    if not _looks_like_pdf(body, content_type):
        retry_url = _extract_citation_pdf_url(body, base_url=paper.pdf_url)
        if retry_url and retry_url != paper.pdf_url:
            _LOG.info(
                "pdf %s returned HTML; retrying via <meta name=\"citation_pdf_url\"> %s",
                key, retry_url,
            )
            # The page names this address, so it gets the same routing as the
            # first one: a publisher's PDF goes through visible Chrome.
            if await _browser_fetched(retry_url, target):
                return PdfDownloadResult(
                    paper_key=key, path=target, skipped_reason=None, route=ROUTE_BROWSER
                )
            fetched = await _request_pdf(client, paper, retry_url)
            if isinstance(fetched, PdfDownloadResult):
                return PdfDownloadResult(
                    paper_key=key, path=None, skipped_reason="citation_pdf_url_fail",
                )
            body, content_type = fetched
        if not _looks_like_pdf(body, content_type):
            _LOG.warning(
                "pdf wrong content-type for %s: %r", key, content_type or "<empty>"
            )
            return PdfDownloadResult(
                paper_key=key, path=None, skipped_reason="not_pdf"
            )
    target.write_bytes(body)
    _LOG.info("pdf saved %s (%d bytes) for %s", target, len(body), key)
    return PdfDownloadResult(paper_key=key, path=target, skipped_reason=None)


async def _browser_fetched(url: str, target: Path) -> bool:
    """Fetch ``url`` with visible Chrome when it is a paywalled publisher's.

    False when it is an open host, no browser is available, or Chrome did not
    get the PDF. The caller then tries a direct request.
    """
    from thesisagents.fetchers import webrunner_pdf

    if not webrunner_pdf.should_use_webrunner(url) or not webrunner_pdf.is_available():
        return False
    return await webrunner_pdf.download_via_browser(url, target)


async def _request_pdf(client, paper: Paper, url: str):
    """Run one HTTP GET with browser-style headers and Cookie injection.

    Returns ``(body, content_type)`` on a 2xx response that fits the
    size cap, or a :class:`PdfDownloadResult` with the failure reason
    already populated.
    """
    headers = _browser_headers(paper)
    cookies = cookies_for_url(url)
    if cookies:
        # Pass cookies through the ``Cookie:`` header directly; httpx's
        # per-request ``cookies=`` arg is deprecated, and our cookies are
        # opaque-strings-from-a-file, never managed across requests.
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    try:
        response = await client.get(url, headers=headers)
    except Exception as err:  # noqa: BLE001  # network errors come in many shapes
        _LOG.warning("pdf network error for %s: %s", url, err)
        return PdfDownloadResult(
            paper_key="", path=None, skipped_reason="network_error"
        )
    if response.status_code >= 400:
        _LOG.warning("pdf http %s for %s", response.status_code, url)
        return PdfDownloadResult(
            paper_key="", path=None,
            skipped_reason=f"http_{response.status_code}",
        )
    body = response.content
    if len(body) > _MAX_PDF_BYTES:
        _LOG.warning("pdf too large for %s (%d bytes)", url, len(body))
        return PdfDownloadResult(
            paper_key="", path=None, skipped_reason="too_large"
        )
    content_type = response.headers.get("content-type", "").lower()
    return body, content_type


def _looks_like_pdf(body: bytes, content_type: str) -> bool:
    if "pdf" in content_type:
        return True
    return body.startswith(b"%PDF")


#: One ``<meta ...`` tag, from ``<meta`` to just before its closing ``>``
#: (or the end of the scanned head when the tag is cut off). Nothing follows
#: ``[^>]*``, so the scan never backtracks. The attribute patterns below then
#: run once per tag. The earlier single pattern per attribute order
#: (``<meta\s+[^>]*?name=...[^>]*?content=...``) backtracked polynomially on a
#: long tag that lacks the attribute: a 20 kB tag took seconds to reject.
_META_TAG_RE = re.compile(rb"<meta\s[^>]*", re.IGNORECASE)
_CITATION_NAME_RE = re.compile(rb'name=["\']citation_pdf_url["\']', re.IGNORECASE)
_CONTENT_OPEN_RE = re.compile(rb'content=["\']', re.IGNORECASE)
#: A non-empty attribute value up to its closing quote. Like the old pattern
#: it may run past a ``>``, which is legal inside a quoted HTML value.
_QUOTED_VALUE_RE = re.compile(rb'([^"\']+)["\']')


def _content_values(head: bytes, start: int, end: int) -> list[re.Match[bytes]]:
    """Every non-empty quoted ``content=`` value whose attribute opens in ``[start, end)``.

    Guards the attribute boundary: the ``content=`` opener must sit inside
    the tag (before its ``>``), while the value may run on past it. An empty
    value (``content=""``) is skipped, as the old pattern's ``[^"']+`` did.
    Example: ``[v.group(1) for v in _content_values(b'content="" content="/a"',
    0, 23)] == [b"/a"]``.
    """
    values = []
    for opener in _CONTENT_OPEN_RE.finditer(head, start, end):
        value = _QUOTED_VALUE_RE.match(head, opener.end())
        if value is not None:
            values.append(value)
    return values


def _name_then_content(head: bytes, start: int, end: int) -> bytes | None:
    """The ``content`` value of a tag written ``name="citation_pdf_url" content="..."``.

    ``start`` / ``end`` bound one ``<meta`` tag in ``head`` (a match of
    ``_META_TAG_RE``). Returns ``None`` when the tag names something else or
    has no ``content`` after the ``name``. Example: for the tag
    ``<meta name="citation_pdf_url" content="/a.pdf">`` it returns ``b"/a.pdf"``.
    """
    name = _CITATION_NAME_RE.search(head, start, end)
    if name is None:
        return None
    values = _content_values(head, name.end(), end)
    return values[0].group(1) if values else None


def _content_then_name(head: bytes, start: int, end: int) -> bytes | None:
    """The ``content`` value of a tag written ``content="..." name="citation_pdf_url"``.

    ``start`` / ``end`` bound one ``<meta`` tag in ``head``. The ``name``
    attribute must follow the value before the next ``>``. Candidates are
    tried in order. A value that ends inside the tag searches up to the
    tag's own ``>``, the same range a failed earlier candidate already
    searched, so that search is skipped and the scan stays linear. Example:
    for the tag ``<meta content="/a.pdf" name="citation_pdf_url">`` it
    returns ``b"/a.pdf"``.
    """
    searched_until = -1
    for value in _content_values(head, start, end):
        tail_start = value.end()
        if tail_start <= end:
            tail_end = end
        else:
            tail_end = head.find(b">", tail_start)
            tail_end = len(head) if tail_end == -1 else tail_end
        if tail_end == searched_until:
            continue
        if _CITATION_NAME_RE.search(head, tail_start, tail_end) is not None:
            return value.group(1)
        searched_until = tail_end
    return None


def _find_citation_pdf_url(head: bytes) -> bytes | None:
    """The first ``citation_pdf_url`` value in ``head``, as raw bytes.

    A tag with ``name`` before ``content`` anywhere in ``head`` wins over a
    tag with the reverse order, the precedence the extractor has always had.
    Example: ``_find_citation_pdf_url(b'<meta content="/a.pdf"
    name="citation_pdf_url">') == b"/a.pdf"``.
    """
    tags = [(tag.start(), tag.end()) for tag in _META_TAG_RE.finditer(head)]
    for finder in (_name_then_content, _content_then_name):
        for start, end in tags:
            value = finder(head, start, end)
            if value is not None:
                return value
    return None


def _extract_citation_pdf_url(body: bytes, *, base_url: str) -> str | None:
    """Parse ``<meta name="citation_pdf_url" content="...">`` out of HTML.

    The tag is the Google Scholar metadata convention every publisher
    landing page implements; the URL points at the canonical PDF for
    that paper. We accept either attribute order. Relative URLs are
    resolved against ``base_url`` so we don't issue an unparseable GET.
    """
    if not body:
        return None
    head = body[:32_768]  # the tag always sits in the document <head>
    value = _find_citation_pdf_url(head)
    if value is None:
        return None
    candidate = value.decode("utf-8", errors="replace").strip()
    if not candidate:
        return None
    return urljoin(base_url, candidate)


def _browser_headers(paper: Paper) -> dict[str, str]:
    """Per-request headers that make us look like a browser to publisher
    CDNs. ``Referer`` is the paper's landing page (when its host matches
    the PDF host) so the request looks like a click-through from the
    article page; that closes the most common 403 case."""
    headers: dict[str, str] = {
        "User-Agent": _BROWSER_UA,
        "Accept": "application/pdf,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    referer = _referer_for(paper)
    if referer:
        headers["Referer"] = referer
    return headers


def _referer_for(paper: Paper) -> str | None:
    """Use ``paper.url`` as Referer when its host matches the PDF's host —
    a cross-host Referer would itself trip anti-bot rules."""
    if not paper.url or not paper.pdf_url:
        return None
    landing_host = urlparse(paper.url).hostname or ""
    pdf_host = urlparse(paper.pdf_url).hostname or ""
    if landing_host and pdf_host and landing_host == pdf_host:
        return paper.url
    return None

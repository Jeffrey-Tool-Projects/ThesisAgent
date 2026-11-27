"""Tests for the PDF downloader in thesisagents.core.pdf_download."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from thesisagents.core import pdf_download as pdf_download_module
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.core.pdf_download import download_pdfs
from thesisagents.fetchers import http as http_module


@pytest.fixture(autouse=True)
def _reset_clients():
    yield
    http_module._CLIENTS.clear()  # noqa: SLF001


def _paper(**overrides) -> Paper:
    base = {
        "source": "arxiv",
        "source_id": "1706.03762",
        "title": "Attention Is All You Need",
        "authors": ("Ashish Vaswani",),
        "year": 2017,
        "venue": "NeurIPS",
        "abstract": "We propose the Transformer.",
        "url": "https://arxiv.org/abs/1706.03762",
        "pdf_url": "https://arxiv.org/pdf/1706.03762",
    }
    base.update(overrides)
    return Paper(**base)


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(
        query=Query(keywords="x", sources=("arxiv",), max_results=len(papers) or 1),
        papers=tuple(papers),
    )


class _CannedTransport(httpx.AsyncBaseTransport):
    def __init__(self, status: int, body: bytes, content_type: str = "application/pdf"):
        self.status = status
        self.body = body
        self.content_type = content_type
        self.calls: list[str] = []
        self.request_headers: list[dict[str, str]] = []

    async def handle_async_request(self, request):
        self.calls.append(str(request.url))
        self.request_headers.append({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(
            self.status,
            content=self.body,
            headers={"content-type": self.content_type},
            request=request,
        )

    async def aclose(self):
        return None


def _install_transport(monkeypatch, transport):
    http_module._CLIENTS.clear()  # noqa: SLF001

    async def fake_get_client(_source):
        return httpx.AsyncClient(transport=transport)

    monkeypatch.setattr(
        "thesisagents.core.pdf_download.get_client", fake_get_client
    )


async def test_download_pdfs_writes_file(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nfake bytes")
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper()), tmp_path)
    assert len(results) == 1
    saved = results[0]
    assert saved.skipped_reason is None
    assert saved.path is not None
    assert saved.path.exists()
    assert saved.path.read_bytes().startswith(b"%PDF")
    assert saved.path.parent.name == "pdfs"


async def test_download_pdfs_skips_paper_without_pdf_url(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper(pdf_url=None)), tmp_path)
    assert results[0].path is None
    assert results[0].skipped_reason == "no_pdf_url"
    # The transport should never have been touched.
    assert transport.calls == []


async def test_download_pdfs_rejects_non_pdf_payload(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"<html>nope</html>", content_type="text/html")
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper()), tmp_path)
    assert results[0].path is None
    assert results[0].skipped_reason == "not_pdf"


class _ScriptedTransport(httpx.AsyncBaseTransport):
    """Returns a different response per request — for the citation_pdf_url
    retry path where the first GET returns HTML and the second returns the
    actual PDF."""

    def __init__(self, responses: list[tuple[int, bytes, str]]):
        self.responses = list(responses)
        self.calls: list[str] = []

    async def handle_async_request(self, request):
        self.calls.append(str(request.url))
        status, body, content_type = self.responses.pop(0)
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": content_type},
            request=request,
        )

    async def aclose(self):
        return None


async def test_download_pdfs_follows_citation_pdf_url_meta(
    tmp_path: Path, monkeypatch
):
    """Publisher landing page returns HTML with citation_pdf_url meta tag —
    downloader extracts the URL and retries once, getting the real PDF."""
    landing_html = (
        b"<html><head>"
        b'<meta name="citation_title" content="A Paper" />'
        b'<meta name="citation_pdf_url" content="/articles/abc.pdf" />'
        b"</head><body>landing</body></html>"
    )
    transport = _ScriptedTransport(
        [
            (200, landing_html, "text/html"),
            (200, b"%PDF-1.4\nreal pdf bytes", "application/pdf"),
        ]
    )
    _install_transport(monkeypatch, transport)
    paper = _paper(
        url="https://publisher.example/article/abc",
        pdf_url="https://publisher.example/article/abc",
    )
    results = await download_pdfs(_collection(paper), tmp_path)
    assert results[0].skipped_reason is None
    assert results[0].path is not None
    assert results[0].path.read_bytes().startswith(b"%PDF")
    # Second GET should resolve the relative meta URL against the first.
    assert transport.calls[1] == "https://publisher.example/articles/abc.pdf"


async def test_download_pdfs_citation_pdf_url_fail_when_retry_also_html(
    tmp_path: Path, monkeypatch
):
    """If the citation_pdf_url target also returns HTML, surface a distinct reason."""
    landing_html = (
        b"<html><head>"
        b'<meta name="citation_pdf_url" content="https://x/y.pdf" />'
        b"</head></html>"
    )
    transport = _ScriptedTransport(
        [
            (200, landing_html, "text/html"),
            (200, b"<html>still not a pdf</html>", "text/html"),
        ]
    )
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper()), tmp_path)
    assert results[0].path is None
    assert results[0].skipped_reason == "not_pdf"
    # Both URLs were attempted.
    assert len(transport.calls) == 2


async def test_download_pdfs_handles_http_error(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(404, b"missing", content_type="text/plain")
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper()), tmp_path)
    assert results[0].path is None
    assert results[0].skipped_reason == "http_404"


async def test_download_pdfs_skips_existing_file_it_owns(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nfresh content")
    _install_transport(monkeypatch, transport)
    paper = _paper()
    first = (await download_pdfs(_collection(paper), tmp_path))[0]
    first.path.write_bytes(b"%PDF-1.4 already here")
    again = (await download_pdfs(_collection(paper), tmp_path))[0]
    assert again.path == first.path
    assert again.path.read_bytes() == b"%PDF-1.4 already here"
    # Only the first run asked the network: the second found its own file.
    assert len(transport.calls) == 1


# --- a reused folder and papers that share a BibTeX key (review R02) ----------------


class _PathEchoTransport(httpx.AsyncBaseTransport):
    """Answer every request with a PDF whose body names the requested path."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def handle_async_request(self, request):
        self.calls.append(request.url.path)
        return httpx.Response(
            200, content=b"%PDF " + request.url.path.encode(),
            headers={"content-type": "application/pdf"}, request=request,
        )

    async def aclose(self):
        return None


def _twins() -> tuple[Paper, Paper]:
    """Two different papers (DOIs differ) with one BibTeX key."""
    a = _paper(source_id="a", doi="10.1000/a", pdf_url="https://e.example/a")
    b = _paper(source_id="b", doi="10.1000/b", pdf_url="https://e.example/b")
    assert a.bibtex_key() == b.bibtex_key()
    return a, b


async def test_a_later_batch_does_not_get_another_papers_pdf(tmp_path: Path, monkeypatch):
    """Batch 1 saved A. Batch 2 holds only B, whose key is A's: B was reported
    ``on_disk`` with A's PDF, and its per-paper deck was built from it."""
    _install_transport(monkeypatch, _PathEchoTransport())
    a, b = _twins()
    await download_pdfs(_collection(a), tmp_path)
    result = (await download_pdfs(_collection(b), tmp_path))[0]
    assert result.route == pdf_download_module.ROUTE_DIRECT
    assert result.path.read_bytes() == b"%PDF /b"


async def test_swapping_two_papers_keeps_each_ones_file(tmp_path: Path, monkeypatch):
    transport = _PathEchoTransport()
    _install_transport(monkeypatch, transport)
    a, b = _twins()
    await download_pdfs(_collection(a, b), tmp_path)
    results = await download_pdfs(_collection(b, a), tmp_path)
    assert [r.path.read_bytes() for r in results] == [b"%PDF /b", b"%PDF /a"]
    assert [r.route for r in results] == ["on_disk", "on_disk"]
    assert transport.calls == ["/a", "/b"]


async def test_a_folder_from_before_the_manifest_is_not_trusted(tmp_path: Path, monkeypatch):
    """A file under the plain key with no manifest entry has an unknown
    owner: it is neither reused nor overwritten, and the paper downloads
    again under its identity name. That name is reused even unlisted,
    because only this paper's identity produces it."""
    _install_transport(monkeypatch, _PathEchoTransport())
    a, b = _twins()
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    legacy = pdf_dir / f"{a.bibtex_key()}.pdf"
    legacy.write_bytes(b"%PDF /a")
    digest = hashlib.sha256(b.dedup_key().encode("utf-8")).hexdigest()[:8]
    hashed = pdf_dir / f"{a.bibtex_key()}-{digest}.pdf"
    hashed.write_bytes(b"%PDF /b (old collision name)")
    results = await download_pdfs(_collection(b, a), tmp_path)
    assert results[0].path == hashed
    assert results[0].route == pdf_download_module.ROUTE_ON_DISK
    assert results[1].path != legacy
    assert results[1].path.read_bytes() == b"%PDF /a"
    assert results[1].route == pdf_download_module.ROUTE_DIRECT
    assert legacy.read_bytes() == b"%PDF /a"


async def test_an_unreadable_manifest_only_costs_a_download(tmp_path: Path, monkeypatch):
    _install_transport(monkeypatch, _PathEchoTransport())
    a, b = _twins()
    await download_pdfs(_collection(a), tmp_path)
    (tmp_path / "pdfs" / ".owners.json").write_text("{not json", encoding="utf-8")
    result = (await download_pdfs(_collection(b), tmp_path))[0]
    assert result.path.read_bytes() == b"%PDF /b"


# --- the size cap holds while the body streams in (review R08) ---------------------


class _EndlessChunks(httpx.AsyncByteStream):
    """A body without Content-Length that counts the chunks it hands out."""

    def __init__(self, chunk: bytes, total: int) -> None:
        self.chunk = chunk
        self.total = total
        self.served = 0
        self.closed = False

    async def __aiter__(self):
        while self.served < self.total:
            self.served += 1
            yield self.chunk

    async def aclose(self) -> None:
        self.closed = True


class _StreamTransport(httpx.AsyncBaseTransport):
    def __init__(self, stream: _EndlessChunks) -> None:
        self.stream = stream

    async def handle_async_request(self, request):
        return httpx.Response(
            200, stream=self.stream,
            headers={"content-type": "application/pdf"}, request=request,
        )

    async def aclose(self):
        return None


async def test_an_oversized_chunked_body_stops_at_the_cap(tmp_path: Path, monkeypatch):
    """The body was read in full before its length was checked, so every
    parallel download could hold a whole oversized file in memory."""
    monkeypatch.setattr(pdf_download_module, "_MAX_PDF_BYTES", 2500)
    stream = _EndlessChunks(b"%PDF" + b"x" * 996, total=100)
    _install_transport(monkeypatch, _StreamTransport(stream))
    result = (await download_pdfs(_collection(_paper()), tmp_path))[0]
    assert result.skipped_reason == "too_large"
    assert stream.served == 3
    assert stream.closed


async def test_download_pdfs_too_large_is_skipped(tmp_path: Path, monkeypatch):
    big_body = b"%PDF-1.4" + b"x" * (pdf_download_module._MAX_PDF_BYTES + 10)  # noqa: SLF001
    transport = _CannedTransport(200, big_body)
    _install_transport(monkeypatch, transport)
    results = await download_pdfs(_collection(_paper()), tmp_path)
    assert results[0].path is None
    assert results[0].skipped_reason == "too_large"


async def test_download_pdfs_filename_is_sanitised(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    paper = _paper(
        authors=("Über Müller",),
        title="Weird/Title: With * Bad ? chars",
    )
    results = await download_pdfs(_collection(paper), tmp_path)
    assert results[0].path is not None
    name = results[0].path.name
    assert name.endswith(".pdf")
    # No path separators or shell metacharacters survived.
    for forbidden in ("/", "\\", ":", "*", "?", "<", ">"):
        assert forbidden not in name


# ---------------------------------------------------------------------------
# Browser-header + cookie behaviour (added when publishers started returning
# 403 to non-browser UAs even on OpenAlex-supplied PDF URLs).
# ---------------------------------------------------------------------------


async def test_download_pdfs_sends_browser_user_agent(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    await download_pdfs(_collection(_paper()), tmp_path)
    headers = transport.request_headers[0]
    assert "Mozilla/5.0" in headers.get("user-agent", "")
    assert "application/pdf" in headers.get("accept", "")
    assert headers.get("accept-language", "").startswith("en")


async def test_download_pdfs_sends_referer_when_landing_host_matches(
    tmp_path: Path, monkeypatch,
):
    """Same-host Referer fixes the most common publisher 403."""
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    paper = _paper(
        url="https://example.com/article/123",
        pdf_url="https://example.com/pdf/123.pdf",
    )
    await download_pdfs(_collection(paper), tmp_path)
    assert transport.request_headers[0].get("referer") == paper.url


async def test_download_pdfs_omits_referer_on_cross_host(
    tmp_path: Path, monkeypatch,
):
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    paper = _paper(
        url="https://openalex.org/W123",
        pdf_url="https://arxiv.org/pdf/1706.03762",
    )
    await download_pdfs(_collection(paper), tmp_path)
    assert "referer" not in transport.request_headers[0]


async def test_download_pdfs_attaches_cookies_when_jar_set(
    tmp_path: Path, monkeypatch,
):
    """Cookies from THESISAGENTS_PDF_COOKIES_FILE must reach the request."""
    from thesisagents.core import pdf_cookies

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".example.com\tTRUE\t/\tFALSE\t0\tJSESSIONID\tabc123\n"
        ".example.com\tTRUE\t/\tFALSE\t0\tauth_token\txyz789\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THESISAGENTS_PDF_COOKIES_FILE", str(cookies_file))
    pdf_cookies._reset_for_tests()  # noqa: SLF001

    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    paper = _paper(
        url="https://example.com/article/123",
        pdf_url="https://example.com/pdf/123.pdf",
    )
    await download_pdfs(_collection(paper), tmp_path / "out")
    cookie_header = transport.request_headers[0].get("cookie", "")
    assert "JSESSIONID=abc123" in cookie_header
    assert "auth_token=xyz789" in cookie_header


async def test_download_pdfs_no_cookies_when_env_unset(
    tmp_path: Path, monkeypatch,
):
    from thesisagents.core import pdf_cookies

    monkeypatch.delenv("THESISAGENTS_PDF_COOKIES_FILE", raising=False)
    pdf_cookies._reset_for_tests()  # noqa: SLF001

    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    await download_pdfs(_collection(_paper()), tmp_path)
    assert "cookie" not in transport.request_headers[0]


async def test_cookies_only_attach_to_matching_host(
    tmp_path: Path, monkeypatch,
):
    """A cookie scoped to ``.publisher.com`` must NOT leak to ``arxiv.org``."""
    from thesisagents.core import pdf_cookies

    cookies_file = tmp_path / "cookies.txt"
    cookies_file.write_text(
        "# Netscape HTTP Cookie File\n"
        ".publisher.com\tTRUE\t/\tFALSE\t0\tSECRET\tdo-not-leak\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THESISAGENTS_PDF_COOKIES_FILE", str(cookies_file))
    pdf_cookies._reset_for_tests()  # noqa: SLF001

    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    paper = _paper(pdf_url="https://arxiv.org/pdf/1706.03762")
    await download_pdfs(_collection(paper), tmp_path / "out")
    cookie_header = transport.request_headers[0].get("cookie", "")
    assert "SECRET" not in cookie_header
    assert "do-not-leak" not in cookie_header


async def test_download_pdfs_caps_concurrency(tmp_path: Path, monkeypatch):
    """A semaphore bounds simultaneous downloads so a big collection doesn't
    hammer a single publisher CDN with one request per paper at once."""
    import asyncio

    # dict (not nonlocal ints) so the counter mutation is visible to static
    # analysers that don't trace the monkeypatched async call path.
    counters = {"active": 0, "peak": 0}

    async def fake_download_one(paper, pdf_dir):
        counters["active"] += 1
        counters["peak"] = max(counters["peak"], counters["active"])
        await asyncio.sleep(0.01)
        counters["active"] -= 1
        return pdf_download_module.PdfDownloadResult(
            paper_key=paper.source_id, path=None, skipped_reason=None
        )

    monkeypatch.setattr(pdf_download_module, "_download_one", fake_download_one)
    papers = [_paper(source_id=str(i), pdf_url="https://e/p.pdf") for i in range(8)]
    results = await download_pdfs(_collection(*papers), tmp_path, concurrency=3)
    assert len(results) == 8
    assert 1 <= counters["peak"] <= 3  # never more than the cap in flight at once


async def test_download_pdfs_isolates_a_hard_failure(tmp_path: Path, monkeypatch):
    """One paper raising must not discard the PDFs already written for others.

    The soft failures (404, wrong content-type, oversized body) are already
    turned into results; what's left is the hard kind — an ``OSError`` from a
    full disk or a path the filesystem rejects. Letting one propagate out of
    ``asyncio.gather`` threw away every PDF the sibling tasks had saved.
    """
    transport = _CannedTransport(200, b"%PDF-1.4\nfake bytes")
    _install_transport(monkeypatch, transport)
    good = _paper(source_id="good", title="Good Paper")
    bad = _paper(source_id="bad", title="Bad Paper")
    real_fetch = pdf_download_module._fetch_and_validate  # noqa: SLF001

    async def _explode(paper, target, key):
        if paper.source_id == "bad":
            raise OSError(28, "No space left on device")
        return await real_fetch(paper, target, key)

    monkeypatch.setattr(pdf_download_module, "_fetch_and_validate", _explode)
    results = await download_pdfs(_collection(good, bad), tmp_path)

    assert len(results) == 2
    saved, failed = results
    assert saved.path is not None
    assert saved.path.exists()
    assert failed.path is None
    assert failed.skipped_reason == "error_OSError"


# --- the route each PDF took (progress #31) ------------------------------------

_PAYWALLED = "https://dl.acm.org/doi/pdf/10.1145/1"


def _browser(monkeypatch, *, available: bool, succeeds: bool = True) -> list[str]:
    """Stub the visible-Chrome downloader and return the URLs it was given."""
    from thesisagents.fetchers import webrunner_pdf

    visited: list[str] = []

    async def fake_download(url: str, target: Path) -> bool:
        visited.append(url)
        if succeeds:
            target.write_bytes(b"%PDF-1.4\nfrom the browser")
        return succeeds

    monkeypatch.setattr(webrunner_pdf, "is_available", lambda: available)
    monkeypatch.setattr(webrunner_pdf, "download_via_browser", fake_download)
    return visited


async def test_an_open_pdf_is_fetched_directly(tmp_path: Path, monkeypatch):
    _install_transport(monkeypatch, _CannedTransport(200, b"%PDF-1.4\nx"))
    visited = _browser(monkeypatch, available=True)
    result = (await download_pdfs(_collection(_paper()), tmp_path))[0]
    assert result.route == pdf_download_module.ROUTE_DIRECT
    assert visited == []


async def test_a_publisher_pdf_goes_through_the_browser(tmp_path: Path, monkeypatch):
    transport = _CannedTransport(200, b"%PDF-1.4\nx")
    _install_transport(monkeypatch, transport)
    visited = _browser(monkeypatch, available=True)
    result = (await download_pdfs(_collection(_paper(pdf_url=_PAYWALLED)), tmp_path))[0]
    assert result.route == pdf_download_module.ROUTE_BROWSER
    assert visited == [_PAYWALLED]
    assert transport.calls == []


async def test_a_browser_failure_is_retried_directly_and_logged(
    tmp_path: Path, monkeypatch, caplog
):
    _install_transport(monkeypatch, _CannedTransport(403, b"denied", "text/html"))
    _browser(monkeypatch, available=True, succeeds=False)
    with caplog.at_level("WARNING", logger="thesisagents.core.pdf_download"):
        result = (await download_pdfs(_collection(_paper(pdf_url=_PAYWALLED)), tmp_path))[0]
    assert result.route == pdf_download_module.ROUTE_DIRECT_BROWSER_FAILED
    assert result.path is None
    assert any("browser could not fetch" in record.getMessage() for record in caplog.records)


async def test_a_missing_browser_is_no_longer_silent(tmp_path: Path, monkeypatch, caplog):
    """Before #31 a paywalled URL went to httpx with no log line at all when
    browser automation was unavailable."""
    _install_transport(monkeypatch, _CannedTransport(403, b"denied", "text/html"))
    visited = _browser(monkeypatch, available=False)
    with caplog.at_level("WARNING", logger="thesisagents.core.pdf_download"):
        result = (await download_pdfs(_collection(_paper(pdf_url=_PAYWALLED)), tmp_path))[0]
    assert result.route == pdf_download_module.ROUTE_DIRECT_NO_BROWSER
    assert visited == []
    assert any("browser automation is unavailable" in r.getMessage() for r in caplog.records)


async def test_a_pdf_already_on_disk_reports_its_route(tmp_path: Path, monkeypatch):
    _install_transport(monkeypatch, _CannedTransport(200, b"%PDF-1.4\nx"))
    first = (await download_pdfs(_collection(_paper()), tmp_path))[0]
    again = (await download_pdfs(_collection(_paper()), tmp_path))[0]
    assert first.route == pdf_download_module.ROUTE_DIRECT
    assert again.route == pdf_download_module.ROUTE_ON_DISK


async def test_a_publisher_link_named_by_a_page_goes_through_the_browser(
    tmp_path: Path, monkeypatch
):
    """The second hop (``citation_pdf_url``) skipped the routing of the first
    and sent a paywalled publisher a direct request."""
    page = f'<html><head><meta name="citation_pdf_url" content="{_PAYWALLED}"></head></html>'
    transport = _CannedTransport(200, page.encode(), "text/html")
    _install_transport(monkeypatch, transport)
    visited = _browser(monkeypatch, available=True)
    result = (await download_pdfs(_collection(_paper()), tmp_path))[0]
    assert visited == [_PAYWALLED]
    assert result.route == pdf_download_module.ROUTE_BROWSER
    assert result.path is not None
    assert len(transport.calls) == 1


async def test_one_host_gets_at_most_two_downloads_at_once(tmp_path: Path, monkeypatch):
    running = {"a.example": 0, "b.example": 0}
    peak = dict(running)

    async def fake_one(paper, pdf_dir):
        host = paper.pdf_url.split("/")[2]
        running[host] += 1
        peak[host] = max(peak[host], running[host])
        await asyncio.sleep(0.01)
        running[host] -= 1
        return pdf_download_module.PdfDownloadResult(paper.source_id, None, "x")

    monkeypatch.setattr(pdf_download_module, "_download_one", fake_one)
    papers = [
        _paper(source_id=str(i), pdf_url=f"https://{'ab'[i % 2]}.example/{i}.pdf")
        for i in range(12)
    ]
    await download_pdfs(_collection(*papers), tmp_path)
    assert peak == {"a.example": 2, "b.example": 2}

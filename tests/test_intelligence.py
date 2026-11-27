"""Tests for the intelligence pipeline (PDF extract + LLM summary)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from thesisagents.core.exceptions import ConfigError, ParseError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.core.pipeline import enrich_collection
from thesisagents.fetchers import http as http_module
from thesisagents.intelligence import pdf as pdf_module
from thesisagents.intelligence import providers
from thesisagents.intelligence import summarise as summarise_module


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


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------


_FAKE_PDF_BODY = b"%PDF-1.4 ...content elided..."


def _install_pdf_transport(monkeypatch, transport):
    http_module._CLIENTS.clear()  # noqa: SLF001

    async def fake_get_client(_source):
        return httpx.AsyncClient(transport=transport)

    # The text fetch shares the downloader's routing, so its client is that
    # module's. The old private client is patched too (when present) so a
    # regression test run against the old code fails on its assertion.
    monkeypatch.setattr("thesisagents.core.pdf_download.get_client", fake_get_client)
    monkeypatch.setattr("thesisagents.intelligence.pdf.get_client", fake_get_client, raising=False)


class _CannedPdfTransport(httpx.AsyncBaseTransport):
    def __init__(self, status: int, body: bytes, content_type: str = "application/pdf"):
        self.status = status
        self.body = body
        self.content_type = content_type

    async def handle_async_request(self, request):
        return httpx.Response(
            self.status, content=self.body,
            headers={"content-type": self.content_type},
            request=request,
        )

    async def aclose(self):
        return None


def _patch_pypdf_to_return(monkeypatch, text: str, pages: int = 3):
    class _FakePage:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _FakeReader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [_FakePage(text)] * pages

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)


async def test_fetch_and_extract_happy_path(monkeypatch):
    transport = _CannedPdfTransport(200, _FAKE_PDF_BODY)
    _install_pdf_transport(monkeypatch, transport)
    _patch_pypdf_to_return(monkeypatch, "Some text from a page.\nNext line.\n\nNew paragraph.")
    result = await pdf_module.fetch_and_extract(
        "https://arxiv.org/pdf/1706.03762", source="arxiv"
    )
    assert result.page_count == 3
    assert "Some text from a page" in result.text


async def test_fetch_and_extract_rejects_non_pdf(monkeypatch):
    transport = _CannedPdfTransport(200, b"<html>nope</html>", content_type="text/html")
    _install_pdf_transport(monkeypatch, transport)
    with pytest.raises(ParseError):
        await pdf_module.fetch_and_extract(
            "https://example.com/paper", source="arxiv"
        )


async def test_fetch_and_extract_size_cap(monkeypatch):
    big = b"%PDF-1.4" + b"x" * (pdf_module.MAX_PDF_BYTES + 100)
    transport = _CannedPdfTransport(200, big)
    _install_pdf_transport(monkeypatch, transport)
    with pytest.raises(ParseError):
        await pdf_module.fetch_and_extract(
            "https://arxiv.org/pdf/big", source="arxiv"
        )


async def test_fetch_and_extract_4xx_raises(monkeypatch):
    transport = _CannedPdfTransport(403, b"forbidden", content_type="text/plain")
    _install_pdf_transport(monkeypatch, transport)
    with pytest.raises(ParseError):
        await pdf_module.fetch_and_extract(
            "https://arxiv.org/pdf/forbidden", source="arxiv"
        )


# ---------------------------------------------------------------------------
# Summarisation (mocked Anthropic client)
# ---------------------------------------------------------------------------


def _fake_anthropic_module(response_text: str):
    """Build a `module-like` mock so summarise_module's lazy import picks it up."""
    captured: dict = {}

    def _fake_client_factory(*, api_key: str):
        class _Client:
            def __init__(self):
                self.messages = _Messages()
                self.beta = MagicMock()
                self.beta.messages = _Messages()

        class _Messages:
            def create(self, **kwargs):  # noqa: ARG002  # mock signature mirrors the SDK
                captured["kwargs"] = kwargs
                thinking = MagicMock()
                thinking.type = "thinking"
                block = MagicMock()
                block.type = "text"
                block.text = response_text
                response = MagicMock()
                response.content = [thinking, block]
                response.stop_reason = captured.get("stop_reason", "end_turn")
                response.stop_details = MagicMock(category="cyber")
                return response

        captured["api_key"] = api_key
        return _Client()

    module = MagicMock()
    module.Anthropic = _fake_client_factory
    return module, captured


def test_summariser_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fake_anthropic, _ = _fake_anthropic_module("{}")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", fake_anthropic
    )
    paper = _paper()
    pdf = pdf_module.ExtractedPdf(
        url=paper.pdf_url, page_count=1, chars=10, text="text"
    )
    with pytest.raises(ConfigError):
        summarise_module.summarise_paper(paper, pdf, language="en")


def test_summariser_parses_response(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    response_text = (
        '{\n'
        '  "motivation": ["Transformers were not yet established."],\n'
        '  "contributions": ["Pure attention; no recurrence; no convolution."],\n'
        '  "method": ["Self-attention with multi-head + sinusoidal positions."],\n'
        '  "results": ["28.4 BLEU on WMT En→De (+2 BLEU)."],\n'
        '  "limitations": ["Quadratic memory in sequence length."],\n'
        '  "takeaways": ["Attention alone suffices for translation."]\n'
        '}'
    )
    fake_anthropic, captured = _fake_anthropic_module(response_text)
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", fake_anthropic
    )
    paper = _paper()
    pdf = pdf_module.ExtractedPdf(
        url=paper.pdf_url, page_count=12, chars=50_000, text="full paper text..."
    )
    summary = summarise_module.summarise_paper(paper, pdf, language="zh-tw")
    assert summary.language == "zh-tw"
    assert summary.motivation == ("Transformers were not yet established.",)
    assert len(summary.contributions) == 1
    assert len(summary.results) == 1
    assert summary.model.startswith("claude")
    assert summary.raw_text_chars == 50_000
    # System prompt should be cache-controlled.
    system = captured["kwargs"]["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_summariser_tolerates_markdown_fenced_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    response_text = (
        "Here is the summary:\n\n```json\n"
        '{"motivation": ["m1"], "contributions": ["c1"], "method": [],\n'
        ' "results": [], "limitations": [], "takeaways": ["t1"]}\n'
        "```"
    )
    fake_anthropic, _ = _fake_anthropic_module(response_text)
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", fake_anthropic
    )
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=10, text="t")
    summary = summarise_module.summarise_paper(_paper(), pdf, language="en")
    assert summary.motivation == ("m1",)
    assert summary.takeaways == ("t1",)


def test_the_current_model_gets_room_to_think_and_a_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("THESISAGENTS_LLM_MODEL", raising=False)
    fake_anthropic, captured = _fake_anthropic_module('{"takeaways": ["t1"]}')
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=10, text="t")
    summary = summarise_module.summarise_paper(_paper(), pdf, language="en")
    sent = captured["kwargs"]
    assert summary.takeaways == ("t1",)
    assert sent["model"] == "claude-opus-5-5"
    assert sent["max_tokens"] >= 16_000
    assert sent["output_config"] == {"effort": "medium"}
    assert sent["fallbacks"] == "default"
    assert "temperature" not in sent and "thinking" not in sent


def test_an_older_model_gets_the_plain_request(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("THESISAGENTS_LLM_MODEL", "claude-haiku-4-5")
    fake_anthropic, captured = _fake_anthropic_module('{"takeaways": ["t1"]}')
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=10, text="t")
    summarise_module.summarise_paper(_paper(), pdf, language="en")
    assert "output_config" not in captured["kwargs"]
    assert "fallbacks" not in captured["kwargs"]


@pytest.mark.parametrize(("stop", "message"), [
    ("refusal", r"declined this paper \(cyber\)"), ("max_tokens", "cut off"),
])
def test_a_refusal_or_a_cut_answer_is_named(monkeypatch, stop, message):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("THESISAGENTS_LLM_MODEL", raising=False)
    fake_anthropic, captured = _fake_anthropic_module('{"takeaways": ["t1"]}')
    captured["stop_reason"] = stop
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=10, text="t")
    with pytest.raises(ParseError, match=message):
        summarise_module.summarise_paper(_paper(), pdf, language="en")


def test_summariser_rejects_non_json(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    fake_anthropic, _ = _fake_anthropic_module("I refuse to comply.")
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", fake_anthropic
    )
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=10, text="t")
    paper = _paper()
    with pytest.raises(ParseError):
        summarise_module.summarise_paper(paper, pdf, language="en")


def test_terminal_summary_keeps_thesis_fields_and_records_its_input(monkeypatch):
    def complete(_settings, instructions, prompt):
        assert "headline_metrics" in instructions
        assert "Traditional Chinese" in prompt
        assert "paper text" in prompt
        return json.dumps({
            "research_question": "Which method scored higher?",
            "contributions_detailed": [[str(index), "claim"] for index in range(5)],
            "method_sections": [["Study", ["Two groups."]]],
            "headline_metrics": [["Score", "80%", "70%"]],
            "rq_results": [{"rq_id": "RQ1", "question": "Which scored higher?",
                            "table": [["Group", "Score"], ["A", "80%"]],
                            "analysis": ["Group A scored higher."]}],
            "future_work": ["Repeat the study."],
            "findings": ["Group A scored higher."],
            "language": "ru", "model": "wrong", "raw_text_chars": 1,
            "figures": [["Untrusted path", "private.png", []]],
        })

    monkeypatch.setattr(providers, "complete", complete)
    settings = providers.resolve("cli")
    summary = summarise_module.summarise_with(settings, _paper(), "paper text", "zh-tw", 10)
    assert summary.has_rich_fields()
    assert summary.research_question == "Which method scored higher?"
    assert summary.contributions_detailed == tuple((str(i), "claim") for i in range(4))
    assert summary.method_sections == (("Study", ("Two groups.",)),)
    assert summary.headline_metrics == (("Score", "80%", "70%"),)
    assert summary.rq_results[0].table == (("Group", "Score"), ("A", "80%"))
    assert summary.future_work == ("Repeat the study.",)
    assert summary.limitations == ()
    assert summary.results == ("Group A scored higher.",)
    assert summary.language == "zh-tw"
    assert summary.model == settings.provider.label
    assert summary.raw_text_chars == 10
    assert summary.figures == ()


async def test_malformed_terminal_result_keeps_the_existing_summary(monkeypatch, caplog):
    async def fetch(url, **_kwargs):
        return pdf_module.ExtractedPdf(url=url, page_count=1, chars=4, text="body")

    paper = _paper(summary=PaperSummary(language="en", research_question="Original question?"))
    collection = PaperCollection(query=Query(keywords="x", sources=("arxiv",)), papers=(paper,))
    monkeypatch.setattr(pdf_module, "fetch_and_extract", fetch)
    monkeypatch.setattr(
        providers, "complete", lambda *_: '{"method_sections": [["Heading", [42]]]}',
    )
    result = await enrich_collection(collection, language="en", provider="cli")
    assert result.papers[0].summary == paper.summary
    assert "invalid summary field method_sections" in caplog.text


# ---------------------------------------------------------------------------
# Enrichment pipeline (skips bad papers, attaches summary on success)
# ---------------------------------------------------------------------------


async def test_enrich_collection_skips_papers_without_pdf(monkeypatch):
    paper_no_pdf = _paper(pdf_url=None)
    coll = PaperCollection(
        query=Query(keywords="x", sources=("arxiv",), max_results=1),
        papers=(paper_no_pdf,),
    )
    out = await enrich_collection(coll, language="en")
    assert out.papers[0].summary is None


async def test_enrich_collection_attaches_summary(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    async def fake_fetch(url, source="arxiv"):
        return pdf_module.ExtractedPdf(
            url=url, page_count=1, chars=100, text="fake paper content"
        )

    response_text = (
        '{"motivation": ["m"], "contributions": ["c"], "method": ["meth"],\n'
        ' "results": ["r"], "limitations": [], "takeaways": ["t"]}'
    )
    fake_anthropic, _ = _fake_anthropic_module(response_text)
    monkeypatch.setitem(
        __import__("sys").modules, "anthropic", fake_anthropic
    )
    monkeypatch.setattr(
        "thesisagents.intelligence.pdf.fetch_and_extract", fake_fetch
    )

    paper = _paper()
    coll = PaperCollection(
        query=Query(keywords="x", sources=("arxiv",), max_results=1),
        papers=(paper,),
    )
    out = await enrich_collection(coll, language="en")
    summary = out.papers[0].summary
    assert summary is not None
    assert summary.motivation == ("m",)
    assert summary.takeaways == ("t",)
    assert summary.language == "en"


# ---------------------------------------------------------------------------
# One fetch route for text and downloads (review R07) and the streamed cap (R08)
# ---------------------------------------------------------------------------

_PUBLISHER_PDF = "https://dl.acm.org/doi/pdf/10.1145/1"


def _browser_gets(monkeypatch, body: bytes) -> list[str]:
    """Stub visible Chrome as succeeding with ``body``. Returns the URLs it opened."""
    from thesisagents.fetchers import webrunner_pdf

    visited: list[str] = []

    async def fake_download(url, target):
        visited.append(url)
        target.write_bytes(body)
        return True

    monkeypatch.setattr(webrunner_pdf, "is_available", lambda: True)
    monkeypatch.setattr(webrunner_pdf, "download_via_browser", fake_download)
    return visited


def _echo_extract(monkeypatch) -> None:
    """Make the "extracted text" the PDF bytes, so a test sees which file was read."""
    monkeypatch.setattr(
        "thesisagents.intelligence.pdf._extract_text",
        lambda body, source: (body.decode(), 1),  # noqa: ARG005  # signature mirror
    )


async def test_fetch_and_extract_sends_a_publisher_pdf_to_the_browser(monkeypatch):
    """A plain request to a publisher is refused (403 here). The text fetch
    used one, while the downloader got the same PDF through Chrome."""
    transport = _CannedPdfTransport(403, b"denied", content_type="text/html")
    _install_pdf_transport(monkeypatch, transport)
    visited = _browser_gets(monkeypatch, b"%PDF-1.4 from chrome")
    _echo_extract(monkeypatch)
    result = await pdf_module.fetch_and_extract(_PUBLISHER_PDF, source="acm")
    assert result.text == "%PDF-1.4 from chrome"
    assert visited == [_PUBLISHER_PDF]


class _CountedChunks(httpx.AsyncByteStream):
    """A body without Content-Length that counts the chunks it hands out."""

    def __init__(self) -> None:
        self.served = 0
        self.closed = False

    async def __aiter__(self):
        while self.served < 100:
            self.served += 1
            yield b"%PDF" + b"x" * 996

    async def aclose(self):
        self.closed = True


class _ChunkTransport(httpx.AsyncBaseTransport):
    def __init__(self, stream):
        self.stream = stream

    async def handle_async_request(self, request):
        return httpx.Response(
            200, stream=self.stream, headers={"content-type": "application/pdf"},
            request=request,
        )

    async def aclose(self):
        return None


async def test_fetch_and_extract_stops_reading_past_the_cap(monkeypatch):
    """The whole body was read before the cap was checked."""
    monkeypatch.setattr(pdf_module, "MAX_PDF_BYTES", 2500)
    stream = _CountedChunks()
    _install_pdf_transport(monkeypatch, _ChunkTransport(stream))
    with pytest.raises(ParseError, match="cap"):
        await pdf_module.fetch_and_extract("https://arxiv.org/pdf/big", source="arxiv")
    assert stream.served == 3
    assert stream.closed


async def test_enrich_collection_reads_the_pdf_already_on_disk(monkeypatch, tmp_path):
    """A saved PDF is summarised from the file, with no request at all."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    saved = tmp_path / "paper.pdf"
    saved.write_bytes(b"%PDF-1.4 saved earlier")
    _echo_extract(monkeypatch)

    async def no_fetch(*_args, **_kwargs):
        raise AssertionError("a saved PDF must not be fetched again")

    monkeypatch.setattr(pdf_module, "fetch_and_extract", no_fetch)
    seen: list[str] = []

    def fake_summarise(_paper, pdf, **_kwargs):
        seen.append(pdf.text)
        return PaperSummary(language="en", takeaways=("t",))

    monkeypatch.setattr(summarise_module, "summarise_paper", fake_summarise)
    coll = PaperCollection(
        query=Query(keywords="x", sources=("arxiv",), max_results=2),
        papers=(_paper(), _paper(source_id="2", pdf_url=None)),
    )
    out = await enrich_collection(coll, language="en", local_pdfs=[saved, None])
    assert seen == ["%PDF-1.4 saved earlier"]
    assert out.papers[0].summary is not None
    assert out.papers[1].summary is None


async def test_enrich_collection_rejects_misaligned_local_pdfs(tmp_path):
    coll = PaperCollection(
        query=Query(keywords="x", sources=("arxiv",), max_results=1), papers=(_paper(),),
    )
    with pytest.raises(ValueError, match="local_pdfs"):
        await enrich_collection(coll, language="en", local_pdfs=[])

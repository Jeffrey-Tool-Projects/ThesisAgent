"""Inputs that used to lose data or end a whole run, outside the source parsers."""
from __future__ import annotations

import asyncio
import io
import threading

import httpx
import pytest

from thesisagents import cli
from thesisagents.core import pdf_cookies, pdf_download
from thesisagents.core.bib_import import parse_bibtex
from thesisagents.core.comparison import comparison_rows
from thesisagents.core.exceptions import ConfigError, ParseError
from thesisagents.core.export_validation import (
    VerificationStatus,
    _probe_url,
    verify_collection,
)
from thesisagents.core.local_pdf import build_local_collection
from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.core.oa_resolver import resolve_oa_pdfs
from thesisagents.core.ranking import rank
from thesisagents.core.summary_text import summary_to_texts, texts_to_summary
from thesisagents.core.top_venues import is_top_tier
from thesisagents.evaluation import judge
from thesisagents.evaluation.search_quality import evaluate_query
from thesisagents.fetchers import http as http_module
from thesisagents.fetchers import webrunner_browser, webrunner_pdf
from thesisagents.intelligence import providers
from thesisagents.intelligence.pdf import _extract_text
from thesisagents.intelligence.pdf_metadata import extract_metadata


def _paper(source_id: str = "1", **fields) -> Paper:
    defaults = {
        "source": "arxiv", "title": "Deep nets", "authors": ("Wei Wang",), "year": 2023,
        "venue": None, "abstract": "", "url": f"https://example.org/{source_id}",
    }
    return Paper(source_id=source_id, **{**defaults, **fields})


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(Query("x", ("arxiv",)), papers)


# --- summaries an agent wrote -----------------------------------------------------------


def _from_dict(**summary) -> PaperSummary:
    record = _paper().to_dict()
    record["summary"] = {"language": "en", **summary}
    return Paper.from_dict(record).summary


def test_a_sentence_instead_of_a_list_is_one_statement():
    summary = _from_dict(
        limitations="Only Java.", pain_points=[["Cost", "It is slow."]], takeaways="  ",
    )
    assert summary.limitations == ("Only Java.",)
    assert summary.pain_points == (("Cost", ("It is slow.",)),)
    assert summary.takeaways == ()


def test_short_rows_are_filled_up():
    summary = _from_dict(headline_metrics=[["F1", "0.9"]], technique_table=["Beam"])
    assert summary.headline_metrics == (("F1", "0.9", ""),)
    assert summary.technique_table == (("Beam", ""),)


def test_a_metric_without_a_baseline_does_not_fail_the_table():
    summary = PaperSummary(language="en", headline_metrics=(("F1", "0.9"),))
    assert comparison_rows([_paper(summary=summary)])[0].strengths == ("F1: 0.9",)


def test_summary_text_survives_marks_and_line_breaks():
    summary = PaperSummary(
        language="en",
        limitations=("first\nline",),
        pain_points=(("Cost", ("#1 cause is memory", "\\#2 is time")),),
        technique_table=(("a\nb", "c|d"),),
    )
    again = texts_to_summary(summary, summary_to_texts(summary))
    assert again.limitations == ("first line",)
    assert again.pain_points == summary.pain_points
    assert again.technique_table == (("a b", "c|d"),)


# --- bibliographies ---------------------------------------------------------------------


def test_addresses_are_not_typography():
    paper = parse_bibtex(
        r"@misc{a, title={T}, url={http://cs.edu/\~{}foo/a--b\_c.pdf}, doi={10.1000/a--b\_c}}"
    ).papers[0]
    assert paper.url == "http://cs.edu/~foo/a--b_c.pdf"
    assert paper.doi == "10.1000/a--b_c"


@pytest.mark.parametrize(("field", "authors"), [
    ("{Barnes and Noble, Inc.}", ("Barnes and Noble, Inc.",)),
    ("Lovelace, Ada and {The X, Y Group}", ("Ada Lovelace", "The X, Y Group")),
    ("{Lovelace}, {Ada}", ("Ada Lovelace",)),
])
def test_an_organisation_in_braces_is_no_person(field, authors):
    assert parse_bibtex(f"@misc{{a, title={{T}}, author={{{field}}}}}").papers[0].authors == authors


def test_quoted_bibtex_in_an_abstract_is_no_record():
    result = parse_bibtex("@misc{a, title={T}, abstract={see @misc{q, title={Ghost}} there}}")
    assert [p.title for p in result.papers] == ["T"]
    assert result.skipped == ()


@pytest.mark.parametrize(("text", "found"), [
    ("https://x.org/pdf/report/1234567", None),
    ("https://x.org/abs/2023.12345", None),
    ("https://arxiv.org/abs/1706.03762v2", "1706.03762v2"),
    ("CoRR, abs/1706.03762", "1706.03762"),
    ("arXiv preprint arXiv:1706.03762", "1706.03762"),
])
def test_only_arxiv_links_name_an_arxiv_paper(text, found):
    field = "url" if text.startswith("http") else "journal"
    assert parse_bibtex(f"@misc{{a, title={{T}}, {field}={{{text}}}}}").papers[0].arxiv_id == found


# --- identifiers ------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "https://exa mple.org/x", "http://[bad", "https://e.org:port/x", "https://",
])
async def test_a_url_that_is_none_is_reported_and_does_not_end_the_export(url):
    report = await verify_collection(_collection(_paper(url=url)))
    assert [check.status for check in report.checks] == [VerificationStatus.INVALID]


async def test_a_malformed_redirect_is_not_the_papers_fault(monkeypatch):
    async def redirect(_client, _url):
        return 302, "https://[bad"

    monkeypatch.setattr(
        "thesisagents.core.export_validation._status_and_location", redirect
    )
    verdict = await _probe_url(None, "https://example.org/1")
    assert verdict.status is VerificationStatus.SKIPPED
    assert not verdict.blocking


async def test_the_title_lookup_searches_titles(monkeypatch):
    asked = []

    class Fetcher:
        async def search(self, query):
            asked.append(query.keywords)
            return []

    monkeypatch.setattr("thesisagents.fetchers.base.load_fetcher", lambda _name: Fetcher())
    await resolve_oa_pdfs(_collection(_paper(source="dblp", title='A "quoted" title')))
    assert asked == ['ti:"A  quoted  title"']


# --- local PDFs -------------------------------------------------------------------------


def test_the_year_is_not_read_from_the_arxiv_stamp():
    text = "arXiv:2005.11401v4 [cs.CL] 12 Apr 2021\nA Title Of Some Length\nAnn Bee, Bo Cee\n"
    assert extract_metadata(text).year == 2021


def test_identifiers_come_from_the_front_page():
    text = (
        "A Title Of Some Length\nAnn Bee, Bo Cee\nAbstract\nWe study things.\n"
        + "word " * 2000 + "References [1] doi:10.1145/3292500.3330701 arXiv:1706.03762"
    )
    found = extract_metadata(text)
    assert (found.doi, found.arxiv_id) == (None, None)
    front = extract_metadata("A Title Of Some Length\ndoi:10.1145/3292500.3330701\n" + text)
    assert front.doi == "10.1145/3292500.3330701"


def test_an_encrypted_pdf_is_one_failed_paper():
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(100, 100)
    writer.encrypt("secret")
    body = io.BytesIO()
    writer.write(body)
    with pytest.raises(ParseError):
        _extract_text(body.getvalue(), "x")


def test_two_local_pdfs_with_one_title_keep_both_copies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "thesisagents.intelligence.pdf._extract_text",
        lambda body, source: ("The Same Long Title\nAnn Bee, Bo Cee\nAbstract\nText.", 1),
    )
    files = []
    for name in ("a", "b"):
        file = tmp_path / f"{name}.pdf"
        file.write_bytes(b"%PDF-1.4 " + name.encode())
        files.append(file)
    out = tmp_path / "out"
    for _run in range(2):
        build_local_collection(files, out)
    copies = {file.read_bytes() for file in (out / "pdfs").glob("*.pdf")}
    assert copies == {b"%PDF-1.4 a", b"%PDF-1.4 b"}
    assert len(list((out / "pdfs").glob("*.pdf"))) == 2


# --- downloads --------------------------------------------------------------------------


async def test_papers_with_one_cite_key_get_files_of_their_own(tmp_path, monkeypatch):
    def answer(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"%PDF " + request.url.path.encode())

    async def client(_source):
        return httpx.AsyncClient(transport=httpx.MockTransport(answer))

    monkeypatch.setattr(pdf_download, "get_client", client)
    papers = [
        _paper(str(i), doi=f"10.1000/{i}", pdf_url=f"https://e.example/{i}") for i in range(2)
    ]
    for _run in range(2):
        results = await pdf_download.download_pdfs(_collection(*papers), tmp_path)
        assert [r.path.read_bytes() for r in results] == [b"%PDF /0", b"%PDF /1"]
    assert [r.route for r in results] == ["on_disk", "on_disk"]


def test_a_failed_download_is_not_hidden_by_a_paper_with_the_same_key(tmp_path):
    papers = _collection(_paper("a", doi="10.1000/a"), _paper("b", doi="10.1000/b"))
    key = papers.papers[0].bibtex_key()
    results = [
        pdf_download.PdfDownloadResult(key, tmp_path / "a.pdf", None),
        pdf_download.PdfDownloadResult(key, None, "http_404"),
    ]
    found = cli._papers_with_pdf(papers, results)  # noqa: SLF001
    assert [p.source_id for p in found] == ["a"]
    # A caller with fewer results is matched by key.
    assert len(cli._papers_with_pdf(papers, results[:1])) == 2  # noqa: SLF001


def test_the_cookies_file_can_be_chosen_while_the_app_runs(tmp_path, monkeypatch):
    pdf_cookies._reset_for_tests()  # noqa: SLF001
    monkeypatch.delenv("THESISAGENTS_PDF_COOKIES_FILE", raising=False)
    assert pdf_cookies.cookies_for_url("https://e.example/x") == {}
    file = tmp_path / "cookies.txt"
    file.write_text(
        "# Netscape HTTP Cookie File\ne.example\tFALSE\t/\tTRUE\t0\tsid\tabc\n", encoding="utf-8"
    )
    monkeypatch.setenv("THESISAGENTS_PDF_COOKIES_FILE", str(file))
    assert pdf_cookies.cookies_for_url("https://e.example/x") == {"sid": "abc"}
    monkeypatch.delenv("THESISAGENTS_PDF_COOKIES_FILE")
    assert pdf_cookies.cookies_for_url("https://e.example/x") == {}
    pdf_cookies._reset_for_tests()  # noqa: SLF001


def test_one_chrome_at_a_time_uses_the_users_profile(tmp_path, monkeypatch):
    running, peak, gate = [], [], threading.Lock()

    def driver(**_kwargs):
        with gate:
            running.append(1)
            peak.append(len(running))
        raise RuntimeError("no Chrome here")

    def left(*_args, **_kwargs):
        with gate:
            if running:
                running.pop()

    monkeypatch.setattr(webrunner_browser, "make_driver", driver)
    monkeypatch.setattr(webrunner_pdf.shutil, "rmtree", left)
    monkeypatch.setenv("THESISAGENTS_CHROME_PROFILE_DIR", str(tmp_path))

    async def run():
        return await asyncio.gather(*(
            webrunner_pdf.download_via_browser("https://dl.acm.org/x", tmp_path / f"{i}.pdf")
            for i in range(4)
        ))

    assert asyncio.run(run()) == [False] * 4
    assert max(peak) == 1
    monkeypatch.delenv("THESISAGENTS_CHROME_PROFILE_DIR")
    assert webrunner_pdf._profile_turn() is not webrunner_pdf._PROFILE_LOCK  # noqa: SLF001


# --- clients and event loops ------------------------------------------------------------


def test_every_event_loop_has_a_client_of_its_own():
    http_module._CLIENTS.clear()  # noqa: SLF001
    first = asyncio.run(http_module.get_client("x"))
    second = asyncio.run(http_module.get_client("x"))
    assert first is not second
    # The client of the loop that ended is forgotten.
    assert [c for c in http_module._CLIENTS.values() if c is first] == []  # noqa: SLF001
    http_module._CLIENTS.clear()  # noqa: SLF001


def test_the_end_of_one_run_leaves_another_runs_clients_open():
    http_module._CLIENTS.clear()  # noqa: SLF001
    ready, finish = threading.Event(), threading.Event()
    closed: list[bool] = []

    async def other():
        client = await http_module.get_client("x")
        assert await http_module.get_client("x") is client
        ready.set()
        while not finish.is_set():
            await asyncio.sleep(0.01)
        closed.append(client.is_closed)
        await http_module.shutdown_clients()
        closed.append(client.is_closed)

    thread = threading.Thread(target=lambda: asyncio.run(other()))
    thread.start()
    assert ready.wait(5)
    asyncio.run(http_module.shutdown_clients())
    finish.set()
    thread.join(5)
    assert closed == [False, True]
    assert http_module._CLIENTS == {}  # noqa: SLF001


# --- models -----------------------------------------------------------------------------


def test_an_address_that_is_none_is_a_config_error():
    settings = providers.resolve("custom", model="m", base_url="http://host:notaport/v1")
    assert providers.max_paper_chars(settings) > 0
    with pytest.raises(ConfigError, match="not a usable address"):
        providers.complete(settings, "s", "u")


def test_a_misspelt_provider_in_the_environment_costs_no_search(monkeypatch, capsys):
    monkeypatch.setenv(providers.PROVIDER_ENV, "olama")
    parse = cli.build_parser().parse_args
    assert cli._resolve_enrich_mode(parse(["-q", "x"])) == "skip-no-key"  # noqa: SLF001
    assert "olama" in cli._missing_model(parse(["-q", "x"]))  # noqa: SLF001
    with pytest.raises(ConfigError):
        cli._resolve_enrich_mode(parse(["-q", "x", "--llm-provider", "olama"]))  # noqa: SLF001


def test_the_notice_names_the_chosen_providers_problem(monkeypatch):
    for name in (providers.PROVIDER_ENV, providers.MODEL_ENV, "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    parse = cli.build_parser().parse_args
    assert "ANTHROPIC_API_KEY" in cli._missing_model(parse(["-q", "x"]))  # noqa: SLF001
    reason = cli._missing_model(parse(["-q", "x", "--llm-provider", "ollama"]))  # noqa: SLF001
    assert "no model is chosen for Ollama" in reason


# --- ranking and venues -----------------------------------------------------------------


@pytest.mark.parametrize(("query", "title"), [
    ("image", "Images"), ("language", "Languages"), ("code", "Codes"), ("database", "Databases"),
    ("process", "Processes"), ("study", "Studies"),
])
def test_a_plural_matches_its_singular(query, title):
    ranked = rank(
        [_paper("off", title="Something else", citation_count=10), _paper("on", title=title)],
        query, current_year=2024,
    )
    assert ranked[0].source_id == "on"


@pytest.mark.parametrize(("venue", "top"), [
    ("Nature", True), ("Science", True), ("Nature 632", True), ("Science (New York, N.Y.)", True),
    ("Science, vol. 384", True), ("ICSE 2024", True), ("CRYPTO 2023", True),
    ("International Journal of Computer Science and Network Security", False),
    ("Nature Medicine", True), ("Nature Reviews Immunology", True), ("Science Robotics", True),
    ("Nature Conservation", False), ("Nature and Culture", False),
    ("Computer Science Review", False), ("Signature Journal", False), ("Cryptography", False),
])
def test_short_venue_names_are_matched_as_names(venue, top):
    assert is_top_tier(_paper(source="openalex", venue=venue)) is top


# --- benchmarks -------------------------------------------------------------------------


async def _judged(payload, keywords, *papers):
    async def search(query):
        return PaperCollection(query, papers)

    return await judge.collect(
        payload, keywords, sources=("arxiv",), max_results=5, search=search
    )


async def test_queries_that_shorten_alike_keep_their_own_judgements():
    payload = await _judged({}, ["C++ testing"], _paper("1", doi="10.1/1"))
    payload["queries"][0]["relevance"] = {"10.1/1": 2}
    payload = await _judged(payload, ["C testing", "C++ testing"], _paper("2", doi="10.1/2"))
    assert [(q["keywords"], q["relevance"]) for q in payload["queries"]] == [
        ("C++ testing", {"10.1/1": 2}), ("C testing", {}),
    ]
    assert len({q["id"] for q in payload["queries"]}) == 2


async def test_a_search_that_found_nothing_keeps_the_earlier_ranking():
    payload = await _judged({}, ["graphs"], _paper("1", doi="10.1/1"))
    payload = await _judged(payload, ["graphs"])
    assert payload["queries"][0]["retrieved"] == ["10.1/1"]


def test_a_query_file_from_notepad_is_read(tmp_path, monkeypatch, capsys):
    asked = []

    async def search(query, **_kwargs):
        asked.append(query.keywords)
        return PaperCollection(query, ())

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", search)
    queries = tmp_path / "q.txt"
    queries.write_bytes("﻿graphs\r\n  # later\r\n".encode())
    assert judge.main(["collect", str(tmp_path / "b.json"), "--queries", str(queries)]) == 0
    assert asked == ["graphs"]


def test_a_paper_listed_twice_is_one_hit():
    result = evaluate_query(["a", "a", "b"], {"a": 1}, cutoff=3)
    assert (result["hits"], result["recall"]) == (1, 1.0)


async def test_a_doi_with_a_hash_is_looked_up_whole(monkeypatch):
    asked = []

    class Client:
        async def get(self, url, **_kwargs):
            asked.append(url)
            return httpx.Response(404)

    async def client(_source):
        return Client()

    async def nothing(_paper):
        return None

    monkeypatch.setenv("THESISAGENTS_CONTACT_EMAIL", "a@example.org")
    monkeypatch.setattr("thesisagents.core.oa_resolver.get_client", client)
    monkeypatch.setattr("thesisagents.core.oa_resolver._query_arxiv_title", nothing)
    await resolve_oa_pdfs(_collection(_paper(source="dblp", doi="10.1002/x<1::a>2.0#b")))
    assert len(asked) == 2
    assert all(url.endswith("10.1002/x%3C1%3A%3Aa%3E2.0%23b") for url in asked)

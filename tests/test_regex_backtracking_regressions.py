"""Regressions for the parser regexes rewritten for SonarCloud S8786 / S5857.

The old patterns (``\\s+and\\s+``, ``\\s+-\\s+``, ``\\s*\\biD\\b``,
``\\S+@\\S+\\.\\S+``, the ``citation_pdf_url`` meta-tag patterns and the IEEE
``\\{.*?\\};`` blob scan) backtracked over
long runs of spaces or characters: on 20,000 spaces they took 1 to 12 s,
the rewritten ones a few milliseconds. Each test keeps both halves: the
rewritten pattern still splits or matches where the old one did, and a
long hostile run finishes quickly. The IEEE case also pins a real bug the
lazy scan had: it stopped at the first ``};`` even inside a JSON string.
"""

from __future__ import annotations

import json
import time

import pytest

from thesisagents.core.exceptions import ParseError
from thesisagents.core.pdf_download import _find_citation_pdf_url
from thesisagents.intelligence import pdf_metadata
from thesisagents.sources.ieee.parser import parse_metadata_blob
from thesisagents.sources.scholar.parser import _META_SPLIT_RE

#: Generous: the rewritten patterns take milliseconds, the old ones seconds.
_FAST_SECONDS = 0.5
_RUN = " " * 20_000


def _elapsed(func) -> float:
    start = time.perf_counter()
    func()
    return time.perf_counter() - start


def _blob_page(title: str) -> str:
    blob = json.dumps({"articleNumber": "1", "title": title, "authors": []})
    return f"<script>xplGlobal.document.metadata={blob};</script>"


def test_an_ieee_title_holding_a_brace_semicolon_parses_whole():
    paper = parse_metadata_blob(_blob_page("A }; B"))
    assert paper.title == "A }; B"


def test_an_ieee_page_without_the_blob_is_still_a_parse_error():
    with pytest.raises(ParseError, match="not found"):
        parse_metadata_blob("<html lang='en'><body>no blob</body></html>")


def test_an_ieee_page_with_a_long_unclosed_blob_fails_fast():
    page = "xplGlobal.document.metadata={" + "x" * 200_000
    with pytest.raises(ParseError):
        parse_metadata_blob(page)


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        ("Ada Lovelace and Alan Turing", ["Ada Lovelace", "Alan Turing"]),
        ("Ada Lovelace   and  Alan Turing", ["Ada Lovelace", "Alan Turing"]),
        (
            "Ada Lovelace, Alan Turing; Grace Hopper",
            ["Ada Lovelace", "Alan Turing", "Grace Hopper"],
        ),
    ],
)
def test_the_author_separator_splits_as_before(text, parts):
    assert pdf_metadata._AUTHOR_SEPARATOR_RE.split(text) == parts


def test_the_author_separator_is_fast_on_a_long_space_run():
    split = pdf_metadata._AUTHOR_SEPARATOR_RE.split
    assert _elapsed(lambda: split("a" + _RUN + "b")) < _FAST_SECONDS


def test_the_orcid_marker_is_removed_and_fast():
    text = "Athanasios Zeris iD 0009-0002-6907-2400"
    assert pdf_metadata._ORCID_RE.sub(" ", text).split() == ["Athanasios", "Zeris"]
    assert _elapsed(lambda: pdf_metadata._ORCID_RE.sub(" ", "a" + _RUN + "b")) < _FAST_SECONDS


def test_the_email_check_matches_and_is_fast():
    has_email = pdf_metadata._has_email_token
    assert has_email("contact ada@example.org now")
    assert not has_email("no address here")
    assert not has_email("@mit.edu a@.b")
    assert _elapsed(lambda: has_email("@" * 200_000)) < _FAST_SECONDS


def test_the_scholar_meta_split_matches_and_is_fast():
    meta = "A Vaswani, N Shazeer - NeurIPS, 2017 - proceedings.neurips.cc"
    assert _META_SPLIT_RE.split(meta) == [
        "A Vaswani, N Shazeer",
        "NeurIPS, 2017",
        "proceedings.neurips.cc",
    ]
    assert _elapsed(lambda: _META_SPLIT_RE.split("a" + _RUN + "b")) < _FAST_SECONDS


@pytest.mark.parametrize(
    "head",
    [
        b'<meta name="citation_pdf_url" content="/a.pdf">',
        b'<meta content="/a.pdf" name="citation_pdf_url">',
        b"<META NAME='citation_pdf_url' CONTENT='/a.pdf' />",
    ],
    ids=["name-then-content", "content-then-name", "upper-case-single-quotes"],
)
def test_the_citation_pdf_url_tag_is_read_in_either_attribute_order(head):
    assert _find_citation_pdf_url(b"<head>" + head + b"</head>") == b"/a.pdf"


def test_a_long_unclosed_meta_tag_is_scanned_fast():
    head = b'<meta name="citation_pdf_url" ' + b"x" * 20_000
    assert _elapsed(lambda: _find_citation_pdf_url(head)) < _FAST_SECONDS

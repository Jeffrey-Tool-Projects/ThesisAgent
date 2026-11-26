"""Tests for building papers from local PDFs (``core/local_pdf.py``).

Covers the core function the CLI's ``--pdf`` mode and the GUI's *Use local
PDFs…* share (``progress.md`` #29), the CLI wrapper's flag mapping, and the
refusals for bad files. The PDFs are written by the test itself, small but
real enough for pypdf to extract their text.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

pytest.importorskip("pypdf", reason="install thesisagents[intelligence]")

from thesisagents.cli_local_pdf import build_from_local_pdf  # noqa: E402
from thesisagents.core.exceptions import ThesisAgentsError  # noqa: E402
from thesisagents.core.local_pdf import (  # noqa: E402
    LocalPdfOverrides,
    build_local_collection,
    resolve_pdf_inputs,
)


def _pdf(path: Path, *lines: str) -> Path:
    """Write a one-page PDF showing ``lines``, with a correct xref table."""
    text = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(
        f"({line.replace('(', '').replace(')', '')}) Tj T*" for line in lines
    ) + " ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(text), text.encode("latin-1")),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref,
    )
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def thesis_pdf(tmp_path: Path) -> Path:
    return _pdf(
        tmp_path / "my_thesis.pdf",
        "Sparse Attention for Long Documents",
        "Ada Lovelace, Alan Turing",
        "Abstract",
        "We study sparse attention for long documents and show it scales.",
    )


def test_one_pdf_becomes_one_paper_with_a_copy(thesis_pdf, tmp_path):
    out = tmp_path / "exports"
    collection = build_local_collection([thesis_pdf], out)
    assert len(collection.papers) == 1
    paper = collection.papers[0]
    assert paper.source == "local"
    assert paper.url.startswith("file:///")
    assert paper.pdf_url is None
    assert "sparse attention" in paper.raw["extracted_text"].lower()
    assert collection.query.sources == ("local",)
    copies = list((out / "pdfs").glob("*.pdf"))
    assert len(copies) == 1


def test_overrides_win_for_a_single_pdf(thesis_pdf, tmp_path):
    overrides = LocalPdfOverrides(title="My Thesis", authors="A. One, B. Two", year=2026)
    paper = build_local_collection([thesis_pdf], tmp_path, overrides).papers[0]
    assert paper.title == "My Thesis"
    assert paper.authors == ("A. One", "B. Two")
    assert paper.year == 2026


def test_overrides_are_ignored_for_a_batch(thesis_pdf, tmp_path):
    second = _pdf(tmp_path / "other.pdf", "Another Paper", "Abstract", "Text.")
    collection = build_local_collection(
        [thesis_pdf, second], tmp_path / "out", LocalPdfOverrides(title="Same for all")
    )
    assert len(collection.papers) == 2
    assert all(p.title != "Same for all" for p in collection.papers)
    assert collection.query.keywords == "2 local PDFs"


def test_a_folder_expands_to_its_pdfs(thesis_pdf, tmp_path):
    (tmp_path / "notes.txt").write_text("not a pdf", encoding="utf-8")
    assert resolve_pdf_inputs(tmp_path) == [thesis_pdf.resolve()]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "empty"),
        (b"hello world", "not a PDF"),
        (b"%PDF-1.4\n/Encrypt <<>>", "encrypted"),
    ],
)
def test_bad_files_are_refused_by_name(tmp_path, content, message):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(content)
    with pytest.raises(ThesisAgentsError, match=message):
        build_local_collection([bad], tmp_path / "out")


def test_no_paths_and_missing_paths_are_refused(tmp_path):
    with pytest.raises(ThesisAgentsError, match="no PDF files"):
        build_local_collection([], tmp_path)
    with pytest.raises(ThesisAgentsError, match="does not exist"):
        resolve_pdf_inputs(tmp_path / "missing.pdf")


def test_the_cli_wrapper_maps_the_flags(thesis_pdf, tmp_path):
    args = argparse.Namespace(
        pdf=str(thesis_pdf), out=str(tmp_path / "cli"), title="Flag Title",
        authors=None, year=None, venue="TCSE", doi=None, arxiv_id=None,
    )
    paper = build_from_local_pdf(args).papers[0]
    assert (paper.title, paper.venue) == ("Flag Title", "TCSE")


def test_the_cli_wrapper_reports_an_empty_folder(tmp_path):
    args = argparse.Namespace(pdf=str(tmp_path), out=str(tmp_path / "cli"))
    with pytest.raises(ThesisAgentsError, match="--pdf found no PDFs"):
        build_from_local_pdf(args)

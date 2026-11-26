"""Reading BibTeX and RIS files: the fields, the markup, and broken records."""
from __future__ import annotations

import pytest

from thesisagents import cli
from thesisagents.core import bib_import
from thesisagents.core.bib_import import parse_bibtex, parse_ris, read_bibliography
from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection, Query
from thesisagents.exporters import export_collection
from thesisagents.library import Library

_BIB = r"""
% A comment line
@comment{ignored, title = {Not this}}
@string{neurips = "Advances in " # "NeurIPS"}
@inproceedings{vaswani2017attention,
  title     = {Attention Is {All} You Need},
  author    = {Vaswani, Ashish and {The Google Brain Team and Friends}
               and G{\"o}del, Kurt and others},
  booktitle = neurips,
  year      = 2017,
  doi       = {https://doi.org/10.5555/3295222.3295349},
  eprint    = {1706.03762v5}, archivePrefix = {arXiv},
  abstract  = {Models \& transduction at 50\% cost. {\'E}tude -- fran\c{c}aise, Erd\H{o}s, \O{}re.},
}
@article(knuth84, title = "Literate {P}rogramming", author = "Donald E. Knuth",
  journal = "Comput. J.", date = {1984-05}, url = {https://example.org/lp})
@misc{no_title, author = {Nobody}}
@phdthesis{phd, title={A Thesis}, author={Smith, Jr., John}, school={MIT}, year={2001}}
"""


def test_bibtex_fields_are_read():
    result = parse_bibtex(_BIB)
    attention, knuth, thesis = result.papers
    assert attention.title == "Attention Is All You Need"
    assert attention.authors == (
        "Ashish Vaswani", "The Google Brain Team and Friends", "Kurt Gödel"
    )
    assert attention.venue == "Advances in NeurIPS"
    assert (attention.year, attention.doi) == (2017, "10.5555/3295222.3295349")
    assert attention.arxiv_id == "1706.03762v5"
    assert attention.url == "https://doi.org/10.5555/3295222.3295349"
    assert attention.abstract == (
        "Models & transduction at 50% cost. Étude – française, Erdős, Øre."
    )
    assert (attention.source, attention.source_id) == ("bibtex", "vaswani2017attention")
    assert (knuth.title, knuth.year, knuth.url) == (
        "Literate Programming", 1984, "https://example.org/lp"
    )
    assert thesis.authors == ("John Smith Jr.",)
    assert thesis.venue == "MIT"
    assert result.skipped == ("line 17: no_title has no title",)


@pytest.mark.parametrize(("latex", "plain"), [
    (r"{\'E}tude", "Étude"), (r"\'{e}", "é"), (r"\'e", "é"), (r"\v{c}", "č"), (r"\v c", "č"),
    (r"na\"{\i}ve", "naïve"), (r"\ss", "ß"), (r"\aa{}", "å"), (r"\emph{word} x", "word x"),
    (r"a~b", "a b"), (r"$x_1$", "$x_1$"), (r"{\textbf{Bold}}", "Bold"), (r"100\%", "100%"),
])
def test_latex_becomes_text(latex, plain):
    assert parse_bibtex("@misc{k, title = {" + latex + "}}").papers[0].title == plain


def test_a_broken_record_does_not_swallow_the_next():
    result = parse_bibtex(
        "@article{bad, title = {Never closed\n\n@article{good, title = {Fine}, year = 2020}\n"
    )
    assert [p.title for p in result.papers] == ["Fine"]
    assert result.skipped == ("line 1: the record is not closed",)


def test_an_at_sign_inside_a_value_is_not_a_record():
    text = "@misc{k, title = {Mail}, note = {write to\n@someone about {it}}, year = 2001}"
    assert [p.title for p in parse_bibtex(text).papers] == ["Mail"]


def test_an_old_arxiv_identifier_and_one_in_the_url():
    result = parse_bibtex(
        "@misc{a, title={A}, eprint={hep-th/9901001}, archiveprefix={arXiv}}"
        "@misc{b, title={B}, url={https://arxiv.org/abs/2401.00001v2}}"
        "@misc{c, title={C}, eprint={12345}, archiveprefix={PubMed}}"
    )
    assert [p.arxiv_id for p in result.papers] == ["hep-th/9901001", "2401.00001v2", None]


def test_parsing_a_large_file_is_fast():
    record = "@article{k%d, title = {Title {%d}}, author = {A, B and C, D}, year = 2020}\n"
    text = "".join(record % (i, i) for i in range(3000))
    assert len(parse_bibtex(text).papers) == 3000


_RIS = """TY  - JOUR
TI  - Attention Is All
  You Need
AU  - Vaswani, Ashish
A1  - Noam Shazeer
PY  - 2017/06/12/
JO  - NeurIPS
DO  - 10.5555/1
UR  - https://arxiv.org/abs/1706.03762
AB  - First part
second part.
ER  -

TY  - BOOK
AU  - Nobody
ER  -
TY  - GEN
T1  - No end tag
"""


def test_ris_fields_are_read():
    result = parse_ris(_RIS)
    first, second = result.papers
    assert first.title == "Attention Is All You Need"
    assert first.authors == ("Ashish Vaswani", "Noam Shazeer")
    assert (first.year, first.venue, first.doi) == (2017, "NeurIPS", "10.5555/1")
    assert first.arxiv_id == "1706.03762"
    assert first.abstract == "First part second part."
    assert second.title == "No end tag"
    assert result.skipped == ("line 14: the record has no title",)


# --- files --------------------------------------------------------------------------


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "latin-1"])
def test_files_in_common_encodings_are_read(tmp_path, encoding):
    file = tmp_path / "x.txt"
    file.write_bytes("@misc{k, title = {Café}}".encode(encoding))
    assert read_bibliography(file).papers[0].title == "Café"


@pytest.mark.parametrize("content", [b"", b"just text", b"\x00\x01\x02"])
def test_a_file_with_no_record_is_refused(tmp_path, content):
    file = tmp_path / "x.bib"
    file.write_bytes(content)
    with pytest.raises(ThesisAgentsError, match="no BibTeX or RIS record"):
        read_bibliography(file)


def test_missing_and_oversized_files_are_refused(tmp_path, monkeypatch):
    with pytest.raises(ThesisAgentsError, match="cannot read"):
        read_bibliography(tmp_path / "none.bib")
    file = tmp_path / "x.bib"
    file.write_text("@misc{k, title={T}}", encoding="utf-8")
    monkeypatch.setattr(bib_import, "MAX_FILE_BYTES", 5)
    with pytest.raises(ThesisAgentsError, match="larger than"):
        read_bibliography(file)


@pytest.mark.parametrize("fmt", ["bib", "ris"])
def test_our_own_exports_come_back(tmp_path, fmt):
    paper = Paper(
        source="arxiv", source_id="1706.03762", title="Attention Is All You Need",
        authors=("Ashish Vaswani", "Noam Shazeer"), year=2017, venue="NeurIPS",
        abstract="We propose the Transformer.", url="https://arxiv.org/abs/1706.03762",
        doi="10.5555/3295222.3295349",
    )
    written = export_collection(
        PaperCollection(query=Query("x", ("arxiv",)), papers=(paper,)),
        ExportOptions(formats=(fmt,), out_dir=str(tmp_path), verify_identifiers=False),
    )
    back = read_bibliography(written[fmt]).papers[0]
    assert (back.title, back.authors, back.year) == (paper.title, paper.authors, paper.year)
    assert (back.doi, back.venue) == (paper.doi, paper.venue)
    assert set(back.identity_keys()) & set(paper.identity_keys())


def test_cli_imports_and_tags(tmp_path, capsys):
    file, path = tmp_path / "x.bib", tmp_path / "lib.db"
    file.write_text(_BIB, encoding="utf-8")
    assert cli.main(["library", str(path), "import", str(file), "--tag", "from zotero"]) == 0
    out = capsys.readouterr()
    assert "3 added, 0 already" in out.out
    assert "no_title has no title" in out.err
    assert cli.main(["library", str(path), "import", str(file)]) == 0
    assert "0 added, 3 already" in capsys.readouterr().out
    with Library(path) as library:
        assert library.tags() == {"from zotero": 3}
        assert library.runs()[0].kind == "import"

"""The literature review draft: APA, comparison table, Word and LaTeX."""
from __future__ import annotations

import pytest
from docx import Document

from thesisagents import cli
from thesisagents.core.comparison import comparison_rows
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters import export_collection
from thesisagents.exporters.apa import (
    citation_labels,
    reference,
    reference_order,
    split_name,
)
from thesisagents.exporters.latex import escape
from thesisagents.exporters.review_document import Bullets, Heading, Table, review_blocks


def _paper(source_id: str = "1", **fields) -> Paper:
    defaults = {
        "source": "arxiv", "title": f"Title {source_id}", "authors": ("Ada Lovelace",),
        "year": 2020, "venue": None, "abstract": "An abstract.",
        "url": f"https://example.org/{source_id}",
    }
    defaults.update(fields)
    return Paper(source_id=source_id, **defaults)


RICH = PaperSummary(
    language="en",
    motivation=("Repairs are slow",), method=("It searches & ranks patches.",),
    results=("Fixes 40% more bugs.",), limitations=("Only Java was studied.", "One data set"),
    future_work=("Try C_programs.",), headline_metrics=(("Fixed", "40%", "vs 28%"),),
    technique_table=(("Beam search", "explores"), ("Ranking", "orders")),
)
FULL = _paper(
    "full", title="Learned Repair", authors=("Ada Lovelace", "Kurt Gödel", "Lee Kim"),
    venue="ICSE", doi="10.1/x", summary=RICH,
)
PLAIN = _paper("plain", title="Plain Paper", authors=("Bo Zhang",), arxiv_id="2401.00001")


def _collection(*papers: Paper) -> PaperCollection:
    return PaperCollection(query=Query("program repair", ("arxiv",)), papers=papers)


def _export(tmp_path, fmt: str, *papers: Paper, **options):
    written = export_collection(
        _collection(*papers),
        ExportOptions(
            formats=(fmt,), out_dir=str(tmp_path), filename_stem="review",
            verify_identifiers=False, **options,
        ),
    )
    return written[fmt]


# --- APA ----------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "expected"), [
    ("Ashish Vaswani", ("Vaswani", "Ashish")),
    ("Vaswani, Ashish N.", ("Vaswani", "Ashish N.")),
    ("John Q. Smith Jr.", ("Smith", "John Q., Jr.")),
    ("Plato", ("Plato", "")),
    ("王小明", ("王小明", "")),
    ("김 철수", ("김 철수", "")),
])
def test_names_are_split(name, expected):
    assert split_name(name) == expected


@pytest.mark.parametrize(("authors", "expected"), [
    (("Ada Lovelace",), "(Lovelace, 2020)"),
    (("Ada Lovelace", "Kurt Gödel"), "(Lovelace & Gödel, 2020)"),
    (("Ada Lovelace", "Kurt Gödel", "Lee Kim"), "(Lovelace et al., 2020)"),
    (("", " "), "(“Title 1”, 2020)"),
])
def test_citations_in_the_text(authors, expected):
    assert citation_labels([_paper(authors=authors)])[0].in_text == expected


def test_the_narrative_form_spells_out_and():
    label = citation_labels([_paper(authors=("A Bee", "C Dee"))])[0]
    assert label.narrative == "Bee and Dee (2020)"


def test_papers_that_look_alike_get_letters_in_reference_order():
    papers = [
        _paper("2", title="Zebra"), _paper("1", title="Apple"), _paper("3", year=None),
        _paper("4", year=None),
    ]
    assert [label.year for label in citation_labels(papers)] == [
        "2020b", "2020a", "n.d.-a", "n.d.-b",
    ]


def _joined(paper: Paper) -> str:
    return "".join(
        f"*{text}*" if italic else text for text, italic in reference(paper)
    )


@pytest.mark.parametrize(("paper", "expected"), [
    (FULL, "Lovelace, A., Gödel, K., & Kim, L. (2020). Learned Repair. *ICSE*. "
           "https://doi.org/10.1/x"),
    (PLAIN, "Zhang, B. (2020). *Plain Paper* (arXiv:2401.00001). arXiv. "
            "https://arxiv.org/abs/2401.00001"),
    (_paper(authors=("Jean-Paul Sartre",), year=None, title="No date."),
     "Sartre, J.-P. (n.d.). *No date*. https://example.org/1"),
    (_paper(authors=("王小明",), venue="資訊學報", title="軟體修復"),
     "王小明. (2020). 軟體修復. *資訊學報*. https://example.org/1"),
    (_paper(authors=(), title="Anonymous"), "*Anonymous*. (2020). https://example.org/1"),
    (_paper(doi="https://doi.org/10.2/y"), "Lovelace, A. (2020). *Title 1*. https://doi.org/10.2/y"),
])
def test_references(paper, expected):
    assert _joined(paper) == expected


def test_more_than_twenty_authors_are_shortened():
    text = _joined(_paper(authors=tuple(f"A Name{i:02}" for i in range(25))))
    assert "Name18, A., … Name24, A. (2020)" in text
    assert "Name19" not in text


def test_the_reference_list_is_alphabetical_accents_aside():
    papers = [_paper(authors=(n,)) for n in ("B Zoo", "A Öhm", "C Nash", "D Pratt")]
    order = [papers[i].authors[0] for i in reference_order(papers)]
    assert order == ["C Nash", "A Öhm", "D Pratt", "B Zoo"]


# --- comparison -------------------------------------------------------------------------


def test_the_table_quotes_the_summary_and_invents_nothing():
    full, plain = comparison_rows([FULL, PLAIN])
    assert full.method == ("Beam search", "Ranking")
    assert full.strengths[0] == "Fixed: 40% (vs 28%)"
    assert full.weaknesses == ("Only Java was studied.", "One data set")
    assert plain.is_empty
    table = next(b for b in review_blocks(_collection(FULL, PLAIN), "en") if isinstance(b, Table))
    assert [cell[0] for cell in table.rows[2][1:]] == ["—", "—", "—"]


def test_the_workbook_has_the_table_when_there_is_something_to_compare(tmp_path):
    from openpyxl import load_workbook

    book = load_workbook(_export(tmp_path, "xlsx", FULL, PLAIN))
    rows = list(book["Comparison"].values)
    assert rows[0] == ("Author", "Title", "Method", "Strengths", "Weaknesses")
    assert rows[1][:3] == ("Lovelace et al. (2020)", "Learned Repair", "Beam search\nRanking")
    assert len(rows) == 2
    without = load_workbook(_export(tmp_path / "b", "xlsx", PLAIN))
    assert "Comparison" not in without.sheetnames


# --- the draft ----------------------------------------------------------------------------


def test_the_sections_of_the_draft():
    blocks = review_blocks(_collection(FULL, PLAIN), "zh-tw")
    headings = [b.text for b in blocks if isinstance(b, Heading)]
    assert headings == [
        "文獻探討：program repair", "2.3 文獻探討", "2.3.1 Learned Repair", "2.3.2 Plain Paper",
        "2.4 文獻比較分析",
    ]
    points = next(b for b in blocks if isinstance(b, Bullets))
    assert len(points.items) == 3


def test_without_summaries_there_is_no_analysis():
    blocks = review_blocks(_collection(PLAIN), "en")
    assert not any(isinstance(b, Bullets) for b in blocks)


@pytest.mark.parametrize(("years", "expected"), [
    ((2018, 2021), "published between 2018 and 2021"),
    ((2020, 2020), "published in 2020"),
    ((None, None), "This section reviews 2 papers."),
])
def test_the_opening_sentence_states_the_years(years, expected):
    papers = [_paper(str(i), year=y) for i, y in enumerate(years)]
    paragraph = review_blocks(_collection(*papers), "en")[2]
    assert expected in paragraph.content[0]


# --- Word -----------------------------------------------------------------------------------


def _docx_text(path) -> list[str]:
    return [p.text for p in Document(str(path)).paragraphs]


def test_word_draft(tmp_path):
    path = _export(tmp_path, "docx", FULL, PLAIN)
    texts = _docx_text(path)
    assert "Repairs are slow. (Lovelace et al., 2020)" in texts
    assert "It searches & ranks patches. (Lovelace et al., 2020)" in texts
    assert "An abstract. (Zhang, 2020)" in texts
    assert "One data set (Lovelace et al., 2020)" in texts
    document = Document(str(path))
    table = document.tables[0]
    assert [c.text for c in table.rows[0].cells] == ["Author", "Method", "Strengths", "Weaknesses"]
    assert table.rows[1].cells[1].text == "Beam search\nRanking"
    last = document.paragraphs[-1]
    assert last.text.startswith("Zhang, B. (2020).")
    assert [r.text for r in last.runs if r.italic] == ["Plain Paper"]


def test_word_draft_in_traditional_chinese_follows_the_handbook(tmp_path):
    document = Document(str(_export(tmp_path, "docx", FULL, language="zh-tw")))
    normal = document.styles["Normal"]
    heading = document.styles["Heading 2"]
    assert (normal.font.size.pt, heading.font.size.pt, heading.font.bold) == (14, 20, True)
    for style in (normal, heading):
        fonts = style.element.rPr.rFonts
        east_asia = fonts.get(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia"
        )
        assert (style.font.name, east_asia) == ("Times New Roman", "標楷體")
        assert not [name for name in fonts.attrib if name.endswith("Theme")]


def test_word_draft_goes_into_a_template_and_keeps_it(tmp_path):
    template = tmp_path / "school.docx"
    source = Document()
    source.add_paragraph("Declaration of the school")
    source.styles["Normal"].font.name = "Comic Sans MS"
    source.save(str(template))
    before = template.read_bytes()
    path = _export(tmp_path, "docx", FULL, docx_template=str(template))
    document = Document(str(path))
    assert document.paragraphs[0].text == "Declaration of the school"
    assert document.styles["Normal"].font.name == "Comic Sans MS"
    assert any("Learned Repair" in p.text for p in document.paragraphs)
    assert template.read_bytes() == before


@pytest.mark.parametrize(("name", "content", "match"), [
    ("x.txt", b"text", "not a .docx file"),
    ("x.docx", b"not a zip", "cannot read the template"),
    (None, b"", "cannot read the template"),
])
def test_an_unusable_template_is_named(tmp_path, name, content, match):
    template = tmp_path / (name or "missing.docx")
    if name:
        template.write_bytes(content)
    with pytest.raises(ExportError, match=match):
        _export(tmp_path, "docx", FULL, docx_template=str(template))


def test_characters_word_refuses_do_not_fail_the_export(tmp_path):
    path = _export(tmp_path, "docx", _paper(title="Form\x0cfeed", abstract="A\x00b\x1fc"))
    assert any("Abc" in text for text in _docx_text(path))


# --- LaTeX --------------------------------------------------------------------------------------


@pytest.mark.parametrize(("text", "expected"), [
    ("a_b & 5% #1 {x} $y$ ~ ^ \\cmd <t>", r"a\_b \& 5\% \#1 \{x\} \$y\$ \textasciitilde{} "
     r"\textasciicircum{} \textbackslash{}cmd \textless{}t\textgreater{}"),
    ("tab\tand\x07bell", "tab\tandbell"),
])
def test_latex_escaping(text, expected):
    assert escape(text) == expected


def test_latex_draft_cites_the_keys_of_its_bib_file(tmp_path):
    twin = _paper("twin", title="Learned Other", authors=("Ada Lovelace",))
    path = _export(tmp_path, "tex", FULL, twin, PLAIN)
    text = path.read_text(encoding="utf-8")
    bib = path.with_suffix(".bib").read_text(encoding="utf-8")
    import re

    cited = set(re.findall(r"\\citep\{([^}]+)\}", text))
    defined = set(re.findall(r"@\w+\{([^,]+),", bib))
    assert cited == defined
    assert len(defined) == 3
    assert r"It searches \& ranks patches." in text
    assert r"Try C\_programs" in text
    assert r"\bibliography{review}" in text
    assert "Beam search \\newline Ranking" in text
    plain = text.replace(r"\{", "").replace(r"\}", "")
    assert plain.count("{") == plain.count("}")
    for name in ("document", "itemize", "longtable"):
        assert text.count(f"\\begin{{{name}}}") == text.count(f"\\end{{{name}}}") == 1
    assert "xeCJK" not in text


def test_latex_draft_loads_cjk_fonts_for_cjk(tmp_path):
    text = _export(tmp_path, "tex", FULL, language="zh-tw").read_text(encoding="utf-8")
    assert r"\usepackage{xeCJK}" in text
    assert r"\subsection{文獻探討}" in text


def test_an_empty_collection_still_exports(tmp_path):
    for fmt in ("docx", "tex"):
        assert _export(tmp_path, fmt).exists()


# --- command line ------------------------------------------------------------------------


def test_cli_exports_a_library_as_a_word_draft(tmp_path):
    from thesisagents.library import Library

    path = tmp_path / "l.db"
    with Library(path) as library:
        library.add_papers([FULL])
    code = cli.main([
        "--library", str(path), "--library-export", "--export", "docx,tex",
        "--out", str(tmp_path / "out"), "--no-verify-identifiers", "--filename-stem", "draft",
    ])
    assert code == 0
    assert (tmp_path / "out" / "draft.docx").exists()
    assert (tmp_path / "out" / "draft.tex").exists()
    assert (tmp_path / "out" / "draft.bib").exists()

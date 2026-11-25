"""Exports of unusual papers, long collections and real-world templates."""
from __future__ import annotations

import json
import zipfile

import pytest
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from thesisagents.core.bib_import import parse_bibtex
from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters import export_collection, pptx_edit
from thesisagents.exporters.apa import reference_order
from thesisagents.exporters.audit import audit_deck
from thesisagents.exporters.bibtex import bibtex_entry, unique_keys
from thesisagents.exporters.overflow import check_pptx
from thesisagents.exporters.pptx_text import _render_math_paragraph
from thesisagents.exporters.template import validate_template


def _paper(source_id: str = "1", **fields) -> Paper:
    defaults = {
        "source": "arxiv", "title": f"Paper {source_id}", "authors": ("Ann Bee",), "year": 2020,
        "venue": "V", "abstract": "One. Two. Three.", "url": f"https://e.org/{source_id}",
        "doi": f"10.1000/{source_id}",
    }
    return Paper(source_id=source_id, **{**defaults, **fields})


def _export(tmp_path, fmt: str, *papers: Paper, **options):
    return export_collection(
        PaperCollection(Query("q", ("arxiv",)), papers),
        ExportOptions(
            formats=(fmt,), out_dir=str(tmp_path), filename_stem="x",
            verify_identifiers=False, **options,
        ),
    )[fmt]


# --- tables and bibliographies ----------------------------------------------------------


def test_a_cell_that_begins_like_a_formula_stays_text(tmp_path):
    summary = PaperSummary(language="en", limitations=("=1+1",))
    path = _export(tmp_path, "xlsx", _paper(title='=HYPERLINK("http://x","y")', summary=summary))
    book = load_workbook(path)
    assert book["Papers"]["B2"].value == '=HYPERLINK("http://x","y")'
    kinds = {cell.data_type for sheet in book for row in sheet.iter_rows() for cell in row}
    assert "f" not in kinds
    assert book["Comparison"]["E2"].value == "=1+1"


def test_bibtex_escapes_each_character_once():
    entry = bibtex_entry(_paper(title=r"a\b {c}"))
    assert r"a\textbackslash{}b \{c\}" in entry
    assert parse_bibtex(entry).papers[0].title == r"a\b {c}".replace("{", "").replace("}", "")


def test_an_organisation_with_and_stays_one_author():
    paper = _paper(authors=("Barnes and Noble", "Ada Lovelace"))
    entry = bibtex_entry(paper)
    assert "author = {{Barnes and Noble} and Ada Lovelace}" in entry
    assert parse_bibtex(entry).papers[0].authors == paper.authors


def test_thirty_equal_cite_keys_are_all_usable():
    keys = unique_keys([_paper()] * 30)
    assert len(set(keys)) == 30
    assert all(key.isalnum() for key in keys)
    assert keys[:3] == ["bee2020paper", "bee2020paperb", "bee2020paperc"]


def test_csl_names_and_ids(tmp_path):
    path = _export(
        tmp_path, "csl",
        _paper("1", authors=("Lovelace, Ada", "王小明", "Martin King Jr.", "Plato")),
        _paper("1"),
    )
    items = json.loads(path.read_text(encoding="utf-8"))
    assert items[0]["author"] == [
        {"family": "Lovelace", "given": "Ada"},
        {"family": "王小明"},
        {"family": "King", "given": "Martin", "suffix": "Jr."},
        {"family": "Plato"},
    ]
    assert [item["id"] for item in items] == unique_keys([
        _paper("1", authors=("Lovelace, Ada",)), _paper("1"),
    ])


def test_references_in_other_scripts_are_in_order():
    papers = [
        _paper("a", authors=("王小明", "李四"), year=2021),
        _paper("b", authors=("丁一", "張三"), year=2022),
        _paper("c", authors=("王小明",), year=2019),
    ]
    order = [papers[i].source_id for i in reference_order(papers)]
    assert order == ["b", "c", "a"]


# --- the literature review draft --------------------------------------------------------


def test_a_word_template_without_heading_styles_can_be_used(tmp_path):
    template = tmp_path / "school.docx"
    document = Document()
    for level in (2, 3):
        style = document.styles[f"Heading {level}"]
        style.element.getparent().remove(style.element)
    document.save(template)
    path = _export(tmp_path, "docx", _paper(), docx_template=str(template))
    bold = [p.text for p in Document(path).paragraphs if p.runs and p.runs[0].bold]
    assert "2.3.1 Paper 1" in bold


def test_a_latex_item_that_begins_with_a_bracket_is_no_label(tmp_path):
    summary = PaperSummary(language="en", limitations=("[Scope] only Java",))
    text = _export(tmp_path, "tex", _paper(summary=summary)).read_text(encoding="utf-8")
    assert r"\item {}[Scope] only Java" in text


def test_latex_fonts_can_show_the_language(tmp_path):
    hindi = _export(tmp_path, "tex", _paper(), language="hi").read_text(encoding="utf-8")
    assert r"\setmainfont[Script=Devanagari]" in hindi
    japanese = _export(tmp_path, "tex", _paper(), language="ja").read_text(encoding="utf-8")
    assert "XeLaTeX or LuaLaTeX" not in japanese


# --- decks ------------------------------------------------------------------------------


def _slide_parts(path) -> list[str]:
    names = zipfile.ZipFile(path).namelist()
    return [name for name in names if name.startswith("ppt/slides/slide")]


def test_slides_over_the_budget_leave_the_file(tmp_path):
    summary = PaperSummary(
        language="en", method_sections=tuple((f"h{i}", ("a",)) for i in range(40)),
        contributions_detailed=(("x", "y"),),
    )
    path = _export(tmp_path, "pptx", _paper(summary=summary), max_slides_per_paper=10)
    assert len(_slide_parts(path)) == len(Presentation(str(path)).slides) == 10
    pptx_edit.add_slide(path, title="New", body="b")
    parts = _slide_parts(path)
    assert len(parts) == len(set(parts)) == 11


def test_a_long_agenda_and_long_references_continue_on_the_next_slide(tmp_path):
    papers = [
        _paper(str(i), title=f"A rather long paper title about topic number {i} and its use")
        for i in range(25)
    ]
    path = _export(tmp_path, "pptx", *papers)
    assert check_pptx(path) == []
    titles = [view.title for view in pptx_edit.inspect(path)]
    assert "Agenda (1/2)" in titles
    assert "References (4/4)" in titles
    text = " ".join(s.text for v in pptx_edit.inspect(path) for s in v.shapes)
    assert "25. Ann Bee (2020)" in text


def test_reference_lines_use_no_dash(tmp_path):
    path = _export(tmp_path, "pptx", _paper(title="A title."))
    body = next(
        s.text for v in pptx_edit.inspect(path) if v.title == "References"
        for s in v.shapes if s.name == "body"
    )
    assert "—" not in body
    assert "A title. 10.1000/1" in body


@pytest.mark.parametrize("content", [b"not an image", b'<svg xmlns="http://www.w3.org/2000/svg"/>'])
def test_an_image_that_cannot_be_shown_is_a_placeholder(tmp_path, content):
    image = tmp_path / "figure.png"
    image.write_bytes(content)
    summary = PaperSummary(language="en", figures=(("cap", str(image), ()),))
    path = _export(tmp_path, "pptx", _paper(summary=summary))
    text = " ".join(s.text for v in pptx_edit.inspect(path) for s in v.shapes)
    assert "[figure unavailable: figure.png]" in text


@pytest.mark.parametrize(("text", "runs"), [
    ("from $5 and up to $10 each", ["from $5 and up to $10 each"]),
    ("$5-$10 per call", ["$5-$10 per call"]),
    ("loss $z_a$ here", ["loss ", "z", "a", " here"]),
    ("$x$, then $y$", ["x", ", then ", "y"]),
])
def test_money_is_no_math(text, runs):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    paragraph = slide.shapes.add_textbox(0, 0, 1, 1).text_frame.paragraphs[0]
    _render_math_paragraph(paragraph, text, size_pt=18, colour=RGBColor(1, 2, 3))
    assert [run.text for run in paragraph.runs] == runs


# --- editing a deck ---------------------------------------------------------------------


def test_an_edit_leaves_the_other_lines_as_they_are(tmp_path):
    path = tmp_path / "d.pptx"
    prs = Presentation()
    frame = prs.slides.add_slide(prs.slide_layouts[6]).shapes.add_textbox(
        0, 0, Inches(4), Inches(2)
    ).text_frame
    _render_math_paragraph(frame.paragraphs[0], "loss $z_a$", size_pt=18, colour=RGBColor(9, 9, 9))
    for text, colour in (("second", RGBColor(1, 1, 1)), ("third", RGBColor(2, 2, 2))):
        run = frame.add_paragraph().add_run()
        run.text, run.font.size, run.font.color.rgb = text, Pt(12), colour
    prs.save(path)
    pptx_edit.update_slide(path, 0, shape_updates={0: "loss za\nnew\nsecond changed\nthird"})
    paragraphs = Presentation(str(path)).slides[0].shapes[0].text_frame.paragraphs
    assert [p.text for p in paragraphs] == ["loss za", "new", "second changed", "third"]
    # The subscript is still one, and the last line kept its own colour.
    assert [run.text for run in paragraphs[0].runs] == ["loss ", "z", "a"]
    assert paragraphs[0].runs[2]._r.rPr.get("baseline") == "-25000"
    assert paragraphs[3].runs[0].font.color.rgb == RGBColor(2, 2, 2)
    assert all(run.font.color.rgb is not None for p in paragraphs for run in p.runs)


def test_an_edit_keeps_the_background_of_the_layout(tmp_path):
    path = tmp_path / "d.pptx"
    prs = Presentation()
    layout = prs.slide_layouts[6]
    layout.background.fill.solid()
    layout.background.fill.fore_color.rgb = RGBColor(0x12, 0x15, 0x1B)
    box = prs.slides.add_slide(layout).shapes.add_textbox(0, 0, Inches(3), Inches(1))
    box.text_frame.text = "old"
    prs.save(path)
    pptx_edit.update_slide(path, 0, shape_updates={0: "new"})
    slide = Presentation(str(path)).slides[0]
    assert slide._element.cSld.find(qn("p:bg")) is None
    # Dark behind it, so the text is light, and the audit sees no invisible run.
    assert slide.shapes[0].text_frame.paragraphs[0].runs[0].font.color.rgb == RGBColor(
        0xE5, 0xE7, 0xEB
    )
    assert [issue for issue in audit_deck(path) if issue.hard] == []


# --- templates --------------------------------------------------------------------------


@pytest.fixture
def template(tmp_path):
    path = tmp_path / "school.pptx"
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    prs.slides.add_slide(prs.slide_layouts[0]).shapes.title.text = "SAMPLE"
    prs.save(path)
    return path


def test_the_templates_own_slides_stay_out_of_the_deck(tmp_path, template):
    report = validate_template(template)
    assert report.ok
    assert [issue.code for issue in report.warnings] == ["template-slides-removed"]
    path = _export(tmp_path, "pptx", _paper(), pptx_template=str(template))
    slides = list(Presentation(str(path)).slides)
    names = [{shape.name for shape in slide.shapes} for slide in slides]
    assert "accent_left" in names[0]
    assert all("accent_left" not in found for found in names[1:])
    assert "SAMPLE" not in " ".join(v.title for v in pptx_edit.inspect(path))
    assert len(_slide_parts(path)) == len(slides)


def test_a_potx_is_a_template(tmp_path, template):
    potx = tmp_path / "school.potx"
    with zipfile.ZipFile(template) as source, zipfile.ZipFile(potx, "w") as target:
        for name in source.namelist():
            data = source.read(name)
            if name == "[Content_Types].xml":
                data = data.replace(
                    b"presentationml.presentation.main+xml", b"presentationml.template.main+xml"
                )
            target.writestr(name, data)
    assert validate_template(potx).ok
    path = _export(tmp_path, "pptx", _paper(), pptx_template=str(potx))
    assert len(Presentation(str(path)).slides) > 2
    (tmp_path / "broken.potx").write_bytes(b"no zip")
    report = validate_template(tmp_path / "broken.potx")
    assert [issue.code for issue in report.errors] == ["unreadable-template"]


# --- what the audit sees, what a spreadsheet runs -----------------------------------------


def test_the_audit_reads_tables_and_groups(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    table = slide.shapes.add_table(1, 1, Inches(1), Inches(1), Inches(3), Inches(1)).table
    run = table.cell(0, 0).text_frame.paragraphs[0].add_run()
    run.text = "in a table"
    run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
    group = slide.shapes.add_group_shape()
    box = group.shapes.add_textbox(Inches(1), Inches(3), Inches(3), Inches(1))
    box.text_frame.text = "in a group"
    deck.save(tmp_path / "d.pptx")
    assert {i.kind for i in audit_deck(tmp_path / "d.pptx") if i.hard} == {"red text", "invisible"}


def test_a_csv_cell_is_text_and_not_a_formula(tmp_path):
    paper = _paper(title='=HYPERLINK("http://x","y")', authors=("@cmd",), venue="+1", abstract="-x")
    text = _export(tmp_path, "csv", paper).read_text(encoding="utf-8")
    row = text.splitlines()[1]
    for value in ("\"'=HYPERLINK", "'@cmd", "'+1", "'-x"):
        assert value in row

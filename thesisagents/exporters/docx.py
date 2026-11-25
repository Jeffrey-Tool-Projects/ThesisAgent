"""Word (.docx) exporter: a literature review draft with APA citations.

With ``ExportOptions.docx_template`` the draft is written into a copy of that
document (a school's thesis template): its styles decide how everything
looks, and nothing in it is removed. Without one the document follows the
thesis handbook defaults in ``paper_rule``: for Traditional Chinese 14 pt
標楷體 with Times New Roman and bold 20 pt headings, otherwise 12 pt Times
New Roman.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from thesisagents.core.constants import EXPORT_DOCX
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, PaperCollection
from thesisagents.exporters.apa import CitationLabel, reference, reference_order
from thesisagents.exporters.base import Exporter
from thesisagents.exporters.i18n import normalise_language
from thesisagents.exporters.review_document import (
    Bullets,
    Cite,
    Heading,
    Inline,
    Paragraph,
    References,
    Table,
    labels_of,
    review_blocks,
)
from thesisagents.exporters.xlsx import _sheet_safe

#: CJK font per language, beside Times New Roman for Latin text.
_EAST_ASIAN_FONTS = {
    "zh-tw": "標楷體", "zh-cn": "宋体", "ja": "ＭＳ 明朝", "ko": "바탕",
}
_LATIN_FONT = "Times New Roman"
#: ``(body, heading)`` in points. The 14 / 20 pair is the zh-tw handbook's.
_SIZES = {"zh-tw": (14, 20)}
_DEFAULT_SIZES = (12, 14)


class DocxExporter(Exporter):
    format = EXPORT_DOCX
    extension = "docx"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        try:
            document = self._build(collection, options)
        except ExportError:
            raise
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        document.save(str(out_path))
        return out_path

    def _build(self, collection: PaperCollection, options: ExportOptions) -> Any:
        language = normalise_language(options.language)
        document = _open(options.docx_template)
        if not options.docx_template:
            _apply_defaults(document, language)
        elif document.paragraphs:
            document.add_page_break()
        labels = labels_of(collection)
        for block in review_blocks(collection, options.language):
            if isinstance(block, Heading):
                _add_heading(document, block.text, block.level)
            elif isinstance(block, Paragraph):
                document.add_paragraph(_text(block.content, labels))
            elif isinstance(block, Bullets):
                for item in block.items:
                    document.add_paragraph(_text(item, labels), style=_style(
                        document, "List Bullet"
                    ))
            elif isinstance(block, Table):
                _add_table(document, block, labels)
            elif isinstance(block, References):
                _add_references(document, block, collection, labels)
        return document


def _open(template: str | None) -> Any:
    from docx import Document
    from docx.opc.exceptions import PackageNotFoundError

    if not template:
        return Document()
    path = Path(template)
    if path.suffix.lower() != ".docx":
        raise ExportError(EXPORT_DOCX, f"{template} is not a .docx file")
    try:
        return Document(str(path))
    except (PackageNotFoundError, OSError, KeyError, ValueError) as err:
        raise ExportError(EXPORT_DOCX, f"cannot read the template {template}: {err}") from err


def _style(document: Any, name: str) -> str | None:
    """``name`` when the document has that style, else None (its default)."""
    return name if name in [style.name for style in document.styles] else None


def _add_heading(document: Any, text: str, level: int) -> None:
    """A heading, in bold where the template does not define its style.

    The failure this prevents: a school's template often defines only the
    levels it uses, and python-docx raises ``KeyError`` for the others.
    """
    style = _style(document, f"Heading {level}")
    if style is not None:
        document.add_paragraph(_clean(text), style=style)
        return
    document.add_paragraph().add_run(_clean(text)).bold = True


def _clean(text: str) -> str:
    """Characters XML forbids, which scraped text carries, would fail the export."""
    return _sheet_safe(text)


def _text(content: Inline, labels: list[CitationLabel]) -> str:
    return _clean(
        "".join(
            labels[piece.index].in_text if isinstance(piece, Cite) else piece
            for piece in content
        )
    ).strip()


def _apply_defaults(document: Any, language: str) -> None:
    from docx.shared import Pt, RGBColor

    body, heading = _SIZES.get(language, _DEFAULT_SIZES)
    normal = document.styles["Normal"]
    _set_font(normal, language)
    normal.font.size = Pt(body)
    normal.paragraph_format.line_spacing = 1.5
    for level in (1, 2, 3):
        style = document.styles[f"Heading {level}"]
        _set_font(style, language)
        style.font.size = Pt(heading)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0x00, 0x00, 0x00)


def _set_font(style: Any, language: str) -> None:
    """Latin and East Asian fonts. Word picks by character, so both are set."""
    from docx.oxml.ns import qn

    style.font.name = _LATIN_FONT
    fonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    # A theme font would win over the names set here.
    for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn(f"w:{attribute}"), None)
    fonts.set(qn("w:eastAsia"), _EAST_ASIAN_FONTS.get(language, _LATIN_FONT))


def _add_table(document: Any, block: Table, labels: list[CitationLabel]) -> None:
    from docx.shared import Pt

    caption = document.add_paragraph(_clean(block.caption), style=_style(document, "Caption"))
    caption.paragraph_format.keep_with_next = True
    table = document.add_table(rows=0, cols=len(block.rows[0]))
    table.style = _style(document, "Table Grid")
    for number, row in enumerate(block.rows):
        cells = table.add_row().cells
        for cell, content in zip(cells, row, strict=True):
            lines = _text(content, labels).split("\n")
            cell.text = lines[0]
            for line in lines[1:]:
                cell.add_paragraph(line)
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                for run in paragraph.runs:
                    run.font.size = Pt(10)
                    run.font.bold = number == 0
    # The header row is repeated where the table breaks across pages.
    _mark_header(table.rows[0])


def _mark_header(row: Any) -> None:
    from docx.oxml import OxmlElement

    row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))  # noqa: SLF001 - no public API


def _add_references(
    document: Any,
    block: References,
    collection: PaperCollection,
    labels: list[CitationLabel],
) -> None:
    from docx.shared import Inches

    _add_heading(document, block.heading, 2)
    for index in reference_order(collection.papers):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.5)
        paragraph.paragraph_format.first_line_indent = Inches(-0.5)
        for text, italic in reference(collection.papers[index], labels[index]):
            if text:
                paragraph.add_run(_clean(text)).italic = italic

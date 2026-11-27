r"""LaTeX (.tex) exporter: a literature review draft with a .bib beside it.

Citations are ``\citep{key}`` with the keys of the ``bib`` export, and the
``.bib`` file is written next to the ``.tex``, so the pair compiles as it is
(XeLaTeX or LuaLaTeX, then BibTeX). To use the text in a thesis, copy the
part between the two ``% ---`` lines into the chapter.
"""

from __future__ import annotations

from pathlib import Path

from thesisagents.core.constants import EXPORT_LATEX
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, PaperCollection
from thesisagents.exporters.base import Exporter
from thesisagents.exporters.bibtex import BibtexExporter, unique_keys
from thesisagents.exporters.i18n import normalise_language
from thesisagents.exporters.review_document import (
    Bullets,
    Cite,
    Heading,
    Inline,
    Paragraph,
    References,
    Table,
    review_blocks,
)

_SECTIONS = {1: "section", 2: "subsection", 3: "subsubsection"}
_CJK = {"zh-tw", "zh-cn", "ja", "ko"}

_ESCAPES = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "%": r"\%",
    "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "<": r"\textless{}", ">": r"\textgreater{}",
}


def escape(text: str) -> str:
    r"""``text`` with the characters LaTeX treats specially written out.

    >>> escape("50% of A&B_c")
    '50\\% of A\\&B\\_c'
    """
    cleaned = "".join(c for c in text if c >= " " or c in "\n\t")
    return "".join(_ESCAPES.get(c, c) for c in cleaned)


class LatexExporter(Exporter):
    format = EXPORT_LATEX
    extension = "tex"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        out_path = self.resolve_out_path(collection, options)
        try:
            content = self._render(collection, options, out_path.stem)
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path.write_text(content, encoding="utf-8")
        BibtexExporter().write(
            collection, out_path.with_suffix(".bib"), include_abstract=options.include_abstract
        )
        return out_path

    def _render(self, collection: PaperCollection, options: ExportOptions, stem: str) -> str:
        language = normalise_language(options.language)
        keys = unique_keys(collection.papers)
        body: list[str] = []
        for block in review_blocks(
            collection, options.language, include_abstract=options.include_abstract
        ):
            if isinstance(block, Heading):
                # The numbers belong to the author's own document.
                text = block.text.split(" ", 1)[1] if block.level > 1 else block.text
                body.append(f"\\{_SECTIONS[block.level]}{{{escape(text)}}}")
            elif isinstance(block, Paragraph):
                body.append(_inline(block.content, keys))
            elif isinstance(block, Bullets):
                items = "\n".join(f"  \\item {_item(item, keys)}" for item in block.items)
                body.append(f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}")
            elif isinstance(block, Table):
                body.append(_table(block, keys))
            elif isinstance(block, References):
                body.append(f"% --- references\n\\bibliography{{{stem}}}")
        return _document("\n\n".join(body), language)


def _inline(content: Inline, keys: list[str]) -> str:
    return "".join(
        f"\\citep{{{keys[piece.index]}}}" if isinstance(piece, Cite) else escape(piece)
        for piece in content
    ).strip()


def _item(content: Inline, keys: list[str]) -> str:
    r"""The text of an ``\item``, which takes a leading ``[`` for its label."""
    text = _inline(content, keys)
    return "{}" + text if text.startswith("[") else text


def _table(block: Table, keys: list[str]) -> str:
    # longtable, because a review's table is longer than a page.
    columns = "p{0.16\\linewidth}p{0.24\\linewidth}p{0.26\\linewidth}p{0.24\\linewidth}"
    rendered = [
        " & ".join(
            " \\newline ".join(
                part.strip() for part in _inline(cell, keys).split("\n") if part.strip()
            )
            for cell in row
        )
        + " \\\\"
        for row in block.rows
    ]
    header, *rows = rendered
    return "\n".join([
        f"\\begin{{longtable}}{{{columns}}}",
        f"\\caption{{{escape(block.caption)}}} \\\\",
        "\\toprule", header, "\\midrule", "\\endfirsthead",
        "\\toprule", header, "\\midrule", "\\endhead",
        *rows, "\\bottomrule", "\\end{longtable}",
    ])


def _document(body: str, language: str) -> str:
    fonts = "\\usepackage{fontspec}\n"
    if language in _CJK:
        fonts += "\\usepackage{xeCJK}\n"
    elif language == "hi":
        # The main font: a family nothing switches to leaves the text unreadable.
        fonts += "\\setmainfont[Script=Devanagari]{Noto Serif Devanagari}\n"
    # xeCJK works with XeLaTeX only.
    engines = "XeLaTeX" if language in _CJK else "XeLaTeX or LuaLaTeX"
    return (
        f"% Compile with {engines}, then BibTeX.\n"
        "\\documentclass[12pt]{article}\n"
        f"{fonts}"
        "\\usepackage[round]{natbib}\n\\usepackage{booktabs,longtable}\n"
        "\\usepackage[hidelinks]{hyperref}\n"
        "\\bibliographystyle{apalike}\n\\begin{document}\n% --- text\n\n"
        f"{body}\n\n\\end{{document}}\n"
    )

"""BibTeX exporter. Stable, collision-free keys."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from thesisagents.core.constants import EXPORT_BIBTEX
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection
from thesisagents.exporters.base import Exporter


class BibtexExporter(Exporter):
    format = EXPORT_BIBTEX
    extension = "bib"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        try:
            content = self._render(collection)
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def _render(self, collection: PaperCollection) -> str:
        entries = [
            _render_entry(key, paper)
            for key, paper in zip(unique_keys(collection.papers), collection.papers, strict=True)
        ]
        return "\n\n".join(entries) + "\n"

    def write(self, collection: PaperCollection, path: Path) -> None:
        """Write the entries to ``path``, for the LaTeX draft that cites them."""
        path.write_text(self._render(collection), encoding="utf-8")


def unique_keys(papers: Iterable[Paper]) -> list[str]:
    """One cite key per paper, repeated ones told apart by a letter.

    The LaTeX draft cites with the same keys, so both take them from here.
    """
    used_keys: dict[str, int] = {}
    keys: list[str] = []
    for paper in papers:
        base_key = paper.bibtex_key()
        count = used_keys.get(base_key, 0)
        used_keys[base_key] = count + 1
        keys.append(base_key if count == 0 else f"{base_key}{chr(ord('a') + count)}")
    return keys


def bibtex_entry(paper: Paper) -> str:
    """One paper as a BibTeX entry under its own ``bibtex_key()``.

    For copying a single citation (the GUI's *Copy BibTeX*). A ``.bib``
    export goes through :class:`BibtexExporter` instead, which also makes
    keys unique across the whole collection.

    Example: ``bibtex_entry(paper)`` → ``"@article{vaswani2017attention, ..."``.
    """
    return _render_entry(paper.bibtex_key(), paper)


def _render_entry(key: str, paper: Paper) -> str:
    entry_type = "article" if paper.venue else "misc"
    fields: list[tuple[str, str]] = []
    fields.append(("title", _bib_escape(paper.title)))
    if paper.authors:
        fields.append(("author", _bib_escape(" and ".join(paper.authors))))
    if paper.year is not None:
        fields.append(("year", str(paper.year)))
    if paper.venue:
        fields.append(("journal", _bib_escape(paper.venue)))
    if paper.doi:
        fields.append(("doi", _bib_escape(paper.doi)))
    if paper.arxiv_id:
        fields.append(("eprint", _bib_escape(paper.arxiv_id)))
        fields.append(("archivePrefix", "arXiv"))
    if paper.url:
        fields.append(("url", _bib_escape(paper.url)))
    if paper.abstract:
        fields.append(("abstract", _bib_escape(paper.short_abstract())))
    field_block = ",\n  ".join(f"{name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n  {field_block}\n}}"


_REPLACEMENTS = (
    ("\\", r"\textbackslash{}"),
    ("{", r"\{"),
    ("}", r"\}"),
    ("&", r"\&"),
    ("%", r"\%"),
    ("$", r"\$"),
    ("#", r"\#"),
    ("_", r"\_"),
    ("~", r"\textasciitilde{}"),
    ("^", r"\textasciicircum{}"),
)


def _bib_escape(value: str) -> str:
    out = value
    for src, target in _REPLACEMENTS:
        out = out.replace(src, target)
    return out

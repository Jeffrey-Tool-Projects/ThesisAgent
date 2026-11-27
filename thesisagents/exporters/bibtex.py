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
            content = self._render(collection, include_abstract=options.include_abstract)
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def _render(self, collection: PaperCollection, *, include_abstract: bool = True) -> str:
        entries = [
            _render_entry(key, paper, include_abstract=include_abstract)
            for key, paper in zip(unique_keys(collection.papers), collection.papers, strict=True)
        ]
        return "\n\n".join(entries) + "\n"

    def write(
        self, collection: PaperCollection, path: Path, *, include_abstract: bool = True
    ) -> None:
        """Write the entries to ``path``, for the LaTeX draft that cites them.

        ``include_abstract`` is the draft's own ``ExportOptions`` value, so the
        ``.bib`` beside a ``--no-abstract`` draft carries no abstract either.
        """
        path.write_text(
            self._render(collection, include_abstract=include_abstract), encoding="utf-8"
        )


def unique_keys(papers: Iterable[Paper]) -> list[str]:
    """One cite key per paper, repeated ones told apart by a letter.

    The LaTeX draft cites with the same keys, so both take them from here, and
    the CLI names each per-paper deck after its key. Every final key is checked
    against the keys already handed out, not only against the base key. The
    failure this prevents: titles ``Gene A``, ``Gene C`` and ``GeneB study`` by
    one author in one year have the base keys ``doe2025gene``, ``doe2025gene``
    and ``doe2025geneb``, so counting base keys alone gave the second and the
    third paper ``doe2025geneb``, and one deck overwrote the other.

    Example: for those three papers the keys are ``["doe2025gene",
    "doe2025geneb", "doe2025genebb"]``. The third paper keeps its own base
    key and takes the next letter after it, because ``doe2025geneb`` was
    already handed out.
    """
    taken: set[str] = set()
    next_count: dict[str, int] = {}
    keys: list[str] = []
    for paper in papers:
        base_key = paper.bibtex_key()
        count = next_count.get(base_key, 0)
        key = _suffixed(base_key, count)
        while key in taken:
            count += 1
            key = _suffixed(base_key, count)
        next_count[base_key] = count + 1
        taken.add(key)
        keys.append(key)
    return keys


def _suffixed(base_key: str, count: int) -> str:
    """``base_key`` for the first paper, then ``b``, ``c``, ... and numbers."""
    if count == 0:
        return base_key
    # After "z" a number: the character behind it in ASCII is a brace.
    return f"{base_key}{chr(ord('a') + count) if count < 26 else count + 1}"


def bibtex_entry(paper: Paper) -> str:
    """One paper as a BibTeX entry under its own ``bibtex_key()``.

    For copying a single citation (the GUI's *Copy BibTeX*). A ``.bib``
    export goes through :class:`BibtexExporter` instead, which also makes
    keys unique across the whole collection.

    Example: ``bibtex_entry(paper)`` → ``"@article{vaswani2017attention, ..."``.
    """
    return _render_entry(paper.bibtex_key(), paper)


def _render_entry(key: str, paper: Paper, *, include_abstract: bool = True) -> str:
    """One entry. ``include_abstract=False`` (``--no-abstract``) leaves the
    ``abstract`` field out, which the entry used to carry whatever the option said.
    """
    entry_type = "article" if paper.venue else "misc"
    fields: list[tuple[str, str]] = []
    fields.append(("title", _bib_escape(paper.title)))
    if paper.authors:
        fields.append(("author", " and ".join(map(_bib_name, paper.authors))))
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
    if include_abstract and paper.abstract:
        fields.append(("abstract", _bib_escape(paper.short_abstract())))
    field_block = ",\n  ".join(f"{name} = {{{value}}}" for name, value in fields)
    return f"@{entry_type}{{{key},\n  {field_block}\n}}"


_REPLACEMENTS = str.maketrans({
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
})


def _bib_name(name: str) -> str:
    """One author. "Barnes and Noble" needs braces, or BibTeX reads two people."""
    escaped = _bib_escape(" ".join(name.split()))
    return f"{{{escaped}}}" if " and " in f" {escaped.lower()} " else escaped


def _bib_escape(value: str) -> str:
    """``value`` with LaTeX's special characters written out.

    In one pass: replacing one character after the other escaped the braces
    of ``\\textbackslash{}`` again, which prints them.
    """
    return value.translate(_REPLACEMENTS)

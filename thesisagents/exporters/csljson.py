"""CSL-JSON exporter — the Pandoc / citeproc citation format.

CSL-JSON (Citation Style Language JSON, https://citationstyles.org) is the
intermediate format Pandoc and citeproc read to render a bibliography in any of
the thousands of published CSL styles (APA, IEEE, Nature, …). It is a JSON array
of citation-item objects; passing the file to ``pandoc --citeproc --bibliography
refs.csl.json`` formats every reference for you.

Why this lives next to the BibTeX and RIS exporters: those three are the
interchange triad for reference tooling — BibTeX for LaTeX, RIS for desktop
managers, CSL-JSON for Markdown/Pandoc workflows. A thesis written in Markdown
wants this one.

Author-name handling is the one subtlety. ``Paper`` stores a flat "First Last"
display string, but CSL wants a structured ``{"family": …, "given": …}`` so a
style can render "Last, F." or "First Last" as the style dictates. Names are
split by ``apa.split_name``, which the Word draft uses too: the last token is
``family``, "Last, First" is read as written, and a name in Chinese, Japanese or
Korean characters stays whole.
"""

from __future__ import annotations

import json
from pathlib import Path

from thesisagents.core.constants import EXPORT_CSL
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection
from thesisagents.exporters.apa import split_name
from thesisagents.exporters.base import Exporter
from thesisagents.exporters.bibtex import unique_keys

# CSL reference types. A paper with a venue is a journal/conference article; one
# without (an arXiv preprint, a tech report) is a "manuscript", the CSL type
# citeproc renders without a container title.
_TYPE_ARTICLE = "article-journal"
_TYPE_MANUSCRIPT = "manuscript"


class CslJsonExporter(Exporter):
    format = EXPORT_CSL
    # Compound extension so the artefact is `<stem>.csl.json` — distinct from
    # the plain `<stem>.json` PaperCollection dump, which would otherwise
    # overwrite it (both share the same stem).
    extension = "csl.json"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        try:
            items = [
                _render_item(key, paper)
                for key, paper in _keyed(collection)
            ]
            content = json.dumps(items, ensure_ascii=False, indent=2) + "\n"
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        out_path.write_text(content, encoding="utf-8")
        return out_path


def _keyed(collection: PaperCollection):
    """Yield (collision-free cite key, paper), reusing the BibTeX key scheme so
    the same paper carries the same id across the bib / CSL exports."""
    yield from zip(unique_keys(collection.papers), collection.papers, strict=True)


def _render_item(key: str, paper: Paper) -> dict:
    item: dict = {
        "id": key,
        "type": _TYPE_ARTICLE if paper.venue else _TYPE_MANUSCRIPT,
        "title": paper.title,
    }
    authors = [_name_parts(name) for name in paper.authors]
    if authors:
        item["author"] = authors
    if paper.year is not None:
        item["issued"] = {"date-parts": [[paper.year]]}
    if paper.venue:
        item["container-title"] = paper.venue
    if paper.doi:
        item["DOI"] = paper.doi
    if paper.url:
        item["URL"] = paper.url
    if paper.abstract:
        item["abstract"] = paper.short_abstract()
    return item


def _name_parts(name: str) -> dict[str, str]:
    """Split a flat display name into CSL ``family`` / ``given`` parts."""
    family, given = split_name(name)
    given, _comma, suffix = (part.strip() for part in given.partition(","))
    parts = {"family": family, "given": given, "suffix": suffix}
    return {key: value for key, value in parts.items() if value or key == "family"}

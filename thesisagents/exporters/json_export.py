"""JSON exporter: dumps the full PaperCollection as structured data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from thesisagents.core.constants import EXPORT_JSON
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection
from thesisagents.exporters.base import Exporter


class JsonExporter(Exporter):
    format = EXPORT_JSON
    extension = "json"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        try:
            payload = {
                "query": {
                    "keywords": collection.query.keywords,
                    "sources": list(collection.query.sources),
                    "max_results": collection.query.max_results,
                    "year_from": collection.query.year_from,
                    "year_to": collection.query.year_to,
                },
                "papers": [
                    _paper_dict(paper, include_abstract=options.include_abstract)
                    for paper in collection.papers
                ],
            }
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        out_path.write_text(content, encoding="utf-8")
        return out_path


def _paper_dict(paper: Paper, *, include_abstract: bool) -> dict[str, Any]:
    """``paper.to_dict()``, with an empty ``abstract`` under ``--no-abstract``.

    The key stays, so the file keeps one schema and still loads with
    ``Paper.from_dict``. The failure this prevents: the dump used to carry
    every abstract whatever ``include_abstract`` said.

    Example: ``_paper_dict(paper, include_abstract=False)["abstract"] == ""``.
    """
    data = paper.to_dict()
    if not include_abstract:
        data["abstract"] = ""
    return data

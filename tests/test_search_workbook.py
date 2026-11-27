"""Search export round trips and edits to a workbook before reopening it."""

from dataclasses import replace

import pytest
from openpyxl import load_workbook

from thesisagents.core.models import ExportOptions, PaperCollection, Query
from thesisagents.core.search_workbook import read_search_workbook
from thesisagents.exporters.xlsx import XlsxExporter


def _export(tmp_path, papers):
    collection = PaperCollection(Query("a search", ("arxiv",)), tuple(papers))
    return XlsxExporter().export(collection, ExportOptions(formats=("xlsx",), out_dir=tmp_path))


def test_reopening_preserves_author_names_and_respects_workbook_edits(tmp_path, sample_papers):
    names = ("Lovelace, Ada", "Prince", "王小明")
    path = _export(tmp_path, [replace(sample_papers[0], authors=names)])
    assert read_search_workbook(path).papers[0].authors == names

    workbook = load_workbook(path)
    assert workbook["Papers"]["C2"].value == ", ".join(names)
    workbook["Papers"]["C2"] = "Hopper, Grace"
    workbook.save(path)
    workbook.close()
    assert read_search_workbook(path).papers[0].authors == ("Hopper, Grace",)


def test_legacy_workbook_and_numeric_cells(tmp_path, sample_papers):
    path = _export(tmp_path, sample_papers)
    workbook = load_workbook(path)
    sheet = workbook["Papers"]
    sheet.delete_cols(12)
    sheet["C3"] = "Hopper, Grace"
    sheet["D2"] = "2020"
    sheet["E2"] = 24
    sheet["F2"] = 17
    sheet["J2"] = "5"
    sheet["K2"] = 0
    workbook["Query"]["B1"] = 123
    workbook["Query"]["B4"] = "2010"
    workbook.save(path)
    workbook.close()
    result = read_search_workbook(path)
    assert result.papers[0].authors == sample_papers[0].authors
    assert result.papers[1].authors == ("Hopper, Grace",)
    first = result.papers[0]
    assert (first.year, first.citation_count) == (2020, 5)
    assert (first.source, first.venue, first.abstract) == ("17", "24", "0")
    assert (result.query.keywords, result.query.year_from) == ("123", 2010)


@pytest.mark.parametrize(
    ("cell", "value", "field"), [("D2", 2020.5, "Year"), ("J2", "?", "Citations")]
)
def test_bad_numbers_name_the_field(tmp_path, sample_papers, cell, value, field):
    path = _export(tmp_path, sample_papers)
    workbook = load_workbook(path)
    workbook["Papers"][cell] = value
    workbook.save(path)
    workbook.close()
    with pytest.raises(ValueError, match=field):
        read_search_workbook(path)

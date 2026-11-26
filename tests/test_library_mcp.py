"""The MCP library tools, called through the registered handlers."""

from __future__ import annotations

import asyncio
import json

import pytest

from thesisagents import mcp as mcp_pkg
from thesisagents.core.export_validation import Verdict, VerificationStatus
from thesisagents.library import Library
from thesisagents.mcp.server import ToolError


@pytest.fixture
def server():
    return mcp_pkg.build_server()


@pytest.fixture
def library_path(tmp_path) -> str:
    return str(tmp_path / "thesis.db")


def _call(server, tool: str, /, **kwargs):
    result = asyncio.run(server.call_tool(tool, kwargs))
    if isinstance(result, tuple):
        result = result[0]
    result = getattr(result, "content", result)
    return json.loads(next(block.text for block in result if getattr(block, "text", None)))


def _add(server, library_path, papers, **kwargs):
    return _call(
        server, "library_add", library=library_path,
        papers=[paper.to_dict() for paper in papers], **kwargs,
    )


def test_the_three_library_tools_are_registered(server):
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {"library_add", "library_search", "library_stats"} <= names


def test_library_add_then_search_round_trip(server, library_path, sample_papers):
    added = _add(server, library_path, sample_papers, keywords="attention")
    assert (added["added"], added["merged"], added["total"]) == (2, 0, 2)
    assert added["library"] == library_path

    found = _call(server, "library_search", library=library_path, query="attention")

    assert (found["total"], found["count"]) == (2, 1)
    assert found["papers"] == [sample_papers[0].to_dict()]
    entry = found["entries"][0]
    assert entry["paper_key"] == sample_papers[0].dedup_key()
    assert entry["bibtex_key"] == sample_papers[0].bibtex_key()
    assert (entry["times_seen"], entry["sources"]) == (1, ["arxiv"])
    assert entry["score"]["relevance"] > 0


def test_library_add_is_a_merge(server, library_path, sample_papers):
    _add(server, library_path, sample_papers)
    again = _add(server, library_path, sample_papers)
    assert (again["added"], again["merged"], again["total"]) == (0, 2, 2)


def test_library_add_stores_the_relations_snowball_returns(server, library_path, sample_papers):
    first, second = sample_papers
    relation = {
        "source_key": first.dedup_key(), "target_key": second.dedup_key(),
        "relation": "references", "provider": "openalex", "depth": 1,
    }
    added = _add(server, library_path, sample_papers, relations=[relation])
    assert (added["relations_added"], added["relations_skipped"]) == (1, 0)
    assert _call(server, "library_stats", library=library_path)["relations"] == 1


@pytest.mark.parametrize(
    ("relation", "message"),
    [
        (
            {"source_key": "doi:10.1/a"},
            "relation is missing field(s): target_key, relation, provider, depth",
        ),
        (
            {"source_key": "a", "target_key": "b", "relation": "mentions",
             "provider": "openalex", "depth": 1},
            "'relation' must be 'references' or 'cited_by'",
        ),
    ],
)
def test_library_add_names_what_is_wrong_with_a_relation(
    server, library_path, sample_papers, relation, message
):
    with pytest.raises(ToolError) as raised:
        _add(server, library_path, sample_papers, relations=[relation])
    assert message in str(raised.value)


def test_library_add_requires_papers(server, library_path):
    with pytest.raises(ToolError, match="requires at least one paper"):
        _call(server, "library_add", library=library_path, papers=[])


def test_library_search_lists_recent_papers_for_an_empty_query(
    server, library_path, sample_papers
):
    _add(server, library_path, sample_papers)
    found = _call(server, "library_search", library=library_path, limit=1)
    assert (found["count"], found["total"]) == (1, 2)
    assert found["entries"][0]["score"] is None


def test_library_search_rejects_a_limit_out_of_range(server, library_path, sample_papers):
    _add(server, library_path, sample_papers)
    with pytest.raises(ToolError, match=r"limit must be in \[1, 200\]"):
        _call(server, "library_search", library=library_path, limit=0)


@pytest.mark.parametrize("tool", ["library_search", "library_stats"])
def test_reading_a_missing_library_is_a_tool_error(server, tmp_path, tool):
    missing = tmp_path / "typo.db"
    with pytest.raises(ToolError, match="no library at"):
        _call(server, tool, library=str(missing))
    assert not missing.exists()


def test_library_stats_reports_size_and_recent_runs(server, library_path, sample_papers):
    _add(server, library_path, sample_papers, keywords="attention")
    stats = _call(server, "library_stats", library=library_path)

    assert (stats["papers"], stats["runs"], stats["relations"]) == (2, 1, 0)
    assert stats["sources"] == {"arxiv": 2}
    assert (stats["year_min"], stats["year_max"]) == (2023, 2024)
    assert stats["recent_runs"] == [
        {
            "run_id": 1, "started_at": stats["last_run"], "kind": "mcp",
            "keywords": "attention", "papers": 2,
        }
    ]


def test_export_remembers_verdicts_in_the_library(
    server, library_path, sample_papers, tmp_path, monkeypatch
):
    from thesisagents.core import export_validation

    asked: list[int] = []

    async def _recording(targets):
        asked.append(len(targets))
        return {target: Verdict(VerificationStatus.OK) for target in targets}

    monkeypatch.setattr(export_validation, "_resolve_targets", _recording)
    arguments = {
        "papers": [paper.to_dict() for paper in sample_papers], "keywords": "attention",
        "formats": ["bib"], "out_dir": str(tmp_path / "out"), "library": library_path,
    }
    first = _call(server, "export", **arguments)
    second = _call(server, "export", **arguments)

    assert first["verification"]["ok"] is True
    assert second["verification"]["ok"] is True
    assert asked[0] == 3
    assert sum(asked[1:]) == 0                         # the second call asked nothing
    with Library(library_path) as library:
        assert library.stats().verifications == {"ok": 3}
        assert len(library) == 0                       # export stores verdicts, not papers


# --- editing (mcp/curation_tools.py) ------------------------------------------------


def _fails(server, tool: str, match: str, /, **kwargs):
    with pytest.raises(ToolError, match=match):
        asyncio.run(server.call_tool(tool, kwargs))


def test_the_curation_tools_are_registered(server):
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert {
        "library_update", "library_delete", "library_import", "library_duplicates",
        "library_merge", "library_saved_search", "library_prisma",
    } <= names


def test_library_update_records_what_the_reader_decided(server, library_path, sample_papers):
    _add(server, library_path, sample_papers)
    found = _call(server, "library_search", library=library_path, query="")
    first, second = (entry["paper_id"] for entry in found["entries"])
    updated = _call(
        server, "library_update", library=library_path, paper_ids=[first, second],
        add_tags=["chapter 2"], status="read", decision="include",
    )
    assert updated["tags"] == {"chapter 2": 2}
    assert {p["status"] for p in updated["papers"]} == {"read"}
    assert "abstract" not in updated["papers"][0]
    _call(server, "library_update", library=library_path, paper_ids=[first], note="cite")
    tagged = _call(server, "library_search", library=library_path, tags=["Chapter 2"])
    assert len(tagged["papers"]) == 2
    assert _call(server, "library_search", library=library_path, status="unread")["papers"] == []
    _call(
        server, "library_update", library=library_path, paper_ids=[second],
        remove_tags=["chapter 2"], decision="exclude", stage="full_text", reason="no data",
    )
    flow = _call(server, "library_prisma", library=library_path)
    assert flow["reasons_full_text"] == {"no data": 1}
    _fails(server, "library_update", "exactly one", library=library_path,
           paper_ids=[first, second], note="x")
    _fails(server, "library_update", "reading status", library=library_path,
           paper_ids=[first], status="skimmed")
    _fails(server, "library_update", "no paper with id", library=library_path,
           paper_ids=[999], status="read")


def test_library_delete_merge_and_duplicates(server, library_path, sample_papers):
    from dataclasses import replace

    twin = replace(
        sample_papers[0], source_id="twin", doi="10.9/twin", arxiv_id=None,
        title=sample_papers[0].title + ".", year=1999,
    )
    _add(server, library_path, [*sample_papers, twin])
    groups = _call(server, "library_duplicates", library=library_path)["groups"]
    assert len(groups) == 1
    keep, other = (paper["paper_id"] for paper in groups[0])
    merged = _call(
        server, "library_merge", library=library_path, survivor=keep, others=[other]
    )
    assert merged["total"] == 2
    _fails(server, "library_merge", "two different", library=library_path,
           survivor=keep, others=[keep])
    assert _call(
        server, "library_delete", library=library_path, paper_ids=[keep]
    ) == {"deleted": 1, "total": 1}


def test_library_import_reads_a_bibliography(server, library_path, tmp_path):
    file = tmp_path / "x.bib"
    file.write_text("@misc{a, title={One}}\n@misc{b, author={Nobody}}", encoding="utf-8")
    result = _call(server, "library_import", library=library_path, file=str(file), tags=["z"])
    assert (result["added"], result["skipped"]) == (1, ["line 2: b has no title"])
    file.write_text("@misc{b, author={Nobody}}", encoding="utf-8")
    _fails(server, "library_import", "no usable record", library=library_path, file=str(file))


def test_saved_searches_over_mcp(server, library_path, sample_papers, monkeypatch):
    from thesisagents.core.models import PaperCollection

    async def fake(query, **_kwargs):
        return PaperCollection(query=query, papers=tuple(sample_papers))

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", fake)
    saved = _call(
        server, "library_saved_search", library=library_path, action="save",
        name="att", keywords="attention", sources=["arxiv"],
    )
    assert saved["searches"][0]["query"]["keywords"] == "attention"
    ran = _call(server, "library_saved_search", library=library_path, action="run", name="att")
    assert (ran["found"], len(ran["new"])) == (2, 2)
    again = _call(server, "library_saved_search", library=library_path, action="run", name="att")
    assert again["new"] == []
    listed = _call(
        server, "library_saved_search", library=library_path, action="delete", name="att"
    )
    assert listed["searches"] == []
    _fails(server, "library_saved_search", "action must be", library=library_path, action="go")
    _fails(server, "library_saved_search", "name needs", library=library_path, action="save",
           name="", keywords="x")


def test_library_prisma_draws(server, library_path, sample_papers, tmp_path):
    _add(server, library_path, sample_papers)
    target = tmp_path / "flow.svg"
    result = _call(server, "library_prisma", library=library_path, svg_path=str(target))
    assert result["unique"] == 2
    assert target.read_text(encoding="utf-8").startswith("<svg")
    _fails(server, "library_prisma", "cannot write", library=library_path, svg_path=str(tmp_path))


def test_library_prisma_overwrites_only_drawings(server, library_path, sample_papers, tmp_path):
    _add(server, library_path, sample_papers)
    _fails(server, "library_prisma", "does not end with .svg", library=library_path,
           svg_path=library_path)
    assert _call(server, "library_prisma", library=library_path)["unique"] == 2


def test_library_import_tags_a_paper_that_was_merged(server, library_path, tmp_path):
    file = tmp_path / "x.bib"
    file.write_text("@misc{a, title={One}, doi={10.1000/one}}", encoding="utf-8")
    _call(server, "library_import", library=library_path, file=str(file))
    file.write_text(
        "@misc{a, title={Uno}, doi={10.1000/one}}\n@misc{b, title={Due}, doi={10.1000/due}}",
        encoding="utf-8",
    )
    _call(server, "library_import", library=library_path, file=str(file), tags=["t"])
    found = _call(server, "library_search", library=library_path, tags=["t"])
    assert found["count"] == 2


def test_library_update_makes_all_changes_or_none(server, library_path, sample_papers):
    _add(server, library_path, sample_papers)
    with pytest.raises(ToolError):
        _call(
            server, "library_update", library=library_path, paper_ids=[1],
            add_tags=["chapter 2"], status="raed",
        )
    with Library(library_path, create=False) as library:
        assert not library.tags()

"""Tags, notes, screening, duplicates, saved searches and PRISMA in the library."""
from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ElementTree  # noqa: S405 - parses what this code wrote

import pytest

from thesisagents import cli
from thesisagents.core.diagnostics import SearchDiagnostics, SourceStat
from thesisagents.core.exceptions import LibraryError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary, Query
from thesisagents.library import (
    Library,
    prisma_flow,
    prisma_svg,
    run_saved_search,
    schema,
)
from thesisagents.library.curation import normalise_tag


def _paper(source_id: str, title: str, **fields) -> Paper:
    defaults = {
        "source": "arxiv", "authors": ("Ada Lovelace",), "year": 2024, "venue": None,
        "abstract": "", "url": f"https://example.org/{source_id}",
    }
    defaults.update(fields)
    return Paper(source_id=source_id, title=title, **defaults)


@pytest.fixture
def library(tmp_path):
    with Library(tmp_path / "lib.db") as store:
        store.add_papers([
            _paper("1", "Graph neural networks for molecules", doi="10.1/a"),
            _paper("2", "A survey of program repair", doi="10.1/b"),
            _paper("3", "Reinforcement learning in games", doi="10.1/c"),
        ])
        yield store


def _ids(library: Library) -> dict[str, int]:
    return {entry.paper.source_id: entry.paper_id for entry in library.entries()}


def _entry(library: Library, paper_id: int):
    return next(e for e in library.entries() if e.paper_id == paper_id)


# --- annotations ------------------------------------------------------------------


def test_tags_notes_and_status_are_kept_with_the_paper(library):
    ids = _ids(library)
    library.add_tags([ids["1"], ids["2"]], ["Chapter 2", "chapter  2", "to cite"])
    library.set_note(ids["1"], "  read §3 again  ")
    library.set_reading_status([ids["1"]], "reading")
    entry = _entry(library, ids["1"])
    assert entry.tags == ("Chapter 2", "to cite")
    assert (entry.note, entry.status) == ("read §3 again", "reading")
    assert _entry(library, ids["3"]).status == "unread"
    assert library.tags() == {"Chapter 2": 2, "to cite": 2}
    library.remove_tags([ids["1"], ids["2"]], ["CHAPTER 2"])
    library.set_note(ids["1"], "")
    assert _entry(library, ids["1"]).tags == ("to cite",)
    assert _entry(library, ids["1"]).note == ""
    assert _entry(library, ids["1"]).status == "reading"


def test_importing_again_keeps_what_the_reader_recorded(library):
    ids = _ids(library)
    library.add_tags([ids["1"]], ["mine"])
    library.screen([ids["1"]], "include", reason="fits")
    library.add_papers([_paper("1", "Graph neural networks for molecules", doi="10.1/a")])
    entry = _entry(library, ids["1"])
    assert entry.tags == ("mine",)
    assert entry.screening[0].decision == "include"


@pytest.mark.parametrize("tag", ["", "  ", ",", "x" * 61])
def test_unusable_tags_are_refused(tag):
    with pytest.raises(ValueError, match="tag"):
        normalise_tag(tag)


def test_wrong_values_change_nothing(library):
    ids = _ids(library)
    with pytest.raises(ValueError, match="reading status"):
        library.set_reading_status([ids["1"]], "skimmed")
    with pytest.raises(ValueError, match="decision"):
        library.screen([ids["1"]], "perhaps")
    with pytest.raises(ValueError, match="stage"):
        library.screen([ids["1"]], "include", stage="second")
    with pytest.raises(ValueError, match="reason"):
        library.screen([ids["1"]], "exclude", stage="full_text", reason="  ")
    with pytest.raises(LibraryError, match="999"):
        library.add_tags([ids["1"], 999], ["x"])
    assert library.annotations() == {}


def test_search_narrows_to_what_was_recorded(library):
    ids = _ids(library)
    library.add_tags([ids["1"], ids["2"]], ["Keep"])
    library.add_tags([ids["2"]], ["later"])
    library.set_reading_status([ids["2"]], "read")
    library.screen([ids["2"]], "include")

    def found(**criteria):
        return {e.paper.source_id for e in library.search(**criteria)}

    assert found(tags=["keep"]) == {"1", "2"}
    assert found(tags=["keep", "LATER"]) == {"2"}
    assert found(status="unread") == {"1", "3"}
    assert found(decision="include") == {"2"}
    assert found(decision="none") == {"1", "3"}
    assert found(query="survey repair", tags=["keep"]) == {"2"}
    assert [p.source_id for p in library.collection(tags=["later"]).papers] == ["2"]


# --- deleting and merging -------------------------------------------------------------


def test_deleting_removes_everything_recorded(library):
    ids = _ids(library)
    library.add_tags([ids["1"]], ["x"])
    library.screen([ids["1"]], "maybe")
    assert library.delete([ids["1"], ids["1"]]) == 1
    assert len(library) == 2
    assert library.tags() == {}
    assert library.annotations() == {}
    assert not library.holds(_paper("1", "Graph neural networks for molecules", doi="10.1/a"))


def test_a_preprint_and_its_journal_version_become_one(library):
    library.add_papers([
        _paper("p", "Attention is all you need", doi="10.48550/x", arxiv_id="1706.03762"),
        _paper("j", "Attention is All You Need!", doi="10.5555/y", venue="NeurIPS"),
    ])
    ids = _ids(library)
    assert (ids["p"], ids["j"]) in library.duplicate_candidates()
    library.add_tags([ids["p"]], ["preprint"])
    library.set_note(ids["p"], "first version")
    library.set_note(ids["j"], "cite this one")
    library.set_reading_status([ids["p"]], "read")
    library.screen([ids["p"]], "include")

    library.merge(ids["j"], [ids["p"]])

    entry = _entry(library, ids["j"])
    assert (entry.paper.venue, entry.paper.doi) == ("NeurIPS", "10.5555/y")
    assert entry.paper.arxiv_id == "1706.03762"
    assert entry.tags == ("preprint",)
    assert entry.note == "cite this one\n\nfirst version"
    assert entry.status == "read"
    assert entry.screening[0].decision == "include"
    # Both identifiers find it from now on.
    again = library.add_papers([
        _paper("p", "Attention is all you need", doi="10.48550/x", arxiv_id="1706.03762")
    ])
    assert (again.added, again.merged) == (0, 1)
    assert library.duplicate_candidates() == []


def test_an_import_that_joins_two_papers_keeps_their_records(library):
    # One record carries the DOI of the first and the arXiv id of the second.
    library.add_papers([
        _paper("d", "Deep widgets explained at length", doi="10.9/z"),
        _paper("x", "Widgets, deeply considered by many", arxiv_id="2401.00001", year=2023),
    ])
    ids = _ids(library)
    library.add_tags([ids["x"]], ["from x"])
    library.add_papers([
        _paper("both", "Deep widgets explained at length", doi="10.9/z", arxiv_id="2401.00001")
    ])
    assert _entry(library, ids["d"]).tags == ("from x",)


def test_merging_one_paper_with_itself_is_refused(library):
    ids = _ids(library)
    with pytest.raises(ValueError, match="two different"):
        library.merge(ids["1"], [ids["1"]])


def test_different_papers_are_not_suggested(library):
    library.add_papers([
        _paper("s1", "A survey of program repair tools"),
        _paper("s2", "A survey of graph repair methods"),
        _paper("short", "Editorial"),
        _paper("short2", "Editorial", year=2020),
    ])
    assert library.duplicate_candidates() == []


# --- saved searches ---------------------------------------------------------------------


_QUERY = Query("graphs", ("arxiv",), max_results=5, year_from=2020)


async def test_a_saved_search_reports_only_what_is_new(library):
    library.save_search("  my   graphs ", _QUERY)
    asked = []

    async def search(query):
        asked.append(query)
        return PaperCollection(query=query, papers=(
            _paper("1", "Graph neural networks for molecules", doi="10.1/a"),
            _paper("9", "Brand new graphs", doi="10.1/new"),
        ))

    first = await run_saved_search(library, "MY graphs", search)
    assert asked == [_QUERY]
    assert [p.source_id for p in first.new_papers] == ["9"]
    second = await run_saved_search(library, "my graphs", search)
    assert second.new_papers == ()
    saved = library.saved_search("my graphs")
    assert (saved.last_new, saved.query) == (0, _QUERY)
    assert saved.last_run_at is not None
    assert library.runs()[0].kind == "saved"


def test_saving_under_the_same_name_replaces_the_query(library):
    library.save_search("a", _QUERY)
    library.record_saved_run("a", 3)
    library.save_search("a", Query("other", ("dblp",)))
    saved = library.saved_searches()
    assert [(s.name, s.query.keywords, s.last_new) for s in saved] == [("a", "other", None)]
    library.delete_saved_search("A")
    assert library.saved_searches() == []
    with pytest.raises(LibraryError, match="no saved search"):
        library.saved_search("a")


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_a_saved_search_needs_a_name(library, name):
    with pytest.raises(ValueError, match="name"):
        library.save_search(name, _QUERY)


# --- PRISMA -----------------------------------------------------------------------------


def _stat(source: str, returned: int, after_dedup: int | None = None) -> SourceStat:
    return SourceStat(
        source=source, requested=25, returned=returned,
        after_dedup=returned if after_dedup is None else after_dedup,
    )


def test_prisma_counts_what_was_recorded(tmp_path):
    with Library(tmp_path / "p.db") as library:
        papers = tuple(
            _paper(str(i), f"Study number {i} about topic {i * 7}") for i in range(10)
        )
        library.add_collection(PaperCollection(
            query=Query("x", ("arxiv", "dblp")), papers=papers,
            diagnostics=SearchDiagnostics(
                source_stats=(_stat("arxiv", 8), _stat("dblp", 6, 2)),
            ),
        ))
        ids = [e.paper_id for e in library.entries()]
        library.screen(ids[:6], "include")
        library.screen(ids[6:8], "exclude", reason="off topic")
        library.screen([ids[8]], "maybe")
        library.screen(ids[:3], "include", stage="full_text")
        library.screen([ids[3]], "exclude", stage="full_text", reason="no data")
        # A full-text decision without passing the first stage does not count.
        library.screen([ids[9]], "include", stage="full_text")
        flow = prisma_flow(library)
    assert flow.identified == {"arxiv": 8, "dblp": 6}
    assert (flow.duplicates_removed, flow.removed_other, flow.unique) == (4, 0, 10)
    assert (flow.excluded_abstract, flow.awaiting) == (2, 2)
    assert (flow.full_text, flow.excluded_full_text, flow.included) == (6, 1, 3)
    assert flow.full_text_awaiting == 2
    assert flow.reasons_abstract == {"off topic": 2}
    assert flow.reasons_full_text == {"no data": 1}
    # What enters a step equals what leaves it.
    assert flow.unique == flow.excluded_abstract + flow.full_text + flow.awaiting
    assert flow.full_text == flow.included + flow.excluded_full_text + flow.full_text_awaiting


def test_an_import_without_statistics_counts_its_papers(library):
    flow = prisma_flow(library)
    assert flow.identified == {"manual": 3}
    assert flow.duplicates_removed == 0


def test_prisma_drawing_is_valid_and_escapes_reasons(library):
    ids = _ids(library)
    library.screen([ids["1"]], "exclude", reason='<b>"off" & wrong</b> ' + "非常長的理由" * 12)
    library.screen([ids["2"]], "include")
    drawing = prisma_svg(prisma_flow(library))
    root = ElementTree.fromstring(drawing)  # noqa: S314 - written by this code
    texts = [node.text for node in root.iter("{http://www.w3.org/2000/svg}text")]
    assert "Records screened (n = 3)" in texts
    long = next(text for text in texts if text.startswith("<b>"))
    assert long.endswith("… (n = 1)")


# --- schema -----------------------------------------------------------------------------


def test_a_version_1_library_is_upgraded_with_its_papers(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with monkeypatch.context() as patch:
        patch.setattr(schema, "SCHEMA_VERSION", 1)
        conn = sqlite3.connect(path, isolation_level=None)
        schema.prepare(conn, str(path))
        conn.execute(
            "INSERT INTO papers (record, title, year, first_seen, last_seen) VALUES (?,?,?,?,?)",
            ('{"source":"arxiv","source_id":"1","title":"Old","authors":[],"year":2001,'
             '"venue":null,"abstract":"","url":"https://example.org"}', "Old", 2001, "a", "a"),
        )
        conn.close()
    with Library(path, create=False) as library:
        assert library.schema_version == schema.SCHEMA_VERSION
        entry = library.entries()[0]
        assert (entry.paper.title, entry.status, entry.tags) == ("Old", "unread", ())
        library.add_tags([entry.paper_id], ["kept"])


# --- command line ------------------------------------------------------------------------


@pytest.fixture
def run(library, tmp_path, capsys):
    path = str(library.path)

    def call(*args: str) -> tuple[int, str, str]:
        code = cli.main(["library", path, *args])
        out = capsys.readouterr()
        return code, out.out, out.err

    return call


def test_cli_edits_a_library(library, run):
    ids = _ids(library)
    one, two = str(ids["1"]), str(ids["2"])
    assert run("tag", one, two, "--add", "chapter 2")[0] == 0
    assert run("status", "read", one)[0] == 0
    assert run("note", one, "用在 2.3")[0] == 0
    assert run("screen", two, "exclude", "--reason", "off topic")[0] == 0
    code, out, _ = run("list", "--tag", "chapter 2", "--status", "read")
    assert code == 0
    assert "Graph neural networks" in out
    assert "1 paper(s)" in out
    _, out, _ = run("show", one)
    assert "用在 2.3" in out
    _, out, _ = run("list", "--decision", "exclude", "--json")
    assert '"off topic"' in out
    assert run("screen", two, "undo")[0] == 0
    assert _entry(library, ids["2"]).screening == ()
    assert run("tag", one, "--remove", "chapter 2")[0] == 0
    assert run("tag", one)[0] == 2
    assert run("show", "999")[0] == 2


def test_cli_asks_before_deleting(library, run, monkeypatch):
    one = str(_ids(library)["1"])
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")
    assert run("delete", one)[0] == 1
    assert len(library) == 3

    def no_terminal(_prompt):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_terminal)
    assert run("delete", one)[0] == 1
    assert run("delete", one, "--yes")[0] == 0
    assert len(library) == 2


def test_cli_finds_and_merges_duplicates(library, run):
    library.add_papers([_paper("1b", "Graph Neural Networks for Molecules.", doi="10.1/a2")])
    ids = _ids(library)
    _, out, _ = run("duplicates")
    assert f"merge {ids['1']} {ids['1b']}" in out
    assert run("merge", str(ids["1"]), str(ids["1b"]))[0] == 0
    assert run("merge", str(ids["1"]))[0] == 2
    assert len(library) == 3


def test_cli_saved_searches(library, run, monkeypatch):
    assert run("save-search", "g", "graphs", "--source", "arxiv, dblp", "--max", "5")[0] == 0
    assert library.saved_search("g").query.sources == ("arxiv", "dblp")

    async def fake(query, **_kwargs):
        return PaperCollection(query=query, papers=(_paper("n", "New one", doi="10.1/n"),))

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", fake)
    _, out, _ = run("run-search", "g")
    assert "New one" in out
    assert "1 new of 1 found" in out
    _, out, _ = run("searches")
    assert "1 new" in out
    assert run("delete-search", "g")[0] == 0
    assert run("run-search", "g")[0] == 2


def test_cli_prisma(library, run, tmp_path):
    target = tmp_path / "flow.svg"
    code, out, _ = run("prisma", "--svg", str(target))
    assert code == 0
    assert '"unique": 3' in out
    assert target.read_text(encoding="utf-8").startswith("<svg")
    assert run("prisma", "--svg", str(tmp_path))[0] == 2


def test_cli_names_a_missing_library(tmp_path, capsys):
    assert cli.main(["library", str(tmp_path / "none.db"), "list"]) == 2
    assert "no library" in capsys.readouterr().err
    assert not (tmp_path / "none.db").exists()


# --- what used to lose or mislabel records ------------------------------------------------


def _run_of(papers, *stats) -> PaperCollection:
    return PaperCollection(
        query=Query("x", ("arxiv",)), papers=tuple(papers),
        diagnostics=SearchDiagnostics(source_stats=stats),
    )


def _studies(count: int) -> list[Paper]:
    return [
        _paper(str(i), f"Study number {i} about topic {i * 7}", doi=f"10.1000/{i}")
        for i in range(count)
    ]


def test_prisma_does_not_call_a_cut_off_record_a_duplicate(tmp_path):
    with Library(tmp_path / "p.db") as library:
        # 40 records, 30 distinct papers, of which the result limit kept 25.
        library.add_collection(_run_of(_studies(25), _stat("arxiv", 25, 25), _stat("dblp", 15, 5)))
        flow = prisma_flow(library)
        assert (flow.duplicates_removed, flow.removed_other, flow.unique) == (10, 5, 25)
        assert flow.to_dict()["removed_other"] == 5
        assert "Records removed for other reasons (n = 5)" in prisma_svg(flow)
        # The same search again finds nothing new: those 25 are duplicates.
        library.add_collection(_run_of(_studies(25), _stat("arxiv", 25, 25), _stat("dblp", 15, 5)))
        flow = prisma_flow(library)
        assert (flow.duplicates_removed, flow.removed_other, flow.unique) == (45, 10, 25)
        library.delete([library.entries()[0].paper_id])
        flow = prisma_flow(library)
        assert (flow.duplicates_removed, flow.unique) == (44, 24)
    total = sum(flow.identified.values())
    assert total == flow.duplicates_removed + flow.removed_other + flow.unique


def test_prisma_counts_papers_found_along_citation_links(tmp_path):
    with Library(tmp_path / "p.db") as library:
        library.add_collection(_run_of(_studies(12), _stat("arxiv", 10, 9)))
        flow = prisma_flow(library)
    assert flow.identified == {"arxiv": 10, "snowball": 3}
    assert (flow.duplicates_removed, flow.removed_other, flow.unique) == (1, 0, 12)


def test_prisma_counts_a_merge_by_hand_as_a_duplicate(tmp_path):
    with Library(tmp_path / "p.db") as library:
        library.add_collection(_run_of(_studies(5), _stat("arxiv", 3, 3), _stat("dblp", 2, 2)))
        first, second, *_rest = [e.paper_id for e in library.entries()]
        library.merge(first, [second])
        flow = prisma_flow(library)
    assert (flow.duplicates_removed, flow.removed_other, flow.unique) == (1, 0, 4)


def test_prisma_leaves_the_box_out_when_nothing_was_cut(library):
    assert "other reasons" not in prisma_svg(prisma_flow(library))


def test_chinese_papers_are_recognised_when_imported_again(library):
    papers = [
        _paper("c1", "深度學習於影像辨識之研究", authors=("王小明",), year=2020),
        _paper("c2", "自然語言處理綜述", authors=("王小明",), year=2020),
    ]
    assert library.add_papers(papers).added == 2
    again = library.add_papers(papers)
    assert (again.added, again.merged) == (0, 2)


def test_chinese_titles_are_compared_too(library):
    library.add_papers([
        _paper("c1", "深度學習於醫學影像辨識之應用研究", authors=("王小明",)),
        _paper("c2", "深度學習於醫學影像辨識的應用研究", authors=("王小明",)),
        _paper("c3", "圖書館服務品質之調查", authors=("李四",)),
    ])
    ids = _ids(library)
    assert (ids["c1"], ids["c2"]) in library.duplicate_candidates()
    assert all(ids["c3"] not in group for group in library.duplicate_candidates())


def test_a_word_only_one_title_has_does_not_hide_the_pair(library):
    # Each title's rarest word was its own, so only papers that shared it were
    # compared, and these two never were.
    words = "graph neural networks for molecular property prediction with message passing and edge"
    library.add_papers([
        _paper("x", f"{words} attention", doi=None),
        _paper("y", f"{words} transformers", doi=None),
    ])
    ids = _ids(library)
    assert (ids["x"], ids["y"]) in library.duplicate_candidates()


def test_imported_papers_are_found_under_their_stored_record(library, run, tmp_path):
    ids = _ids(library)
    # The journal version, merged into the preprint, keeps the preprint's DOI.
    journal = _paper("j", "Quite another title", doi="10.5555/journal")
    library.add_papers([journal])
    library.merge(ids["1"], [_ids(library)["j"]])
    assert library.ids_of([journal, journal]) == [ids["1"]]
    file = tmp_path / "z.bib"
    file.write_text(
        "@article{j, title={Quite another title}, doi={10.5555/journal}}", encoding="utf-8"
    )
    assert run("import", str(file), "--tag", "thesis")[0] == 0
    assert _entry(library, ids["1"]).tags == ("thesis",)


def test_joining_two_stored_papers_keeps_the_richer_summary(tmp_path):
    rich = PaperSummary(language="en", core_observation="It works.")
    flat = PaperSummary(language="en", motivation=("why",))
    with Library(tmp_path / "s.db") as library:
        library.add_papers([
            _paper("a", "One name of it", doi="10.1000/a", summary=flat, citation_count=1),
            _paper("b", "Another name", arxiv_id="2401.00001", summary=rich, citation_count=9),
        ])
        # Carries the DOI of one and the arXiv id of the other.
        library.add_papers([
            _paper("c", "One name of it", doi="10.1000/a", arxiv_id="2401.00001")
        ])
        entry = library.entries()[0]
        assert len(library) == 1
    assert entry.paper.summary == rich
    assert entry.paper.citation_count == 9


def test_saved_searches_that_differ_in_an_accented_letter(library):
    library.save_search("École", _QUERY)
    library.save_search("école", Query("other", ("dblp",)))
    assert library.saved_search("école").query.keywords == "other"
    assert library.saved_search("École").query == _QUERY
    library.delete_saved_search("école")
    assert library.saved_search("ÉCOLE").name == "École"


def test_two_processes_can_upgrade_a_library_at_once(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    with monkeypatch.context() as patch:
        patch.setattr(schema, "SCHEMA_VERSION", 1)
        first = sqlite3.connect(path, isolation_level=None)
        schema.prepare(first, str(path))
    original, upgraded = schema.transaction, []

    def after_another_process(conn):
        if not upgraded:
            upgraded.append(True)
            second = sqlite3.connect(path, isolation_level=None)
            schema.prepare(second, str(path))
            second.close()
        return original(conn)

    monkeypatch.setattr(schema, "transaction", after_another_process)
    assert schema.prepare(first, str(path)) == schema.SCHEMA_VERSION
    first.close()
    with Library(path) as library:
        assert library.tags() == {}


def test_the_diagram_is_only_drawn_into_an_svg(library, run, tmp_path):
    target = tmp_path / "thesis.db"
    target.write_text("precious", encoding="utf-8")
    code, _out, err = run("prisma", "--svg", str(target))
    assert code == 2
    assert ".svg" in err
    assert target.read_text(encoding="utf-8") == "precious"


def test_papers_get_the_identity_keys_of_today(tmp_path):
    # A Chinese title was stored under a key of its ASCII letters, so the same
    # file imported again was a second paper.
    path = tmp_path / "old.db"
    paper = _paper("7", "基於深度學習之程式碼審查", url="https://example.org/7")
    with Library(path) as library:
        library.add_papers([paper])
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("DELETE FROM identity_keys")
    conn.execute("INSERT INTO identity_keys (key, paper_id) VALUES ('hash:old', 1)")
    conn.execute(
        "INSERT INTO papers (record, title, year, first_seen, last_seen) "
        "VALUES ('{}', 'unreadable', 2000, 'a', 'a')"
    )
    conn.execute("PRAGMA user_version = 2")
    conn.close()
    with Library(path, create=False) as library:
        assert library.schema_version == schema.SCHEMA_VERSION
        assert library.add_papers([paper]).merged == 1
        keys = {row[0] for row in library._conn.execute("SELECT key FROM identity_keys")}
        assert {"hash:old", paper.dedup_key()} <= keys


def test_several_edits_are_made_together_or_not_at_all(library):
    paper_id = library.entries()[0].paper_id
    with pytest.raises(ValueError, match="reading status"), library.together():
        library.add_tags([paper_id], ["chapter 2"])
        library.set_reading_status([paper_id], "raed")
    assert library.tags() == {}
    with library.together():
        library.add_tags([paper_id], ["chapter 2"])
        library.set_reading_status([paper_id], "read")
    assert dict(library.tags()) == {"chapter 2": 1}

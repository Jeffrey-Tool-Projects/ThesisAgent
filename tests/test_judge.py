"""Judging search results: what is shown, what is kept, and that nothing is lost."""
from __future__ import annotations

import json

import pytest

from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Paper, PaperCollection
from thesisagents.evaluation import judge
from thesisagents.evaluation.search_quality import evaluate_benchmark


def _paper(i: int, **fields) -> Paper:
    defaults = {
        "source": "arxiv", "source_id": str(i), "title": f"Title {i}", "authors": ("A B",),
        "year": 2020, "venue": None, "abstract": f"Abstract {i}", "url": "", "doi": f"10.1/{i}",
    }
    return Paper(**{**defaults, **fields})


async def _collected(*papers: Paper, payload=None):
    async def search(query):
        return PaperCollection(query=query, papers=papers)

    return await judge.collect(
        payload if payload is not None else {}, ["LLM Code  Review"], sources=("arxiv",),
        max_results=5, search=search,
    )


@pytest.mark.parametrize(("paper", "expected"), [
    (_paper(1, doi="10.1/ABC "), "10.1/abc"),
    (_paper(1, doi=None, arxiv_id="2401.00001v2"), "arxiv:2401.00001"),
])
def test_identifiers(paper, expected):
    assert judge.paper_identifier(paper) == expected


def test_a_paper_without_identifiers_still_has_one():
    assert judge.paper_identifier(_paper(1, doi=None)).startswith("hash:")


async def test_collecting_keeps_the_ranking_and_the_papers():
    payload = await _collected(_paper(2), _paper(1), _paper(2))
    query = payload["queries"][0]
    assert (query["id"], query["keywords"]) == ("llm-code-review", "LLM Code Review")
    assert query["retrieved"] == ["10.1/2", "10.1/1"]
    assert payload["papers"]["10.1/1"]["abstract"] == "Abstract 1"


async def test_collecting_again_keeps_the_judgements():
    payload = await _collected(_paper(1), _paper(2))
    payload["queries"][0]["relevance"]["10.1/1"] = 2
    payload = await _collected(_paper(3), _paper(1), payload=payload)
    assert len(payload["queries"]) == 1
    assert payload["queries"][0]["relevance"] == {"10.1/1": 2}
    assert [i for _q, i in judge.unjudged(payload)] == ["10.1/3"]


async def test_papers_are_shuffled_and_stay_in_order_while_judging():
    payload = await _collected(*(_paper(i) for i in range(12)))
    first = [i for _q, i in judge.unjudged(payload)]
    assert first != payload["queries"][0]["retrieved"]
    assert first == [i for _q, i in judge.unjudged(payload)]
    payload["queries"][0]["relevance"][first[0]] = 1
    assert [i for _q, i in judge.unjudged(payload)] == first[1:]
    assert [i for _q, i in judge.unjudged(payload, seed=1)] != first[1:]


async def _graded(*answers: str):
    payload = await _collected(_paper(1), _paper(2), _paper(3))
    shown, saved = [], []
    given = iter(answers)
    count = judge.grade(
        payload, ask=lambda _prompt: next(given), show=shown.append,
        save=lambda p: saved.append(json.dumps(p)),
    )
    return payload["queries"][0]["relevance"], count, shown, saved


async def test_grades_are_saved_one_by_one():
    relevance, count, shown, saved = await _graded("2", "0", "1")
    assert sorted(relevance.values()) == [0, 1, 2]
    assert (count, len(saved)) == (3, 3)
    assert "[1/3]" in shown[0]
    # Neither rank nor source, which would bias the judge.
    assert "arxiv" not in shown[0]


async def test_skipping_quitting_and_nonsense():
    relevance, count, shown, _saved = await _graded("s", "maybe", "", "1", "q")
    assert (len(relevance), count) == (1, 1)
    assert shown[1] == shown[2] == shown[3]


async def test_a_grade_can_be_taken_back():
    relevance, count, shown, saved = await _graded("u", "0", "u", "2", "q")
    assert list(relevance.values()) == [2]
    assert count == 1
    assert len(saved) == 3
    assert shown[0] == shown[1] == shown[3]


async def test_the_file_is_what_the_evaluator_reads():
    payload = await _collected(_paper(1), _paper(2))
    payload["queries"][0]["relevance"] = {"10.1/1": 2, "10.1/2": 0}
    assert evaluate_benchmark(payload, cutoff=2)["macro"]["precision"] == pytest.approx(0.5)


# --- files ------------------------------------------------------------------------------


def test_a_file_survives_the_round_trip(tmp_path):
    path = tmp_path / "b.json"
    assert judge.load(path, must_exist=False) == {"queries": [], "papers": {}}
    payload = {"queries": [{"id": "q", "retrieved": ["a"], "relevance": {"a": 1}}], "papers": {}}
    judge.store(path, payload)
    assert judge.load(path, must_exist=True) == payload
    assert list(tmp_path.glob("*.saving")) == []


@pytest.mark.parametrize("content", [
    "not json", "[]", '{"queries": [{"id": "q"}]}',
    '{"queries": [{"id": "q", "retrieved": [], "relevance": ["a"]}]}',
])
def test_a_file_that_is_no_benchmark_is_refused(tmp_path, content):
    path = tmp_path / "b.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ThesisAgentsError, match="not a benchmark file"):
        judge.load(path, must_exist=True)


def test_command_line(tmp_path, monkeypatch, capsys):
    async def search(query, **_kwargs):
        return PaperCollection(query=query, papers=(_paper(1),))

    monkeypatch.setattr("thesisagents.core.pipeline.run_search", search)
    queries, bench = tmp_path / "q.txt", tmp_path / "b.json"
    queries.write_text("# comment\ngraphs\n\n", encoding="utf-8")
    assert judge.main(["collect", str(bench), "--queries", str(queries)]) == 0
    assert "1 papers to grade" in capsys.readouterr().out
    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    assert judge.main(["grade", str(bench)]) == 0
    assert "1 graded, 0 to go" in capsys.readouterr().out

    def no_terminal(_prompt):
        raise EOFError

    queries.write_text("other\n", encoding="utf-8")
    judge.main(["collect", str(bench), "--queries", str(queries)])
    monkeypatch.setattr("builtins.input", no_terminal)
    assert judge.main(["grade", str(bench)]) == 2
    assert judge.main(["grade", str(tmp_path / "none.json")]) == 2

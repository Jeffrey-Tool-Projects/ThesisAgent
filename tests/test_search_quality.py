"""Tests for the offline search-quality benchmark evaluator."""

from __future__ import annotations

import json
import math

import pytest

from thesisagents.evaluation.search_quality import evaluate_benchmark, evaluate_query, main


def test_evaluate_query_reports_precision_recall_and_ndcg():
    metrics = evaluate_query(
        ["cornerstone", "noise", "related"],
        {"cornerstone": 2, "related": 1, "missed": 1},
        cutoff=3,
    )
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert 0 < metrics["ndcg"] < 1


def test_a_repeated_paper_does_not_let_rank_three_into_the_top_two():
    """``[A, A, B]`` at cutoff 2 covers one relevant paper, not two: the repeat
    keeps its place and counts zero, so B at rank 3 cannot fill the top two."""
    metrics = evaluate_query(["a", "a", "b"], {"a": 1, "b": 1}, cutoff=2)
    assert metrics["hits"] == 1
    assert metrics["retrieved"] == 2
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["ndcg"] == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_a_repeated_paper_never_lifts_recall_past_one():
    metrics = evaluate_query(["a", "a", "a"], {"a": 2}, cutoff=3)
    assert metrics["hits"] == 1
    assert metrics["recall"] == pytest.approx(1.0)
    assert metrics["ndcg"] == pytest.approx(1.0)


def test_evaluate_benchmark_accepts_binary_and_graded_qrels():
    report = evaluate_benchmark(
        {
            "queries": [
                {"id": "q1", "retrieved": ["a", "x"], "relevance": ["a"]},
                {"id": "q2", "retrieved": ["b", "c"], "relevance": {"b": 2}},
            ]
        },
        cutoff=2,
    )
    assert report["query_count"] == 2
    assert report["macro"]["precision"] == pytest.approx(0.5)
    assert report["macro"]["recall"] == pytest.approx(1.0)


def test_evaluate_benchmark_rejects_missing_queries():
    with pytest.raises(ValueError, match="queries"):
        evaluate_benchmark({})


def test_evaluate_query_rejects_zero_cutoff():
    with pytest.raises(ValueError, match="cutoff"):
        evaluate_query([], {}, cutoff=0)


def test_main_reads_a_benchmark_under_the_root(tmp_path, capsys):
    benchmark = tmp_path / "bench.json"
    benchmark.write_text(
        json.dumps({"queries": [{"id": "q1", "retrieved": ["a"], "relevance": ["a"]}]}),
        encoding="utf-8",
    )
    assert main(["bench.json", "--root", str(tmp_path), "--cutoff", "1"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["query_count"] == 1
    assert report["macro"]["precision"] == pytest.approx(1.0)


@pytest.mark.parametrize("argument", ["../outside.json", "/etc/passwd", "C:/Windows/win.ini"])
def test_main_refuses_a_path_outside_the_root(tmp_path, argument):
    """The path comes off a command line, so it is validated before anything is read."""
    with pytest.raises(ValueError):
        main([argument, "--root", str(tmp_path)])

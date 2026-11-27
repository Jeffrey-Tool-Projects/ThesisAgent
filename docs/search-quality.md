# Search-quality benchmark

Unit tests prove that parsers and ranking rules behave as designed. This
offline benchmark answers a different question: whether ranked results are
actually relevant to representative research queries.

Create a UTF-8 JSON file with stable paper identifiers. DOI is preferred,
followed by arXiv ID. Grade 2 means a cornerstone paper, grade 1 means relevant,
and omitted IDs are treated as non-relevant.

```json
{
  "queries": [
    {
      "id": "llm-code-review",
      "retrieved": ["10.1000/example", "arxiv:2501.00001"],
      "relevance": {
        "10.1000/example": 2,
        "arxiv:2501.00001": 1
      }
    }
  ]
}
```

`thesisagents.evaluation.judge` makes such a file. It runs the queries once
and then shows one paper at a time to grade, in random order and without
rank or source, because a judge who sees rank 1 tends to agree with it:

```powershell
py -m thesisagents.evaluation.judge collect benchmark.json --queries queries.txt --source arxiv,dblp
py -m thesisagents.evaluation.judge grade benchmark.json
```

`queries.txt` holds one query per line. Every grade is saved at once, `s`
skips a paper, `u` takes the last grade back, `q` stops, and `grade` goes on
where it stopped. Running `collect` again refreshes the ranking and keeps
the judgements.

Run the evaluator without network access:

```powershell
py -m thesisagents.evaluation.search_quality benchmark.json --cutoff 10
```

The benchmark path is read relative to `--root`, which defaults to the current
directory; absolute paths and `..` segments are refused, like every other
user-supplied path in this project. A benchmark kept elsewhere is reached by
naming its directory:

```powershell
py -m thesisagents.evaluation.search_quality bench.json --root D:\data\qrels
```

The report includes per-query and macro Precision@K, Recall@K and nDCG@K.

`retrieved` is read as a ranking with its positions kept. A paper listed a
second time keeps its place in the top K and counts zero there, as a
non-relevant result would. So `["a", "a", "b"]` at `--cutoff 2` scores one hit
(precision 0.5), because only `a` is in the top two places. The rank 3 paper
`b` does not move up to fill the place of the repeat, and a repeat can never
push recall past 1. The `collect` command already writes each paper once, so
this matters for a benchmark file made by hand or by another tool.
Judgements should be reviewed by a domain reader, committed separately from
retrieved results, and updated only when the relevance standard changes.

"""Regression tests for two overflows the inspector reported (``progress.md``
#11 and #16), reproduced with the inputs that showed them and checked with
the project's own overflow inspector (``thesisagents/exporters/overflow.py``).
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters.overflow import check_pptx
from thesisagents.exporters.pptx import (
    PptxExporter,
    _callout_height_in,
    _content_meta_height_in,
)

#: The 112-character title from the 2026-10-08 search smoke.
LONG_TITLE = (
    "Energy-Gated Sparse Attention for Long-Context Transformers: Scaling Linear-Time "
    "Inference Across Heterogeneous Hardware"
)
#: A research question of about 170 characters, as in the 2026-10-08 review.
LONG_QUESTION = (
    "Can a retrieval-augmented transformer keep its answer accuracy on long multi-document "
    "questions while cutting inference latency by half on commodity GPUs without retraining?"
)


def _export(tmp_path: Path, paper: Paper, stem: str) -> Path:
    collection = PaperCollection(Query("overflow", ("arxiv",)), (paper,))
    options = ExportOptions(
        formats=("pptx",), out_dir=str(tmp_path), filename_stem=stem,
        verify_identifiers=False,
    )
    return PptxExporter().export(collection, options)


def _describe(violations) -> str:
    return "\n".join(
        f"slide {v.slide} {v.shape}: {v.kind} {v.rendered_in}\" vs {v.limit_in}\""
        for v in violations
    )


# --- #11 the lightweight meta line ------------------------------------------------


def test_meta_height_grows_to_two_lines_then_shrinks_to_fit():
    short, short_overflow = _content_meta_height_in("A short title · Paper 1 of 3")
    long, long_overflow = _content_meta_height_in(f"{LONG_TITLE} · Paper 1 of 3")
    huge, huge_overflow = _content_meta_height_in(f"{LONG_TITLE * 3} · Paper 1 of 3")
    assert (short, short_overflow) == (0.5, False)
    assert long > 0.5
    assert not long_overflow
    assert huge == long                            # capped at two lines
    assert huge_overflow                           # and shrink-to-fit


def test_a_long_title_no_longer_overflows_the_lightweight_deck(tmp_path):
    paper = Paper(
        source="arxiv", source_id="2410.00001", title=LONG_TITLE, authors=("Ada Author",),
        year=2024, venue=None,
        abstract=(
            "We propose energy-gated sparse attention. It keeps the most informative "
            "tokens. It scales linearly with context length. Experiments on three "
            "benchmarks show a two-fold speed-up with no accuracy loss."
        ),
        url="https://example.org/x",
    )
    deck = _export(tmp_path, paper, "long-title")
    violations = check_pptx(deck)
    assert violations == [], _describe(violations)
    metas = [
        shape for slide in Presentation(str(deck)).slides for shape in slide.shapes
        if shape.name == "meta" and "Paper 1 of 1" in shape.text_frame.text
    ]
    assert metas, "the content slides carry the meta line"
    assert all(shape.height.inches > 0.5 for shape in metas)


# --- #16 the research-question callout --------------------------------------------


def _rich(question: str) -> Paper:
    summary = PaperSummary(
        language="en",
        pain_points=(
            ("Long inputs are slow", ("Attention is quadratic", "Memory grows fast")),
            ("Accuracy drops", ("Retrieval misses context", "Answers drift")),
        ),
        research_question=question,
        model="test",
    )
    return Paper(
        source="local", source_id="t", title="A Thesis", authors=("Ada",), year=2026,
        venue=None, abstract="", url="", summary=summary,
    )


def _callouts(deck: Path) -> list[tuple[int, float, float]]:
    """(slide number, top, height) of every research-question callout."""
    return [
        (number, shape.top.inches, shape.height.inches)
        for number, slide in enumerate(Presentation(str(deck)).slides, start=1)
        for shape in slide.shapes
        if shape.name == "rq_box"
    ]


def test_callout_height_estimate_tracks_the_text():
    assert _callout_height_in("Does it scale?") < 0.8
    assert _callout_height_in(LONG_QUESTION) > 0.8


def test_a_short_question_stays_under_the_pain_points(tmp_path):
    deck = _export(tmp_path, _rich("Does sparse attention keep accuracy?"), "short-rq")
    assert check_pptx(deck) == []
    (_, top, height), = _callouts(deck)
    assert (round(top, 2), round(height, 2)) == (6.2, 0.8)


def test_a_long_question_moves_to_its_own_slide_and_fits(tmp_path):
    deck = _export(tmp_path, _rich(LONG_QUESTION), "long-rq")
    violations = check_pptx(deck)
    assert violations == [], _describe(violations)
    (_, top, height), = _callouts(deck)              # shown once, not lost, not twice
    assert round(top, 2) == 2.5
    assert height >= 2.0


# --- the overview slide's authors block (found by the U-20261119-10 DoD smoke) -------


def test_a_long_author_list_fits_the_overview_slide(tmp_path):
    """Attention Is All You Need: eight authors wrapped the overview's fixed
    1.1" meta box to 1.2"."""
    paper = Paper(
        source="arxiv", source_id="1706.03762", title="Attention Is All You Need",
        authors=("Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit",
                 "Llion Jones", "Aidan N. Gomez", "Lukasz Kaiser", "Illia Polosukhin"),
        year=2017, venue="Advances in Neural Information Processing Systems 30 (NeurIPS 2017)",
        abstract="The dominant sequence transduction models are based on recurrent networks.",
        url="https://arxiv.org/abs/1706.03762", doi="10.48550/arXiv.1706.03762",
        arxiv_id="1706.03762", pdf_url="https://arxiv.org/pdf/1706.03762", citation_count=100000,
    )
    deck = _export(tmp_path, paper, "eight-authors")
    violations = check_pptx(deck)
    assert violations == [], _describe(violations)

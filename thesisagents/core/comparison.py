"""The comparison table of a literature review (thesis section 2.3).

One row per paper: author, method, strengths, weaknesses, the columns
``paper_rule`` asks for. Every cell is taken from the paper's own summary.
What the summary does not say stays empty, because a plausible invention in
such a table is research misconduct.

Example::

    rows = comparison_rows(collection.papers)
    rows[0].weaknesses        # ("Evaluated on one data set only.",)
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from thesisagents.core.models import Paper, PaperSummary

#: How many statements of a summary one cell quotes.
_PER_CELL = 3


@dataclass(frozen=True, slots=True)
class ComparisonRow:
    """One paper's row. The author cell is written by the exporter, which
    knows the citation style."""

    paper: Paper
    method: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    weaknesses: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether the summary gave nothing to compare."""
        return not (self.method or self.strengths or self.weaknesses)


def comparison_rows(papers: Iterable[Paper]) -> list[ComparisonRow]:
    """A row per paper, in the given order, papers without a summary included."""
    return [_row(paper) for paper in papers]


def _row(paper: Paper) -> ComparisonRow:
    summary = paper.summary
    if summary is None:
        return ComparisonRow(paper)
    return ComparisonRow(
        paper,
        method=_method(summary),
        strengths=_strengths(summary),
        weaknesses=summary.limitations[:_PER_CELL],
    )


def _method(summary: PaperSummary) -> tuple[str, ...]:
    """The named techniques, else the method headings, else the method bullets."""
    if summary.technique_table:
        return tuple(name for name, _role in summary.technique_table[:_PER_CELL])
    if summary.method_sections:
        return tuple(heading for heading, _bullets in summary.method_sections[:_PER_CELL])
    return summary.method[:_PER_CELL]


def _strengths(summary: PaperSummary) -> tuple[str, ...]:
    """Measured results first, then contributions."""
    measured = tuple(
        f"{label}: {value}" + (f" ({baseline})" if baseline else "")
        for label, value, baseline in summary.headline_metrics[:_PER_CELL]
    )
    claimed = tuple(heading for heading, _text in summary.contributions_detailed)
    return (measured + (claimed or summary.contributions or summary.results))[:_PER_CELL]

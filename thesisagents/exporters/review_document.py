"""What a literature review draft contains, before it is Word or LaTeX.

The draft covers thesis sections 2.3 (literature survey with its comparison
table) and 2.4 (what the papers say is missing) and the reference list. It
says nothing that is not in the papers' records and summaries: no invented
transitions, numbers or gaps. Connecting the papers and naming the gap this
thesis closes is the author's part.

Example::

    for block in review_blocks(collection, "en"):
        ...                      # Heading, Paragraph, Bullets, Table, References
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from thesisagents.core.comparison import comparison_rows, metric_statements
from thesisagents.core.models import Paper, PaperCollection, PaperSummary
from thesisagents.exporters.apa import CitationLabel, citation_labels
from thesisagents.exporters.i18n import normalise_language, t

_EMPTY_CELL = "—"
#: Languages whose sentences follow each other without a space.
_NO_SPACE = {"zh-tw", "zh-cn", "ja"}


@dataclass(frozen=True, slots=True)
class Cite:
    """A reference to a paper inside a text, by its index in the collection."""

    index: int


#: Text and citations in reading order.
Inline = tuple["str | Cite", ...]


@dataclass(frozen=True, slots=True)
class Heading:
    level: int
    text: str


@dataclass(frozen=True, slots=True)
class Paragraph:
    content: Inline


@dataclass(frozen=True, slots=True)
class Bullets:
    items: tuple[Inline, ...]


@dataclass(frozen=True, slots=True)
class Table:
    """``rows[0]`` is the header. A cell is a tuple of lines."""

    caption: str
    rows: tuple[tuple[Inline, ...], ...]


@dataclass(frozen=True, slots=True)
class References:
    heading: str


Block = Heading | Paragraph | Bullets | Table | References


def labels_of(collection: PaperCollection) -> list[CitationLabel]:
    return citation_labels(collection.papers)


def review_blocks(collection: PaperCollection, language: str) -> list[Block]:
    """The draft for ``collection`` with its headings in ``language``."""
    lang = normalise_language(language)
    papers = collection.papers
    blocks: list[Block] = [
        Heading(1, t(lang, "review_title", topic=collection.query.keywords)),
        Heading(2, "2.3 " + t(lang, "review_survey")),
        Paragraph((_intro(papers, lang),)),
    ]
    for number, (index, paper) in enumerate(enumerate(papers), 1):
        blocks.append(Heading(3, f"2.3.{number} {paper.title}"))
        blocks += _paper_paragraphs(index, paper, lang)
    if papers:
        blocks.append(_comparison(papers, lang))
    missing = _open_points(papers)
    if missing:
        blocks.append(Heading(2, "2.4 " + t(lang, "review_analysis")))
        blocks.append(Paragraph((t(lang, "review_gap_intro"),)))
        blocks.append(Bullets(tuple(missing)))
    blocks.append(References(t(lang, "references")))
    return blocks


def _intro(papers: Sequence[Paper], lang: str) -> str:
    years = sorted(paper.year for paper in papers if paper.year)
    if not years:
        return t(lang, "review_intro_plain", count=len(papers))
    if years[0] == years[-1]:
        return t(lang, "review_intro_year", count=len(papers), year=years[0])
    return t(lang, "review_intro_range", count=len(papers), first=years[0], last=years[-1])


def _paper_paragraphs(index: int, paper: Paper, lang: str) -> list[Block]:
    """The paper in its summary's words, else its abstract. Each paragraph is cited."""
    groups = _statements(paper.summary) if paper.summary else []
    if not groups and paper.abstract.strip():
        groups = [(paper.abstract.strip(),)]
    space = "" if lang in _NO_SPACE else " "
    return [
        Paragraph((space.join(_sentence(s, lang) for s in group) + " ", Cite(index)))
        for group in groups
    ]


def _statements(summary: PaperSummary) -> list[tuple[str, ...]]:
    """Why, how, what came out, what is missing: a paragraph for each."""
    why = summary.motivation or tuple(
        bullet for _heading, bullets in summary.pain_points for bullet in bullets
    )
    question = (summary.research_question,) if summary.research_question else ()
    how = summary.method or tuple(
        bullet for _heading, bullets in summary.method_sections for bullet in bullets
    )
    results = summary.results or metric_statements(summary)
    return [
        group
        for group in (why + question, how, results, summary.limitations)
        if group
    ]


def _sentence(text: str, lang: str) -> str:
    """``text`` with a full stop, unless it ends with one already."""
    text = text.strip()
    if text and text[-1] not in ".!?。！？…:：":
        text += "。" if lang in _NO_SPACE else "."
    return text


def _comparison(papers: Sequence[Paper], lang: str) -> Table:
    header: tuple[Inline, ...] = tuple(
        (t(lang, key),)
        for key in (
            "review_col_author", "review_col_method",
            "review_col_strengths", "review_col_weaknesses",
        )
    )
    rows: list[tuple[Inline, ...]] = [header]
    for index, row in enumerate(comparison_rows(papers)):
        rows.append((
            (Cite(index),), _cell(row.method), _cell(row.strengths), _cell(row.weaknesses),
        ))
    return Table(t(lang, "review_comparison"), tuple(rows))


def _cell(statements: Sequence[str]) -> Inline:
    return ("\n".join(statements),) if statements else (_EMPTY_CELL,)


def _open_points(papers: Sequence[Paper]) -> list[Inline]:
    """What the papers themselves call a limitation or leave for later."""
    points: list[Inline] = []
    for index, paper in enumerate(papers):
        if paper.summary is None:
            continue
        for text in (*paper.summary.limitations, *paper.summary.future_work):
            points.append((text.strip().rstrip("。.") + " ", Cite(index)))
    return points

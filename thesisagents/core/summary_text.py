"""A ``PaperSummary`` as editable text, and which thesis sections it covers.

Every field becomes a few lines that a person can edit, and the lines become
the field again. What text cannot hold (figures, tables copied from the
paper, the result blocks per research question) is carried over untouched.

The line formats, also shown to the user:

* a list: one statement per line,
* headed lists: ``# heading`` starts a group, the lines after it belong to it,
* columns: cells separated by `` | ``. A literal bar is written ``\\|``,
* a paragraph: all lines are joined.

Example::

    texts = summary_to_texts(summary)
    texts["limitations"] = "Only Java was studied."
    summary = texts_to_summary(summary, texts)
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Final

from thesisagents.core.models import Paper, PaperSummary

LINES: Final[str] = "lines"
HEADED: Final[str] = "headed"
COLUMNS: Final[str] = "columns"
PARAGRAPH: Final[str] = "paragraph"

#: The seven sections of ``paper_rule``, in order.
ABSTRACT, INTRODUCTION, LITERATURE, METHOD, EXPERIMENT, CONCLUSION, REFERENCES = SECTIONS = (
    "abstract", "introduction", "literature_review", "methodology", "experiment",
    "conclusion", "references",
)


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One editable field: its name in ``PaperSummary``, its line format, the
    thesis section it belongs to, and for columns how many (0 is any)."""

    name: str
    kind: str
    section: str
    columns: int = 0


FIELDS: Final[tuple[FieldSpec, ...]] = (
    FieldSpec("motivation", LINES, INTRODUCTION),
    FieldSpec("pain_points", HEADED, INTRODUCTION),
    FieldSpec("research_question", PARAGRAPH, INTRODUCTION),
    FieldSpec("research_questions", COLUMNS, INTRODUCTION, 2),
    FieldSpec("contributions", LINES, INTRODUCTION),
    FieldSpec("contributions_detailed", COLUMNS, INTRODUCTION, 2),
    FieldSpec("technique_table", COLUMNS, LITERATURE, 2),
    FieldSpec("literature_table", COLUMNS, LITERATURE),
    FieldSpec("method", LINES, METHOD),
    FieldSpec("method_sections", HEADED, METHOD),
    FieldSpec("system_flow", LINES, METHOD),
    FieldSpec("evaluation_sections", HEADED, EXPERIMENT),
    FieldSpec("results", LINES, EXPERIMENT),
    FieldSpec("headline_metrics", COLUMNS, EXPERIMENT, 3),
    FieldSpec("core_observation", PARAGRAPH, CONCLUSION),
    FieldSpec("limitations", LINES, CONCLUSION),
    FieldSpec("future_work", LINES, CONCLUSION),
    FieldSpec("takeaways", LINES, CONCLUSION),
)

_HEADING = re.compile(r"^#+\s*")
_BAR = re.compile(r"(?<!\\)\|")


def summary_to_texts(summary: PaperSummary | None) -> dict[str, str]:
    """Every editable field as text (empty for a paper without a summary)."""
    if summary is None:
        return {spec.name: "" for spec in FIELDS}
    return {spec.name: _to_text(spec, getattr(summary, spec.name)) for spec in FIELDS}


def texts_to_summary(
    base: PaperSummary | None, texts: Mapping[str, str], *, language: str = "en"
) -> PaperSummary:
    """The summary that ``texts`` describe, on top of ``base``.

    ``language`` is used only when there is no base.
    """
    values = {
        spec.name: _to_value(spec, texts[spec.name]) for spec in FIELDS if spec.name in texts
    }
    return replace(  # NOSONAR dataclasses.replace returns the same dataclass type
        base or PaperSummary(language=language), **values
    )


def _to_text(spec: FieldSpec, value: Any) -> str:
    if spec.kind == PARAGRAPH:
        return value
    if spec.kind == LINES:
        return "\n".join(value)
    if spec.kind == HEADED:
        return "\n".join(
            line
            for heading, bullets in value
            for line in (f"# {heading}".rstrip(), *bullets)
        )
    return "\n".join(" | ".join(cell.replace("|", "\\|") for cell in row) for row in value)


def _to_value(spec: FieldSpec, text: str) -> Any:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if spec.kind == PARAGRAPH:
        return " ".join(lines)
    if spec.kind == LINES:
        return tuple(lines)
    if spec.kind == HEADED:
        return _headed(lines)
    return tuple(_row(line, spec.columns) for line in lines)


def _headed(lines: list[str]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Groups of lines. Lines before the first heading get an empty one."""
    groups: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith("#"):
            groups.append((_HEADING.sub("", line), []))
        else:
            if not groups:
                groups.append(("", []))
            groups[-1][1].append(line)
    return tuple((heading, tuple(bullets)) for heading, bullets in groups)


def _row(line: str, columns: int) -> tuple[str, ...]:
    """Cells of a line. A fixed width is filled up, and what is over joins the last."""
    cells = [cell.strip() for cell in _BAR.split(line)]
    if columns:
        if len(cells) > columns:
            cells = [*cells[: columns - 1], " | ".join(cells[columns - 1 :])]
        cells += [""] * (columns - len(cells))
    return tuple(cell.replace("\\|", "|") for cell in cells)


def covered_sections(paper: Paper, summary: PaperSummary | None) -> dict[str, bool]:
    """For each thesis section whether there is something to write it from.

    The abstract comes from the paper, the references from its identifiers,
    the five body sections from the summary.
    """
    covered = dict.fromkeys(SECTIONS, False)
    covered[ABSTRACT] = bool(paper.abstract.strip())
    covered[REFERENCES] = bool(paper.doi or paper.arxiv_id or paper.url)
    if summary is not None:
        for spec in FIELDS:
            if getattr(summary, spec.name):
                covered[spec.section] = True
        if summary.rq_results or summary.paper_tables:
            covered[EXPERIMENT] = True
    return covered

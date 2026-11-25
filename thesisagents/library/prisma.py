"""The PRISMA flow of a library: how many papers were found, screened, included.

The counts follow the PRISMA 2020 flow diagram for database searches. They
come from what the library recorded: what each source returned in every run,
what merging left, and the screening decisions. Nothing is estimated, and a
paper without a decision is reported as still to be screened.

Example::

    flow = prisma_flow(library)
    Path("prisma.svg").write_text(prisma_svg(flow), encoding="utf-8")
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from html import escape
from typing import Any, Final

from thesisagents.library.curation import (
    DECISION_EXCLUDE,
    DECISION_INCLUDE,
    STAGE_ABSTRACT,
    STAGE_FULL_TEXT,
    screening_by_reason,
)


@dataclass(frozen=True, slots=True)
class PrismaFlow:
    """The numbers of the diagram.

    ``identified`` counts records per source over all runs, so a paper two
    sources returned counts twice there and once in ``unique``. ``awaiting``
    are papers without a title and abstract decision (or with "maybe"), and
    ``full_text_awaiting`` those that passed it and have no full-text one.
    """

    identified: Mapping[str, int]
    duplicates_removed: int
    unique: int
    awaiting: int
    excluded_abstract: int
    full_text: int
    full_text_awaiting: int
    excluded_full_text: int
    included: int
    reasons_abstract: Mapping[str, int] = field(default_factory=dict)
    reasons_full_text: Mapping[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identified": dict(self.identified),
            "identified_total": sum(self.identified.values()),
            "duplicates_removed": self.duplicates_removed,
            "unique": self.unique,
            "awaiting": self.awaiting,
            "excluded_abstract": self.excluded_abstract,
            "full_text": self.full_text,
            "full_text_awaiting": self.full_text_awaiting,
            "excluded_full_text": self.excluded_full_text,
            "included": self.included,
            "reasons_abstract": dict(self.reasons_abstract),
            "reasons_full_text": dict(self.reasons_full_text),
        }


def prisma_flow(library: Any) -> PrismaFlow:
    """Count the flow of ``library`` (a ``Library``)."""
    unique = len(library)
    identified = _identified(library)
    annotations = library.annotations()
    first = [a.decision(STAGE_ABSTRACT) for a in annotations.values()]
    second = [
        a.decision(STAGE_FULL_TEXT)
        for a in annotations.values()
        if a.decision(STAGE_ABSTRACT) == DECISION_INCLUDE
    ]
    excluded_abstract = first.count(DECISION_EXCLUDE)
    full_text = first.count(DECISION_INCLUDE)
    return PrismaFlow(
        identified=identified,
        # An import that names no source counts each paper once, so the sum
        # can only fall short when papers were deleted by hand.
        duplicates_removed=max(0, sum(identified.values()) - unique),
        unique=unique,
        awaiting=unique - excluded_abstract - full_text,
        excluded_abstract=excluded_abstract,
        full_text=full_text,
        full_text_awaiting=full_text
        - second.count(DECISION_EXCLUDE)
        - second.count(DECISION_INCLUDE),
        excluded_full_text=second.count(DECISION_EXCLUDE),
        included=second.count(DECISION_INCLUDE),
        reasons_abstract=screening_by_reason(annotations, STAGE_ABSTRACT),
        reasons_full_text=screening_by_reason(
            {
                paper_id: a
                for paper_id, a in annotations.items()
                if a.decision(STAGE_ABSTRACT) == DECISION_INCLUDE
            },
            STAGE_FULL_TEXT,
        ),
    )


def _identified(library: Any) -> dict[str, int]:
    """Records per source over all runs, from the runs' own statistics.

    A run without them (an import, an MCP ``library_add``) counts the papers
    it brought, under its kind.
    """
    counts: dict[str, int] = {}
    for run in library.runs():
        if run.source_stats:
            for stat in run.source_stats:
                name = str(stat.get("source", ""))
                counts[name] = counts.get(name, 0) + int(stat.get("returned") or 0)
        else:
            counts[run.kind] = counts.get(run.kind, 0) + run.papers
    return {name: counts[name] for name in sorted(counts) if counts[name]}


#: The wording of PRISMA 2020. A translation passes its own.
DEFAULT_LABELS: Final[Mapping[str, str]] = {
    "identified": "Records identified",
    "duplicates": "Duplicate records removed",
    "screened": "Records screened",
    "awaiting": "Awaiting screening",
    "excluded": "Records excluded",
    "full_text": "Reports assessed for eligibility",
    "full_text_awaiting": "Awaiting assessment",
    "excluded_full_text": "Reports excluded",
    "included": "Studies included in review",
    "no_reason": "no reason given",
}

_BOX_WIDTH, _GAP, _MARGIN, _LINE, _PADDING = 320, 60, 24, 20, 14
_SHOWN_REASONS = 6


def prisma_svg(flow: PrismaFlow, labels: Mapping[str, str] = DEFAULT_LABELS) -> str:
    """The flow as an SVG drawing, for a thesis or a slide.

    Four boxes run down the left, what left the flow at each step stands
    beside them. Text is escaped: reasons are what somebody typed.
    """
    total = sum(flow.identified.values())
    left = [
        [f"{labels['identified']} (n = {total})"]
        + [f"{name} (n = {count})" for name, count in flow.identified.items()],
        [f"{labels['screened']} (n = {flow.unique})"],
        [f"{labels['full_text']} (n = {flow.full_text})"],
        [f"{labels['included']} (n = {flow.included})"],
    ]
    if flow.awaiting:
        left[1].append(f"{labels['awaiting']} (n = {flow.awaiting})")
    if flow.full_text_awaiting:
        left[2].append(f"{labels['full_text_awaiting']} (n = {flow.full_text_awaiting})")
    right = [
        [f"{labels['duplicates']} (n = {flow.duplicates_removed})"],
        [f"{labels['excluded']} (n = {flow.excluded_abstract})"]
        + _reason_lines(flow.reasons_abstract, labels),
        [f"{labels['excluded_full_text']} (n = {flow.excluded_full_text})"]
        + _reason_lines(flow.reasons_full_text, labels),
        [],
    ]
    parts: list[str] = []
    top = _MARGIN
    for row, (main, side) in enumerate(zip(left, right, strict=True)):
        height = max(len(main), len(side)) * _LINE + 2 * _PADDING
        parts.append(_box(_MARGIN, top, height, main))
        if side:
            x = _MARGIN + _BOX_WIDTH + _GAP
            parts.append(_box(x, top, height, side))
            middle = top + height / 2
            parts.append(_arrow(_MARGIN + _BOX_WIDTH, middle, x, middle))
        if row < len(left) - 1:
            centre = _MARGIN + _BOX_WIDTH / 2
            parts.append(_arrow(centre, top + height, centre, top + height + _GAP / 1.5))
        top += height + _GAP / 1.5
    width = 2 * _MARGIN + 2 * _BOX_WIDTH + _GAP
    total_height = top - _GAP / 1.5 + _MARGIN
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height:.0f}" '
        f'viewBox="0 0 {width} {total_height:.0f}" font-family="sans-serif" font-size="13">'
        '<defs><marker id="tip" markerWidth="8" markerHeight="8" refX="7" refY="4" '
        'orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#1F3A66"/></marker></defs>'
        f'<rect width="{width}" height="{total_height:.0f}" fill="#FFFFFF"/>'
        + "".join(parts)
        + "</svg>\n"
    )


def _reason_lines(reasons: Mapping[str, int], labels: Mapping[str, str]) -> list[str]:
    shown = list(reasons.items())[:_SHOWN_REASONS]
    lines = [f"{reason or labels['no_reason']} (n = {count})" for reason, count in shown]
    rest = sum(reasons.values()) - sum(count for _reason, count in shown)
    if rest:
        lines.append(f"… (n = {rest})")
    return lines


def _box(x: float, y: float, height: float, lines: list[str]) -> str:
    text = "".join(
        f'<text x="{x + _PADDING:.0f}" y="{y + _PADDING + _LINE * index + 14:.0f}" '
        f'fill="#0F172A"{" font-weight=" + chr(34) + "bold" + chr(34) if index == 0 else ""}>'
        f"{escape(_shorten(line))}</text>"
        for index, line in enumerate(lines)
    )
    return (
        f'<rect x="{x:.0f}" y="{y:.0f}" width="{_BOX_WIDTH}" height="{height:.0f}" rx="6" '
        f'fill="#F4F6FA" stroke="#1F3A66"/>{text}'
    )


def _arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
        'stroke="#1F3A66" marker-end="url(#tip)"/>'
    )


def _shorten(line: str, limit: int = 42) -> str:
    """Fit one line into a box. CJK characters take the room of two."""
    width = 0
    for index, char in enumerate(line):
        width += 2 if ord(char) > 0x2E7F else 1
        if width > limit:
            # The count at the end matters more than the last words.
            tail = line[line.rfind(" (n = "):] if " (n = " in line else ""
            return line[: max(1, index - len(tail) - 1)].rstrip() + "…" + tail
    return line

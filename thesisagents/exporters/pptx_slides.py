"""One builder per kind of slide.

A builder adds its slide (or slides) to the presentation from a paper and its
summary. Which builders run, and in which order, is decided in ``pptx.py``.
"""

from __future__ import annotations

from collections.abc import Iterable

from pptx import Presentation
from pptx.enum.text import (
    MSO_ANCHOR,
    MSO_AUTO_SIZE,
    PP_ALIGN,
)
from pptx.util import (
    Emu,
    Inches,
    Pt,
)

from thesisagents.core.models import (
    Paper,
    PaperCollection,
    PaperSummary,
    RqResult,
)
from thesisagents.exporters.i18n import (
    strings_for,
    t,
)
from thesisagents.exporters.pptx_style import (
    _BODY_HEIGHT,
    _BODY_PT,
    _BODY_TOP,
    _BODY_WIDTH,
    _BRAND_DARK,
    _BRAND_GREY,
    _BRAND_HIGHLIGHT,
    _BULLET_MAX_CHARS,
    _BULLETS_PER_CELL_MAX,
    _COVER_META_HEIGHT,
    _COVER_META_PT,
    _COVER_META_TOP,
    _COVER_SUBTITLE_HEIGHT,
    _COVER_SUBTITLE_PT,
    _COVER_SUBTITLE_TOP,
    _COVER_TITLE_HEIGHT,
    _COVER_TITLE_PT,
    _COVER_TITLE_TOP,
    _DARK_BODY_TEXT,
    _EVALUATION_SECTIONS_PER_SLIDE,
    _FOOTER_PT,
    _HEADER_TITLE_FG,
    _MARGIN_X,
    _METHOD_SECTIONS_PER_SLIDE,
    _SECTION_TITLE_PT,
    _SUBHEAD_PT,
    _BuildContext,
)
from thesisagents.exporters.pptx_text import (
    _BODY_LINE_HEIGHT_IN,
    _CONTENT_BODY_BOTTOM,
    _CONTENT_META_GAP_IN,
    _CONTENT_META_PT,
    _TEXTBOX_SIDE_MARGIN_IN,
    _add_bullet_box,
    _add_footer,
    _add_kpi_lines,
    _add_paper_subtitle,
    _add_rq_callout,
    _add_stacked_section,
    _add_subsection,
    _add_table,
    _add_textbox,
    _cap_bullets,
    _clean,
    _content_meta_height_in,
    _equal_col_widths,
    _estimate_wrapped_lines,
    _render_multi_column,
    _sentences_to_bullets,
    _stacked_section_height_in,
    _strip_math_markup,
    _wrapped_box_height_in,
)
from thesisagents.exporters.template import (
    ROLE_CONTENT,
    ROLE_COVER,
    ROLE_QA,
    ROLE_REFERENCES,
    ROLE_SECTION,
    ROLE_TABLE,
)

# ---------------------------------------------------------------------------
# Per-paper dispatch
# ---------------------------------------------------------------------------


def _is_own_thesis(paper: Paper) -> bool:
    """True when ``paper`` is the candidate's OWN thesis, not a fetched paper.

    The boundary this guards: a borrowed paper needs a source/overview slide
    and a BibTeX cite-key (so the deck can attribute and cite it), whereas the
    candidate's own dissertation has neither a fetched source to credit nor a
    publisher DOI nor a cite-key worth advertising in their own defence deck.

    The ``thesis-deck-author`` flow builds the cover ``Paper`` with
    ``source="local"`` and *no* external provenance — empty ``url``, no
    ``doi`` / ``arxiv_id`` / ``pdf_url`` (see ``scripts/regen_thesis_demo.py``).
    The discriminator is deliberately that *combination*, not ``source``
    alone: the CLI ``--pdf`` flow also stamps ``source="local"`` when it
    analyses *someone else's* downloaded paper, but it always records a
    ``file://`` ``url`` (and often a real ``doi`` / ``arxiv_id`` from
    PDF-metadata extraction), so it stays a borrowed paper and keeps its
    source slide. Only an identifier-less local paper is the own-thesis cover.

    >>> own = Paper(source="local", source_id="t", title="My Thesis",
    ...             authors=("Me",), year=2026, venue="NTU", abstract="", url="")
    >>> _is_own_thesis(own)
    True
    """
    if paper.source != "local":
        return False
    return not (paper.url or paper.doi or paper.arxiv_id or paper.pdf_url)


# ---------------------------------------------------------------------------
# Slide builders — cover / agenda / divider / overview / refs / qa
# ---------------------------------------------------------------------------


def _add_cover_slide(
    prs: Presentation, layout, collection: PaperCollection, ctx: _BuildContext
) -> None:
    slide = layout.add_slide(prs, ROLE_COVER)
    title_text = _cover_title(collection, ctx)
    # Cover is a full-bleed navy panel (placed by _add_cover_left_band), so
    # the title is WHITE and the subtitle / meta are near-white — navy text
    # would vanish into the navy. These light colours are correct in BOTH
    # light (default) and dark modes because the cover stays navy either way.
    _add_textbox(
        slide, name="title", text=title_text,
        left=_MARGIN_X, top=_COVER_TITLE_TOP,
        width=_BODY_WIDTH, height=_COVER_TITLE_HEIGHT,
        font_pt=_COVER_TITLE_PT, bold=True, colour=_HEADER_TITLE_FG,
        align=PP_ALIGN.CENTER,
        shrink_to_fit=True,
    )
    if len(collection) == 1:
        subtitle = _english_subtitle(collection.papers[0])
        # Skip the subtitle when it would duplicate the title verbatim — this
        # is the common case for a monolingual English deck. The subtitle is
        # only useful when the cover title was localised and we want the
        # original paper title surfaced underneath.
        if subtitle and subtitle.strip() != title_text.strip():
            _add_textbox(
                slide, name="subtitle", text=subtitle,
                left=_MARGIN_X, top=_COVER_SUBTITLE_TOP,
                width=_BODY_WIDTH, height=_COVER_SUBTITLE_HEIGHT,
                font_pt=_COVER_SUBTITLE_PT, colour=_DARK_BODY_TEXT,
                align=PP_ALIGN.CENTER,
            )
    meta_text = _cover_subtitle(collection, ctx)
    _add_textbox(
        slide, name="meta", text=meta_text,
        left=_MARGIN_X, top=_COVER_META_TOP,
        width=_BODY_WIDTH, height=_COVER_META_HEIGHT,
        font_pt=_COVER_META_PT, colour=_DARK_BODY_TEXT,
        align=PP_ALIGN.CENTER,
    )


def _add_agenda_slide(
    prs: Presentation, layout, collection: PaperCollection, ctx: _BuildContext
) -> None:
    slide = _new_section_slide(prs, layout, t(ctx.language, "agenda"))
    bullets = [_agenda_line(i + 1, p, ctx) for i, p in enumerate(collection.papers)]
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=_BODY_TOP,
        width=_BODY_WIDTH, height=_BODY_HEIGHT,
        font_pt=_BODY_PT,
    )


def _add_section_divider(
    prs: Presentation, layout, index: int, total: int, paper: Paper, ctx: _BuildContext
) -> None:
    slide = layout.add_slide(prs, ROLE_SECTION)
    _add_textbox(
        slide, name="title",
        text=t(ctx.language, "paper_n_of_m", n=index, m=total),
        left=_MARGIN_X, top=Inches(2.6),
        width=_BODY_WIDTH, height=Inches(0.8),
        font_pt=_FOOTER_PT + 8, colour=_BRAND_GREY,
        align=PP_ALIGN.CENTER,
        shrink_to_fit=True,
    )
    _add_textbox(
        slide, name="meta",
        text=_clean(paper.title),
        left=_MARGIN_X, top=Inches(3.4),
        width=_BODY_WIDTH, height=Inches(2.4),
        font_pt=_SECTION_TITLE_PT + 2, bold=True, colour=_BRAND_DARK,
        align=PP_ALIGN.CENTER,
        shrink_to_fit=True,
    )


def _add_overview_slide(
    prs: Presentation, layout, paper: Paper, ctx: _BuildContext
) -> None:
    slide = _new_section_slide(
        prs, layout,
        _clean(paper.title),
        font_pt=_SECTION_TITLE_PT,
    )
    meta_text = _overview_meta(paper, ctx)
    # Authors, year / venue and source: a long author list wraps, and the
    # fixed 1.1" box overflowed for an eight-author paper (found by the DoD
    # smoke of U-20261119-10). Sized like the content-slide meta line; the
    # body list (at most six short lines) moves down and keeps its bottom.
    meta_height_in, meta_overflows = _wrapped_box_height_in(
        meta_text, font_pt=_OVERVIEW_META_PT,
        min_in=_OVERVIEW_META_MIN_IN, max_lines=_OVERVIEW_META_MAX_LINES,
    )
    _add_textbox(
        slide, name="meta", text=meta_text,
        left=_MARGIN_X, top=_BODY_TOP,
        width=_BODY_WIDTH, height=Inches(meta_height_in),
        font_pt=_OVERVIEW_META_PT, colour=_BRAND_GREY,
        shrink_to_fit=meta_overflows,
    )
    bullets = list(_overview_bullets(paper, ctx))
    body_top = _BODY_TOP + Inches(meta_height_in + _CONTENT_META_GAP_IN)
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=body_top,
        width=_BODY_WIDTH, height=_OVERVIEW_BODY_BOTTOM - body_top,
        font_pt=_BODY_PT,
    )


#: The overview slide's authors / year / source block.
_OVERVIEW_META_PT = _BODY_PT - 1
_OVERVIEW_META_MIN_IN = 1.1
_OVERVIEW_META_MAX_LINES = 6
#: Bottom edge of the overview body list, as before (top 2.7" + height 4.3").
_OVERVIEW_BODY_BOTTOM = Inches(7.0)


def _add_references_slide(
    prs: Presentation, layout, collection: PaperCollection, ctx: _BuildContext
) -> None:
    # A References section lists the works the deck *cites* (slide-deck-rules
    # §11), never the presenting paper itself — so the candidate's own thesis
    # is excluded. The rich PaperSummary carries no citation list, so a deck of
    # only the candidate's own thesis gets no references slide at all rather
    # than one that points back at the thesis (and shows an empty identifier).
    cited = [p for p in collection.papers if not _is_own_thesis(p)]
    if not cited:
        return
    slide = _new_section_slide(
        prs, layout, t(ctx.language, "references"), role=ROLE_REFERENCES
    )
    bullets = [_reference_line(i + 1, p, ctx) for i, p in enumerate(cited)]
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=_BODY_TOP,
        width=_BODY_WIDTH, height=_BODY_HEIGHT,
        font_pt=_BODY_PT - 2,
    )
    _add_footer(slide, t(ctx.language, "footer_references"))


def _add_qa_slide(prs: Presentation, layout, paper: Paper, ctx: _BuildContext) -> None:
    slide = layout.add_slide(prs, ROLE_QA)
    _add_textbox(
        slide, name="title", text=t(ctx.language, "section_qa"),
        left=_MARGIN_X, top=Inches(2.6),
        width=_BODY_WIDTH, height=Inches(1.2),
        font_pt=_COVER_TITLE_PT + 4, bold=True, colour=_BRAND_DARK,
        align=PP_ALIGN.CENTER,
        shrink_to_fit=True,
    )
    _add_textbox(
        slide, name="meta", text=t(ctx.language, "footer_qa"),
        left=_MARGIN_X, top=Inches(4.2),
        width=_BODY_WIDTH, height=Inches(0.8),
        font_pt=_COVER_SUBTITLE_PT, colour=_BRAND_GREY,
        align=PP_ALIGN.CENTER,
    )
    _ = paper  # unused but kept for symmetry with other slide builders


# ---------------------------------------------------------------------------
# Rich-tier slide builders
# ---------------------------------------------------------------------------


_PAIN_POINTS_PER_SLIDE = 4   # 2 columns × 2 rows


_PAIN_QUADRANT_HEIGHT_IN = 4.4   # vertical span the quadrant grid occupies


def _pain_points_per_slide(sections) -> int:
    """Cells per pain-point slide. The grid is normally 2×2, but when cells are
    text-heavy a 2×2 forces ``row_h = 4.4/2 = 2.2"`` (body ≈ 1.55") which a
    3-long-bullet cell overflows. Since the project never truncates text, the
    fix is to **paginate to one row of two** for tall content so each cell gets
    the full 4.4" — fewer cells per slide, never a clipped bullet. Short cells
    keep the 2×2 look. Estimates use the same wrap model as the overflow
    inspector so the result is one it agrees fits.
    """
    col_w_in = (_BODY_WIDTH.inches - 0.2) / 2
    max_cell = 0.0
    for _heading, bullets in sections:
        lines = sum(
            _estimate_wrapped_lines(
                _strip_math_markup("• " + b), width_in=col_w_in, font_pt=_BODY_PT
            )
            for b in _cap_bullets(bullets)
        )
        cell = 0.55 + lines * _BODY_LINE_HEIGHT_IN + 0.1  # subhead + body + gap
        max_cell = max(max_cell, cell)
    rows_fit = int(_PAIN_QUADRANT_HEIGHT_IN // max_cell) if max_cell else 2
    return max(2, min(_PAIN_POINTS_PER_SLIDE, rows_fit * 2))


def _add_pain_points_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """Pain-points quadrant slide, paginated by content height so a text-heavy
    cell never overflows. The research-question callout sits on the first slide
    only — subsequent pages are full quadrants of pain points."""
    title = t(ctx.language, "section_pain_points")
    sections = list(summary.pain_points)
    if not sections:
        return
    if _any_section_over_cell_cap(sections):
        # A pain point with more bullets than a quadrant cell holds would lose
        # content; render full-width paginated so every bullet survives. The RQ
        # callout (normally inline under the quadrant) gets its own lead slide so
        # it is still shown — _add_research_question_slide stays skipped because
        # pain_points is non-empty, so there is no duplicate.
        if summary.research_question:
            _add_research_question_lead_slide(prs, layout, paper, summary, ctx)
        _add_paginated_bullet_sections(
            prs, layout, paper, ctx, title=title, sections=tuple(sections),
        )
        return
    # The inline callout under the quadrant has 0.8" before the footer
    # guard. A question that needs more gets its own lead slide instead of
    # overflowing the box (progress #16), the same lead slide the over-cap
    # branch above uses, so it is never truncated.
    rq_on_own_slide = bool(summary.research_question) and (
        _callout_height_in(summary.research_question) > _INLINE_RQ_HEIGHT_IN
    )
    if rq_on_own_slide:
        _add_research_question_lead_slide(prs, layout, paper, summary, ctx)
    per_slide = _pain_points_per_slide(sections)
    chunks = [
        sections[i : i + per_slide]
        for i in range(0, len(sections), per_slide)
    ]
    for chunk_index, chunk in enumerate(chunks):
        chunk_title = title
        if len(chunks) > 1:
            chunk_title = f"{title} ({chunk_index + 1}/{len(chunks)})"
        slide = _new_section_slide(prs, layout, chunk_title)
        _add_paper_subtitle(slide, paper, ctx)
        _render_multi_column(
            slide,
            sections=tuple(chunk),
            left=_MARGIN_X, top=Inches(1.7),
            width=_BODY_WIDTH, height=Inches(4.4),
            columns=2,
            language=ctx.language,
        )
        if chunk_index == 0 and summary.research_question and not rq_on_own_slide:
            _add_rq_callout(
                slide, summary.research_question,
                left=_MARGIN_X, top=Inches(_INLINE_RQ_TOP_IN),
                width=_BODY_WIDTH, height=Inches(_INLINE_RQ_HEIGHT_IN),
            )


def _add_research_question_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    # If we already rendered the RQ inline on the pain-points slide, skip the
    # dedicated slide. Otherwise (no pain_points but a standalone RQ), give it
    # its own slide.
    if summary.pain_points:
        return
    _add_research_question_lead_slide(prs, layout, paper, summary, ctx)


#: The research-question callout under the pain-point grid: from 6.2" to the
#: 7.0" footer guard.
_INLINE_RQ_TOP_IN = 6.2
_INLINE_RQ_HEIGHT_IN = 0.8
#: The callout on a slide of its own starts at 2.5" and is at least 2.0" tall.
_LEAD_RQ_TOP_IN = 2.5
_LEAD_RQ_MIN_HEIGHT_IN = 2.0
#: ``_add_rq_callout``'s inner margins: 0.2" left and right, 0.1" top and bottom.
_CALLOUT_SIDE_MARGIN_IN = 0.2
_CALLOUT_VERTICAL_MARGINS_IN = 0.2


def _callout_height_in(text: str) -> float:
    """Height (inches) a research-question callout needs for ``text``.

    Same estimate as the overflow inspector (``_estimate_wrapped_lines``),
    at the callout's bold body size and its own 0.2" side margins. Used to
    decide whether a question fits the 0.8" inline box (``progress.md``
    #16: a 170-character question rendered at 0.95" there) and to size the
    lead-slide box.

    Example: a one-line question needs about 0.52", a three-line one 1.15".
    """
    plain = _strip_math_markup(" ".join((text or "").split()))
    # _estimate_wrapped_lines takes off the default 0.1" per side, the
    # callout's margins are 0.2", so hand it a width 0.2" narrower.
    extra_margin = 2 * (_CALLOUT_SIDE_MARGIN_IN - _TEXTBOX_SIDE_MARGIN_IN)
    width_in = Emu(_BODY_WIDTH).inches - extra_margin
    lines = _estimate_wrapped_lines(plain, width_in=width_in, font_pt=_BODY_PT)
    return lines * _BODY_LINE_HEIGHT_IN + _CALLOUT_VERTICAL_MARGINS_IN


def _add_research_question_lead_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """The research question on a slide of its own, in a box sized to it.

    At least 2.0" tall as before, taller when the question needs it, never
    past the 7.0" footer guard.
    """
    slide = _new_section_slide(prs, layout, t(ctx.language, "section_research_question"))
    _add_paper_subtitle(slide, paper, ctx)
    room = Emu(_FOOTER_GUARD).inches - _LEAD_RQ_TOP_IN
    needed = _callout_height_in(summary.research_question)
    height = min(room, max(_LEAD_RQ_MIN_HEIGHT_IN, needed))
    _add_rq_callout(
        slide, summary.research_question,
        left=_MARGIN_X, top=Inches(_LEAD_RQ_TOP_IN),
        width=_BODY_WIDTH, height=Inches(height),
    )


_MAX_STACKS_PER_SLIDE = 5   # standalone stacks slide
_FOOTER_GUARD = Inches(7.0)


def _add_contributions_detailed_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """Render contributions and KPI metrics on dedicated slides.

    We always split: even if the paper only has 2 contributions, the KPI
    metrics get their own slide so the layout is predictable and no slide
    has to balance "stacks + KPI" inside a fixed height.
    """
    if summary.contributions_detailed:
        _add_stacks_slide(
            prs, layout, paper, ctx,
            title=t(ctx.language, "section_contributions"),
            stacks=summary.contributions_detailed,
        )
    if summary.headline_metrics:
        _add_kpi_slide(prs, layout, paper, ctx, summary.headline_metrics)


_STACK_TOP_IN = 1.7   # first stacked section's Y on the slide


def _paginate_stacks(stack_list):
    """Pack (heading, body) sections into per-slide chunks by **height budget**
    so no chunk's cumulative height crosses the footer guard. ``(heading, body)``
    sections vary in body length, so a fixed count (``_MAX_STACKS_PER_SLIDE``)
    can't guarantee fit — a slide of four 3-line contributions overflows where
    four 1-line ones fit. ``_MAX_STACKS_PER_SLIDE`` is kept as an upper bound so
    a slide never crowds in more than the documented maximum even when tiny.
    """
    budget = _FOOTER_GUARD.inches
    chunks: list[list] = []
    current: list = []
    y = _STACK_TOP_IN
    for heading, body in stack_list:
        height = _stacked_section_height_in(body)
        over_budget = current and y + height > budget
        over_count = len(current) >= _MAX_STACKS_PER_SLIDE
        if over_budget or over_count:
            chunks.append(current)
            current = []
            y = _STACK_TOP_IN
        current.append((heading, body))
        y += height
    if current:
        chunks.append(current)
    return chunks


def _add_stacks_slide(
    prs: Presentation, layout, paper: Paper, ctx: _BuildContext,
    *, title: str, stacks,
) -> None:
    """Render stacked sections, paginating by height budget so author bullets
    are never silently dropped — instead the title gets ``(1/N)`` and overflow
    spills onto the next slide. See ``_paginate_stacks``.
    """
    stack_list = list(stacks)
    if not stack_list:
        return
    chunks = _paginate_stacks(stack_list)
    for chunk_index, chunk in enumerate(chunks):
        chunk_title = title
        if len(chunks) > 1:
            chunk_title = f"{title} ({chunk_index + 1}/{len(chunks)})"
        slide = _new_section_slide(prs, layout, chunk_title)
        _add_paper_subtitle(slide, paper, ctx)
        cursor = Inches(_STACK_TOP_IN)
        for heading, body in chunk:
            cursor = _add_stacked_section(slide, heading, body, cursor)


_KPI_PER_SLIDE = 6


def _add_kpi_slide(
    prs: Presentation, layout, paper: Paper, ctx: _BuildContext, metrics,
) -> None:
    """Paginate KPI metrics in chunks of ``_KPI_PER_SLIDE`` so an author
    who supplies 10 metrics gets two slides, not one with 6 and four
    silently dropped."""
    metric_list = list(metrics)
    if not metric_list:
        return
    chunks = [
        metric_list[i : i + _KPI_PER_SLIDE]
        for i in range(0, len(metric_list), _KPI_PER_SLIDE)
    ]
    for chunk_index, chunk in enumerate(chunks):
        title = t(ctx.language, "label_headline_metrics")
        if len(chunks) > 1:
            title = f"{title} ({chunk_index + 1}/{len(chunks)})"
        slide = _new_section_slide(prs, layout, title)
        _add_paper_subtitle(slide, paper, ctx)
        kpi_top = Inches(1.7)
        kpi_height = Inches(min(0.55 * len(chunk), 5.0))
        _add_kpi_lines(
            slide, tuple(chunk), ctx,
            left=_MARGIN_X, top=kpi_top,
            width=_BODY_WIDTH, height=kpi_height,
        )


def _add_technique_table_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    title = t(ctx.language, "section_technique_overview")
    slide = _new_section_slide(prs, layout, title, role=ROLE_TABLE)
    _add_paper_subtitle(slide, paper, ctx)
    rows = [(t(ctx.language, "label_technique"), t(ctx.language, "label_technique_role"))]
    rows.extend(summary.technique_table)
    _add_table(
        slide, rows=rows,
        left=_MARGIN_X, top=Inches(1.7),
        width=_BODY_WIDTH, height=Inches(5.0),
        col_widths=(Inches(3.8), Inches(8.5)),
    )


def _add_literature_table_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    title = t(ctx.language, "section_literature_positioning")
    slide = _new_section_slide(prs, layout, title, role=ROLE_TABLE)
    _add_paper_subtitle(slide, paper, ctx)
    rows = summary.literature_table
    if not rows:
        return
    cols = len(rows[0])
    col_widths = _equal_col_widths(_BODY_WIDTH, cols)
    _add_table(
        slide, rows=rows,
        left=_MARGIN_X, top=Inches(1.7),
        width=_BODY_WIDTH, height=Inches(5.0),
        col_widths=col_widths,
    )


def _add_system_overview_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    title = t(ctx.language, "section_system_overview")
    slide = _new_section_slide(prs, layout, title)
    _add_paper_subtitle(slide, paper, ctx)
    bullets = [f"{i + 1}. {step}" for i, step in enumerate(summary.system_flow)]
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=Inches(1.7),
        width=_BODY_WIDTH, height=Inches(5.0),
        font_pt=_BODY_PT,
    )


def _add_method_details_slides(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    sections = summary.method_sections
    chunk_size = _METHOD_SECTIONS_PER_SLIDE
    chunks = [sections[i : i + chunk_size] for i in range(0, len(sections), chunk_size)]
    for chunk_index, chunk in enumerate(chunks):
        title = t(ctx.language, "section_method_details")
        if len(chunks) > 1:
            title = f"{title} ({chunk_index + 1}/{len(chunks)})"
        slide = _new_section_slide(prs, layout, title)
        _add_paper_subtitle(slide, paper, ctx)
        cursor = Inches(1.7)
        for heading, bullets in chunk:
            cursor = _add_subsection(
                slide, heading, bullets, cursor, width=_BODY_WIDTH,
                language=ctx.language,
            )


def _any_section_over_cell_cap(sections) -> bool:
    """True when a section has more bullets than a 2-column grid cell shows.

    The grid path caps a cell at ``_BULLETS_PER_CELL_MAX`` and appends a
    "(+N more)" marker — fine when content fits, but a section with more bullets
    than that loses the overflow. Callers test this and, when True, render the
    section list via ``_add_paginated_bullet_sections`` (full-width, one section
    per slide, split into <= cap pages) where every bullet survives instead of
    being dropped from a cramped cell.

    Example: an evaluation section with eight findings renders as two full-width
    pages ("… (1/2)" with six, "… (2/2)" with two) rather than a 2-column grid
    that would show six + "(+2 more)".
    """
    return any(len(bullets) > _BULLETS_PER_CELL_MAX for _heading, bullets in sections)


def _add_paginated_bullet_sections(
    prs: Presentation, layout, paper: Paper, ctx: _BuildContext, *, title, sections,
) -> None:
    """Render (heading, bullets) sections full-width, one section per slide, with
    any section's bullets split into consecutive ``<heading> (i/N)`` pages of at
    most ``_BULLETS_PER_CELL_MAX`` bullets — so no bullet is ever dropped.

    Each page carries at most the cap the 2-column grid cell was already sized
    for, so the result clears the footer guard the same way the grid does. This
    is the overflow-safe fallback the grid callers use when
    ``_any_section_over_cell_cap`` is True; short content keeps the compact grid.
    """
    cap = _BULLETS_PER_CELL_MAX
    for heading, bullets in sections:
        chunks = [bullets[i : i + cap] for i in range(0, len(bullets), cap)] or [()]
        for chunk_index, chunk in enumerate(chunks):
            slide = _new_section_slide(prs, layout, title)
            _add_paper_subtitle(slide, paper, ctx)
            sub_heading = heading
            if len(chunks) > 1:
                sub_heading = f"{heading} ({chunk_index + 1}/{len(chunks)})"
            _add_subsection(
                slide, sub_heading, chunk, Inches(1.7),
                width=_BODY_WIDTH, language=ctx.language,
            )


def _add_evaluation_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    sections = summary.evaluation_sections
    if not sections:
        return
    if _any_section_over_cell_cap(sections):
        # Full-width, paginated: no bullet dropped from a cramped cell.
        _add_paginated_bullet_sections(
            prs, layout, paper, ctx,
            title=t(ctx.language, "section_evaluation"), sections=sections,
        )
        return
    chunk_size = _EVALUATION_SECTIONS_PER_SLIDE
    chunks = [sections[i : i + chunk_size] for i in range(0, len(sections), chunk_size)]
    for chunk_index, chunk in enumerate(chunks):
        title = t(ctx.language, "section_evaluation")
        if len(chunks) > 1:
            title = f"{title} ({chunk_index + 1}/{len(chunks)})"
        slide = _new_section_slide(prs, layout, title)
        _add_paper_subtitle(slide, paper, ctx)
        _render_multi_column(
            slide,
            sections=tuple(chunk),
            left=_MARGIN_X, top=Inches(1.7),
            width=_BODY_WIDTH, height=Inches(5.0),
            columns=min(2, len(chunk)),
            language=ctx.language,
        )


def _add_figure_slides(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """One slide per figure: image at top, caption below, description bullets.

    The image is loaded from ``figure.image_path`` and scaled to fit a
    fixed area, preserving aspect ratio. A missing / unreadable file is
    rendered as a placeholder bullet so the deck still flows.
    """
    base_title = t(ctx.language, "section_figure")
    for index, (caption, image_path, description) in enumerate(summary.figures, 1):
        title = (
            f"{base_title} {index}/{len(summary.figures)}"
            if len(summary.figures) > 1 else base_title
        )
        slide = _new_section_slide(prs, layout, title)
        _add_paper_subtitle(slide, paper, ctx)
        _add_figure_image(
            slide, image_path,
            left=_MARGIN_X, top=Inches(1.7),
            max_width=_BODY_WIDTH, max_height=Inches(3.6),
        )
        # Caption sits between image and bullets, full-width, italic-ish weight.
        _add_textbox(
            slide, name="subhead",
            text=f"{t(ctx.language, 'label_caption')}: {_clean(caption)}",
            left=_MARGIN_X, top=Inches(5.4),
            width=_BODY_WIDTH, height=Inches(0.5),
            font_pt=_SUBHEAD_PT - 4, bold=True, colour=_BRAND_GREY,
            shrink_to_fit=True,
        )
        if description:
            _add_bullet_box(
                slide, name="body",
                bullets=_cap_bullets(description, max_count=4, language=ctx.language),
                left=_MARGIN_X, top=Inches(5.95),
                width=_BODY_WIDTH, height=Inches(1.05),
                font_pt=_BODY_PT - 2,
            )


def _add_figure_image(
    slide, image_path: str, *, left, top, max_width, max_height,
) -> None:
    from pathlib import Path as PathT

    path = PathT(image_path)
    if not path.is_file():
        _add_textbox(
            slide, name="body",
            text=f"[figure unavailable: {path.name}]",
            left=left, top=top, width=max_width, height=Inches(0.5),
            # Muted grey for a placeholder/error state — not a headline.
            # Was red, then briefly navy; settled on grey because this
            # surface is contextual chrome, not "this stands out".
            font_pt=_BODY_PT, colour=_BRAND_GREY,
        )
        return
    # python-pptx scales by aspect ratio if we pass only height (or
    # width), but we don't know the image's intrinsic size up-front.
    # Strategy: insert with max_height; if the resulting width overflows
    # the body, re-insert with max_width instead. PIL would let us
    # compute aspect ratio first but we avoid the extra dep.
    pic = slide.shapes.add_picture(
        str(path), left, top, height=max_height,
    )
    if pic.width > max_width:
        # Drop + reinsert constrained by width.
        sp = pic._element  # noqa: SLF001  # python-pptx needs raw XML access
        sp.getparent().remove(sp)
        pic = slide.shapes.add_picture(
            str(path), left, top, width=max_width,
        )
    # Centre horizontally if narrower than body
    if pic.width < max_width:
        pic.left = left + Emu((max_width - pic.width) // 2)
    pic.name = "figure"


def _add_paper_table_slides(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """One slide per paper-table: render the table plus analysis bullets."""
    base_title = t(ctx.language, "section_paper_table")
    for index, (caption, rows, analysis) in enumerate(summary.paper_tables, 1):
        if not rows:
            continue
        title = (
            f"{base_title} {index}/{len(summary.paper_tables)}"
            if len(summary.paper_tables) > 1 else base_title
        )
        slide = _new_section_slide(prs, layout, title, role=ROLE_TABLE)
        _add_paper_subtitle(slide, paper, ctx)
        _add_textbox(
            slide, name="subhead",
            text=f"{t(ctx.language, 'label_caption')}: {_clean(caption)}",
            left=_MARGIN_X, top=Inches(1.65),
            width=_BODY_WIDTH, height=Inches(0.55),
            # Mid grey reads as a caption label (matches the figure-slide
            # caption style at line ~887) rather than competing with the
            # paper-table itself for the eye. Was red, then briefly navy.
            font_pt=_SUBHEAD_PT - 2, bold=True, colour=_BRAND_GREY,
            shrink_to_fit=True,
        )
        cols = len(rows[0])
        col_widths = _equal_col_widths(_BODY_WIDTH, cols)
        _add_table(
            slide, rows=rows,
            left=_MARGIN_X, top=Inches(2.3),
            width=_BODY_WIDTH, height=Inches(3.0),
            col_widths=col_widths,
        )
        if analysis:
            _add_bullet_box(
                slide, name="body",
                bullets=_cap_bullets(analysis, max_count=6, language=ctx.language),
                left=_MARGIN_X, top=Inches(5.6),
                width=_BODY_WIDTH, height=Inches(1.4),
                font_pt=_BODY_PT,
            )


def _add_research_questions_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    title = t(ctx.language, "section_research_questions")
    slide = _new_section_slide(prs, layout, title)
    _add_paper_subtitle(slide, paper, ctx)
    bullets = [f"{rq_id}: {question}" for rq_id, question in summary.research_questions]
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=Inches(1.8),
        width=_BODY_WIDTH, height=Inches(4.9),
        font_pt=_BODY_PT + 1,
    )


def _add_rq_result_slide(
    prs: Presentation, layout, paper: Paper, rq: RqResult, ctx: _BuildContext,
    *, rq_lookup: dict[str, str] | None = None,
) -> None:
    title = f"{t(ctx.language, 'section_results_for')} {rq.rq_id}"
    slide = _new_section_slide(prs, layout, title, role=ROLE_TABLE)
    _add_paper_subtitle(slide, paper, ctx)
    # Prefer the verbatim question from ``research_questions`` so the RQ
    # slide carries the paper's actual wording rather than a short label
    # the author may have used in the RqResult.question field. The lookup
    # is keyed by rq_id; falls back to whatever the RqResult provided.
    question_text = rq.question
    if rq_lookup:
        full_question = rq_lookup.get(rq.rq_id, "")
        if full_question:
            question_text = full_question
    _add_textbox(
        slide, name="rq_question", text=question_text,
        left=_MARGIN_X, top=Inches(1.65),
        width=_BODY_WIDTH, height=Inches(0.55),
        # Teal highlight — this is the actual research question being
        # answered on this slide; the eye should land on it before the
        # results table below. Was red, then briefly navy; teal carries
        # the "thoughtful, intentional" tone without the warning vibe.
        font_pt=_SUBHEAD_PT - 2, bold=True, colour=_BRAND_HIGHLIGHT,
        shrink_to_fit=True,
    )
    if rq.table:
        cols = len(rq.table[0])
        col_widths = _equal_col_widths(_BODY_WIDTH, cols)
        _add_table(
            slide, rows=rq.table,
            left=_MARGIN_X, top=Inches(2.3),
            width=_BODY_WIDTH, height=Inches(3.0),
            col_widths=col_widths,
        )
    if rq.analysis:
        analysis_top = Inches(5.6) if rq.table else Inches(2.4)
        # Show up to 6 analysis bullets so authors don't lose argument
        # detail to a silent 3-bullet cap.
        _add_bullet_box(
            slide, name="body",
            bullets=_cap_bullets(rq.analysis, max_count=6, language=ctx.language),
            left=_MARGIN_X, top=analysis_top,
            width=_BODY_WIDTH, height=Inches(1.4 if rq.table else 4.5),
            font_pt=_BODY_PT,
        )


def _add_contribution_summary_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    """Always split contribution-summary stacks vs core_observation callout."""
    if summary.contributions_detailed:
        _add_stacks_slide(
            prs, layout, paper, ctx,
            title=t(ctx.language, "section_contribution_summary"),
            stacks=summary.contributions_detailed,
        )
    if summary.core_observation:
        slide = _new_section_slide(
            prs, layout, t(ctx.language, "label_core_observation")
        )
        _add_paper_subtitle(slide, paper, ctx)
        _add_rq_callout(
            slide, summary.core_observation,
            left=_MARGIN_X, top=Inches(2.5),
            width=_BODY_WIDTH, height=Inches(2.0), highlight=True,
        )


def _add_limitations_future_slide(
    prs: Presentation, layout, paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    title = (
        f"{t(ctx.language, 'section_limitations')} & "
        f"{t(ctx.language, 'section_future_work')}"
    )
    sections: list[tuple[str, tuple[str, ...]]] = []
    if summary.limitations:
        sections.append(
            (t(ctx.language, "section_limitations"), tuple(summary.limitations))
        )
    if summary.future_work:
        sections.append(
            (t(ctx.language, "section_future_work"), tuple(summary.future_work))
        )
    if _any_section_over_cell_cap(sections):
        # A long limitations / future-work list would lose bullets in the
        # 2-column grid; render full-width paginated so all survive.
        _add_paginated_bullet_sections(
            prs, layout, paper, ctx, title=title, sections=tuple(sections),
        )
        return
    slide = _new_section_slide(prs, layout, title)
    _add_paper_subtitle(slide, paper, ctx)
    _render_multi_column(
        slide,
        sections=tuple(sections),
        left=_MARGIN_X, top=Inches(1.7),
        width=_BODY_WIDTH, height=Inches(5.0),
        columns=2,
        language=ctx.language,
    )


# ---------------------------------------------------------------------------
# Legacy content slide (used by flat / abstract fallback paths)
# ---------------------------------------------------------------------------


def _add_content_slide(
    prs: Presentation, layout, index: int, total: int,
    paper: Paper, section_key: str, sentences: list[str], ctx: _BuildContext,
) -> None:
    section_title = t(ctx.language, section_key)
    slide = _new_section_slide(prs, layout, section_title)
    meta_text = (
        f"{_clean(paper.title)} · "
        f"{t(ctx.language, 'paper_n_of_m', n=index, m=total)}"
    )
    meta_height_in, meta_overflows = _content_meta_height_in(meta_text)
    _add_textbox(
        slide, name="meta", text=meta_text,
        left=_MARGIN_X, top=_BODY_TOP,
        width=_BODY_WIDTH, height=Inches(meta_height_in),
        font_pt=_CONTENT_META_PT, colour=_BRAND_GREY,
        shrink_to_fit=meta_overflows,
    )
    fallback = [_clean(paper.abstract)]
    raw_bullets = _sentences_to_bullets(sentences) or fallback
    bullets = _cap_bullets(
        raw_bullets, max_count=6, max_chars=_BULLET_MAX_CHARS, language=ctx.language,
    )
    # The body starts below however many lines the meta needed and keeps its
    # bottom edge, so a two-line title costs the body 0.1" instead of
    # overflowing the meta box (progress #11).
    body_top = _BODY_TOP + Inches(meta_height_in + _CONTENT_META_GAP_IN)
    _add_bullet_box(
        slide, name="body", bullets=bullets,
        left=_MARGIN_X, top=body_top,
        width=_BODY_WIDTH, height=_CONTENT_BODY_BOTTOM - body_top,
        font_pt=_BODY_PT,
    )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _cover_title(collection: PaperCollection, ctx: _BuildContext) -> str:
    if len(collection) == 1:
        return _clean(collection.papers[0].title)
    prefix = t(ctx.language, "paper_review_prefix")
    return f"{prefix} {collection.query.keywords}"


def _english_subtitle(paper: Paper) -> str:
    # For single-paper decks, surface the paper's title verbatim under the
    # (possibly translated) cover title. When the title is already in English
    # this duplicates — that's fine for now and easier than language-detecting.
    return paper.title


def _cover_subtitle(collection: PaperCollection, ctx: _BuildContext) -> str:
    paper_count = len(collection)
    source_list = ", ".join(collection.query.sources)
    if paper_count == 1:
        paper = collection.papers[0]
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."
        year = paper.year or t(ctx.language, "year_no_date")
        venue = paper.venue or paper.source
        return f"{authors}\n{year} · {venue}"
    span_bits: list[str] = []
    if collection.query.year_from or collection.query.year_to:
        span_bits.append(
            f"{collection.query.year_from or '—'} – {collection.query.year_to or '—'}"
        )
    span = f" ({'; '.join(span_bits)})" if span_bits else ""
    count_text = _paper_count_text(paper_count, ctx)
    return f"{count_text} · {source_list}{span}"


def _paper_count_text(count: int, ctx: _BuildContext) -> str:
    key = "paper_count_singular" if count == 1 else "paper_count_plural"
    return t(ctx.language, key, n=count)


def _agenda_line(index: int, paper: Paper, ctx: _BuildContext) -> str:
    title = _clean(paper.title)
    year = paper.year or t(ctx.language, "year_no_date")
    return f"{index:>2}. {title} ({year})"


def _reference_line(index: int, paper: Paper, ctx: _BuildContext) -> str:
    authors_short = paper.authors[0] if paper.authors else "Anon"
    if len(paper.authors) > 1:
        authors_short += " et al."
    year = paper.year or t(ctx.language, "year_no_date")
    ident = paper.doi or paper.arxiv_id or paper.url
    title = _clean(paper.title)
    return f"{index:>2}. {authors_short} ({year}). {title} — {ident}"


def _overview_meta(paper: Paper, ctx: _BuildContext) -> str:
    authors_line = (
        ", ".join(paper.authors) if paper.authors else t(ctx.language, "no_authors_dash")
    )
    year_part = str(paper.year) if paper.year else t(ctx.language, "year_no_date")
    venue_part = f" · {paper.venue}" if paper.venue else ""
    return (
        f"{authors_line}\n{year_part}{venue_part}\n"
        f"{t(ctx.language, 'label_source')}: {paper.source}"
    )


def _overview_bullets(paper: Paper, ctx: _BuildContext) -> Iterable[str]:
    s = strings_for(ctx.language)
    if paper.url:
        yield f"{s['label_url']}: {paper.url}"
    if paper.doi:
        yield f"{s['label_doi']}: {paper.doi}"
    if paper.arxiv_id:
        yield f"{s['label_arxiv']}: {paper.arxiv_id}"
    if paper.pdf_url:
        yield f"{s['label_pdf']}: {paper.pdf_url}"
    if paper.citation_count is not None:
        yield f"{s['label_citations']}: {paper.citation_count}"
    yield f"{s['label_bibtex_key']}: {paper.bibtex_key()}"


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


def _new_section_slide(
    prs: Presentation, layout, title: str, *, font_pt: int = _SECTION_TITLE_PT,
    role: str = ROLE_CONTENT,
):
    """Add a "title on top, content below" slide and return it.

    ``layout`` is the deck's ``LayoutSet`` and ``role`` picks the layout: a
    template can give table and reference slides a layout of their own.
    """
    slide = layout.add_slide(prs, role)
    placeholder = layout.title_placeholder(slide, role)
    if placeholder is not None:
        _fill_title_placeholder(placeholder, _clean(title), font_pt=font_pt)
        return slide
    # The title sits inside the navy header band (placed later by the accent
    # pass), so it is WHITE, not navy — navy-on-navy would be invisible.
    # ``shrink_to_fit`` lets a long title (e.g. a verbatim paper title) wrap
    # within the band's height and PowerPoint scales the font down so the
    # text never spills past the band's bottom accent rule. The separate
    # horizontal rule is gone — the band + its teal under-rule replace it.
    _add_textbox(
        slide, name="title", text=_clean(title),
        left=_MARGIN_X, top=Inches(0.18),
        width=_BODY_WIDTH, height=Inches(0.86),
        font_pt=font_pt, bold=True, colour=_HEADER_TITLE_FG,
        align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE,
        shrink_to_fit=True,
    )
    return slide


def _fill_title_placeholder(placeholder, text: str, *, font_pt: int) -> None:
    """Write a slide title into the template's title placeholder.

    The boundary this guards: a shape the template owns. Its position and
    size are the template's, which is the point of the opt-in. Everything the
    project's contracts need is still set here: the semantic name ``title``
    (``pptx_edit`` and the audits find the title by name), an explicit run
    colour (a run without one is invisible in dark mode), and the exporter's
    title size with shrink-to-fit, so the overflow check reads a real size.

    The colour is ``_BRAND_DARK``, not the white of a band title: with a
    title placeholder the header band is not drawn on the slide.

    Example: a layout "Title Only" whose placeholder sits 0.4 in from the
    top keeps the title there, in navy, named ``title``.
    """
    placeholder.name = "title"
    text_frame = placeholder.text_frame
    text_frame.word_wrap = True
    text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    text_frame.text = text
    for paragraph in text_frame.paragraphs:
        for run in paragraph.runs:
            run.font.size = Pt(font_pt)
            run.font.bold = True
            run.font.color.rgb = _BRAND_DARK

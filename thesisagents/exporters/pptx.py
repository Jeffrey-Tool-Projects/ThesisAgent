"""Full presentable PowerPoint deck.

Three rendering paths:

1. **Lightweight** (default, abstract only). Each paper gets cover · agenda ·
   overview · Background/Approach/Findings · references.

2. **Enriched-flat** (``PaperSummary`` with motivation/contributions/method/
   results/limitations/takeaways but no rich fields). Each paper's flat
   bullet sections become their own slides.

3. **Thesis-style** (``PaperSummary`` with rich fields: pain_points, research
   question, headline_metrics, technique_table, literature_table,
   method_sections, evaluation_sections, research_questions, rq_results,
   …). Each paper expands into a thesis-defence-style deck — multi-column
   pain-point quadrants, KPI callouts, technique-comparison tables, per-RQ
   result tables, contribution summary, limitations + future work, Q&A.

Deck-level features:

* 16:9 widescreen (13.33" × 7.5") matching modern slide tools' default.
* Page-number footer "N / total" on every slide except the cover.
* Section-title plus a horizontal rule beneath, matching the reference deck.

All template strings flow through ``i18n.py`` so the deck respects
``ExportOptions.language``. Shape names stay semantic (``title`` / ``meta``
/ ``body`` / ``footer`` / ``page_number``) so ``pptx_edit`` keeps working.

This module decides what a deck contains. The measures are in
``pptx_style.py``, text and tables in ``pptx_text.py``, the slides in
``pptx_slides.py`` and the finishing passes in ``pptx_finish.py``.
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from thesisagents.core.constants import EXPORT_PPTX
from thesisagents.core.exceptions import ExportError
from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary
from thesisagents.exporters.base import Exporter
from thesisagents.exporters.pptx_finish import (
    _apply_dark_mode,
    _apply_template_palette,
    _apply_typography,
    _categorise_slides,
    _decorate_with_accents,
    _recolor_text_without_chrome,
    _set_east_asian_typeface,
    _stamp_page_numbers,
    _trim_to_slide_budget,
)
from thesisagents.exporters.pptx_slides import (
    _add_agenda_slide,
    _add_content_slide,
    _add_contribution_summary_slide,
    _add_contributions_detailed_slide,
    _add_cover_slide,
    _add_evaluation_slide,
    _add_figure_slides,
    _add_limitations_future_slide,
    _add_literature_table_slide,
    _add_method_details_slides,
    _add_overview_slide,
    _add_pain_points_slide,
    _add_paper_table_slides,
    _add_qa_slide,
    _add_references_slide,
    _add_research_question_slide,
    _add_research_questions_slide,
    _add_rq_result_slide,
    _add_section_divider,
    _add_system_overview_slide,
    _add_technique_table_slide,
    _callout_height_in,
    _is_own_thesis,
)
from thesisagents.exporters.pptx_style import (
    _BODY_TOP,
    _BODY_WIDTH,
    _BRAND_GREY,
    _DARK_BODY_TEXT,
    _MARGIN_X,
    _SECTION_TITLE_PT,
    _SLIDE_HEIGHT,
    _SLIDE_WIDTH,
    _BuildContext,
)
from thesisagents.exporters.pptx_text import (
    _add_bullet_box,
    _add_math_run,
    _add_paper_subtitle,
    _add_rq_callout,
    _add_stacked_section,
    _add_table,
    _add_textbox,
    _append_math_runs,
    _content_meta_height_in,
    _render_math_paragraph,
    _segment_abstract,
)
from thesisagents.exporters.template import (
    LayoutSet,
    TemplateConfig,
    builtin_layouts,
    open_template,
)

#: ``PptxExporter`` is the interface. The others moved to the modules above
#: and stay importable from here, because the regen
#: scripts and the tests name them by this path.
__all__ = [
    "PptxExporter",
    "_BODY_TOP",
    "_BODY_WIDTH",
    "_BRAND_GREY",
    "_DARK_BODY_TEXT",
    "_MARGIN_X",
    "_SECTION_TITLE_PT",
    "_add_bullet_box",
    "_add_math_run",
    "_add_paper_subtitle",
    "_add_rq_callout",
    "_add_stacked_section",
    "_add_table",
    "_add_textbox",
    "_append_math_runs",
    "_callout_height_in",
    "_categorise_slides",
    "_content_meta_height_in",
    "_render_math_paragraph",
    "_set_east_asian_typeface",
]

# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class PptxExporter(Exporter):
    format = EXPORT_PPTX
    extension = "pptx"

    def export(self, collection: PaperCollection, options: ExportOptions) -> Path:
        try:
            presentation = self._build(collection, options)
        except ExportError:
            # Already a named, actionable error (e.g. _run_slide_builder's
            # "in summary field 'research_questions'"). Re-wrapping would
            # nest two "[pptx] render failed:" prefixes and bury the detail.
            raise
        except Exception as err:
            raise ExportError(self.format, f"render failed: {err}") from err
        out_path = self.resolve_out_path(collection, options)
        presentation.save(str(out_path))
        return out_path

    def _build(
        self, collection: PaperCollection, options: ExportOptions
    ) -> Presentation:
        prs, blank, template = _open_presentation(options)
        total = len(collection)
        ctx = _BuildContext(language=options.language, include_abstract=options.include_abstract)
        _add_cover_slide(prs, blank, collection, ctx)
        if total > 1:
            _add_agenda_slide(prs, blank, collection, ctx)
        for index, paper in enumerate(collection.papers, start=1):
            _add_paper_slides(prs, blank, index, total, paper, ctx)
        if total > 0:
            _add_references_slide(prs, blank, collection, ctx)
        # Drop lower-priority slides if a positive cap is configured.
        # ``None`` and any non-positive int both disable the cap so the
        # full rich-tier deck flows through unchanged.
        budget = options.max_slides_per_paper
        if budget is not None and budget > 0:
            _trim_to_slide_budget(
                prs,
                language=ctx.language,
                paper_count=max(total, 1),
                budget_per_paper=budget,
            )
        # Page numbers are stamped AFTER trim so they reflect the final total.
        _stamp_page_numbers(prs, ctx.language)
        # Visual identity passes — applied last so they affect every shape
        # placed by every builder (including page numbers). See the
        # ``deck-design`` subagent doc for rationale.
        _apply_typography(
            prs, ctx.language, latin=template.font_latin, east_asian=template.font_east_asian
        )
        _decorate_with_accents(
            prs, header_band=template.header_band, cover_panel=template.cover_panel
        )
        _recolor_text_without_chrome(prs, template)
        # Dark mode has its own palette, tuned for contrast on the dark
        # slide, so a template's [colors] apply to the light deck only
        # (validate_template reports that as a warning).
        if options.dark_mode:
            _apply_dark_mode(prs)
        elif template.colors:
            _apply_template_palette(prs, template.colors)
        return prs


def _open_presentation(
    options: ExportOptions,
) -> tuple[Presentation, LayoutSet, TemplateConfig]:
    """The presentation to fill, the layout of each slide role, the style overrides.

    The boundary this guards: a user-supplied template. It is checked against
    the template contract here, before any slide is built, and a template that
    does not meet it raises ``TemplateError`` listing every problem (see
    ``thesisagents/exporters/template.py``).

    Without ``options.pptx_template`` this is the built-in deck: python-pptx's
    own template, every role on its blank layout, no overrides.
    """
    if options.pptx_template:
        opened = open_template(
            options.pptx_template,
            options.pptx_template_config,
            dark_mode=options.dark_mode,
        )
        return opened.presentation, opened.layouts, opened.config
    prs = Presentation()
    prs.slide_width = _SLIDE_WIDTH
    prs.slide_height = _SLIDE_HEIGHT
    return prs, builtin_layouts(prs), TemplateConfig()


def _add_paper_slides(
    prs: Presentation, layout, index: int, total: int, paper: Paper, ctx: _BuildContext
) -> None:
    if total > 1:
        _add_section_divider(prs, layout, index, total, paper, ctx)
    # The source/overview slide (and its BibTeX cite-key) exists to attribute a
    # *borrowed* paper; the candidate's own thesis has no fetched source to
    # credit, and the cover already carries its title / authors / venue. Skip
    # it so a defence deck doesn't open on a "來源 / BibTeX key" page.
    if not _is_own_thesis(paper):
        _add_overview_slide(prs, layout, paper, ctx)
    if not ctx.include_abstract:
        return
    summary = paper.summary
    if summary is not None and summary.has_rich_fields():
        _add_rich_summary_slides(prs, layout, index, total, paper, summary, ctx)
        return
    if summary is not None and not summary.is_empty():
        _add_flat_summary_slides(prs, layout, index, total, paper, summary, ctx)
        return
    if paper.abstract:
        _add_abstract_split_slides(prs, layout, index, total, paper, ctx)


#: Slide plan entries: (predicate(summary) -> bool, builder).
#: Used by _add_rich_summary_slides; split into two halves around per-RQ
#: result slides so RQ-intro → per-RQ tables → contribution summary stays
#: in narrative order.
def _build_rich_plan(summary: PaperSummary):
    return [
        (bool(summary.pain_points), _add_pain_points_slide),
        (
            bool(summary.research_question) and not summary.pain_points,
            _add_research_question_slide,
        ),
        (
            bool(summary.contributions_detailed or summary.headline_metrics),
            _add_contributions_detailed_slide,
        ),
        (bool(summary.technique_table), _add_technique_table_slide),
        (bool(summary.literature_table), _add_literature_table_slide),
        (bool(summary.system_flow), _add_system_overview_slide),
        (bool(summary.figures), _add_figure_slides),
        (bool(summary.method_sections), _add_method_details_slides),
        (bool(summary.evaluation_sections), _add_evaluation_slide),
        (bool(summary.paper_tables), _add_paper_table_slides),
        (bool(summary.research_questions), _add_research_questions_slide),
    ]


def _build_rich_plan_tail(summary: PaperSummary):
    return [
        (
            bool(summary.contributions_detailed or summary.core_observation),
            _add_contribution_summary_slide,
        ),
        (bool(summary.limitations or summary.future_work), _add_limitations_future_slide),
    ]


def _add_rich_summary_slides(
    prs: Presentation, layout, index: int, total: int,
    paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    _ = index, total  # reserved for future per-slide footers
    for predicate, builder in _build_rich_plan(summary):
        if predicate:
            _run_slide_builder(builder, prs, layout, paper, summary, ctx)
    rq_lookup = dict(summary.research_questions)
    for rq in summary.rq_results:
        _add_rq_result_slide(prs, layout, paper, rq, ctx, rq_lookup=rq_lookup)
    for predicate, builder in _build_rich_plan_tail(summary):
        if predicate:
            _run_slide_builder(builder, prs, layout, paper, summary, ctx)
    _add_qa_slide(prs, layout, paper, ctx)


#: Rich ``PaperSummary`` field each slide builder reads, so a shape error can
#: name the field the author has to fix rather than the private function.
_BUILDER_SOURCE_FIELD: dict[str, str] = {
    "_add_pain_points_slide": "pain_points",
    "_add_research_question_slide": "research_question",
    "_add_contributions_detailed_slide": "contributions_detailed / headline_metrics",
    "_add_technique_table_slide": "technique_table",
    "_add_literature_table_slide": "literature_table",
    "_add_system_overview_slide": "system_flow",
    "_add_figure_slides": "figures",
    "_add_method_details_slides": "method_sections",
    "_add_evaluation_slide": "evaluation_sections",
    "_add_paper_table_slides": "paper_tables",
    "_add_research_questions_slide": "research_questions",
    "_add_contribution_summary_slide": "contributions_detailed / core_observation",
    "_add_limitations_future_slide": "limitations / future_work",
}


def _run_slide_builder(builder, prs, layout, paper, summary, ctx) -> None:
    """Call one rich-tier slide builder, naming the guilty field if it raises.

    Why: every rich field is a nested tuple shape (``pain_points`` is
    ``((heading, (bullet, ...)), ...)``; ``research_questions`` is
    ``((rq_id, question), ...)``), and this project's documented authoring path
    is a hand-written ``scripts/regen_*.py``. Passing a flat list of strings
    where a pair was expected surfaced as
    ``[pptx] render failed: too many values to unpack (expected 2)`` — a true
    statement that names neither the field nor the paper, leaving the author to
    bisect a 15-field summary by hand.

    Example message after this wrapper::

        [pptx] render failed for 'chen2026longtext' in summary field
        'research_questions': too many values to unpack (expected 2)

    Anti-pattern: catching and *skipping* the failed builder — that ships a deck
    silently missing a section the author wrote.
    """
    try:
        builder(prs, layout, paper, summary, ctx)
    except (ValueError, TypeError, AttributeError, IndexError, KeyError) as err:
        field_name = _BUILDER_SOURCE_FIELD.get(
            getattr(builder, "__name__", ""), "an unknown field"
        )
        raise ExportError(
            EXPORT_PPTX,
            f"render failed for {paper.bibtex_key()!r} in summary field "
            f"{field_name!r}: {err}. Check that field's shape against "
            f"PaperSummary in thesisagents/core/models.py.",
        ) from err


def _add_flat_summary_slides(
    prs: Presentation, layout, index: int, total: int,
    paper: Paper, summary: PaperSummary, ctx: _BuildContext,
) -> None:
    sections: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("section_motivation", summary.motivation),
        ("section_contributions", summary.contributions),
        ("section_method", summary.method),
        ("section_results", summary.results),
        ("section_limitations", summary.limitations),
        ("section_takeaways", summary.takeaways),
    )
    for key, bullets in sections:
        if bullets:
            _add_content_slide(prs, layout, index, total, paper, key, list(bullets), ctx)


def _add_abstract_split_slides(
    prs: Presentation, layout, index: int, total: int,
    paper: Paper, ctx: _BuildContext,
) -> None:
    buckets = _segment_abstract(paper.abstract)
    _add_content_slide(
        prs, layout, index, total, paper,
        "section_background", buckets["background"], ctx,
    )
    if buckets["approach"]:
        _add_content_slide(
            prs, layout, index, total, paper,
            "section_approach", buckets["approach"], ctx,
        )
    _add_content_slide(
        prs, layout, index, total, paper,
        "section_findings",
        buckets["results"] or buckets["background"], ctx,
    )

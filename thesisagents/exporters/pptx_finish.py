"""What is done to a deck after its slides exist.

Trimming to the slide budget, page numbers, fonts, the header band and cover
panel, template palette, and the dark-mode pass.
"""

from __future__ import annotations

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu

from thesisagents.exporters.i18n import strings_for
from thesisagents.exporters.pptx_style import (
    _ACCENT_RULE_HEIGHT,
    _BRAND_DARK,
    _BRAND_GREY,
    _BRAND_HIGHLIGHT,
    _BRAND_LIGHT,
    _DARK_BODY_TEXT,
    _DARK_SLIDE_BG,
    _DEFAULT_FONT_FAMILY,
    _FONT_FAMILIES,
    _FOOTER_HEIGHT,
    _FOOTER_PT,
    _FOOTER_Y,
    _HEADER_ACCENT_FILL,
    _HEADER_BAND_HEIGHT,
    _HEADER_TITLE_FG,
    _LIGHT_TO_DARK_FILL,
    _LIGHT_TO_DARK_TEXT,
    _PAGE_NUMBER_WIDTH,
    _PAGE_NUMBER_X,
    _SLIDE_HEIGHT,
    _SLIDE_WIDTH,
    _rgb_hex,
    _rgb_key,
)
from thesisagents.exporters.pptx_text import _add_textbox
from thesisagents.exporters.template import TemplateConfig

#: Slide-category priority for the ``max_slides_per_paper`` trim.
#: Higher = keep; lower = drop first when over budget. Categories not
#: listed here default to ``_DEFAULT_PRIORITY``.
_CATEGORY_PRIORITY: dict[str, int] = {
    "cover": 100,
    "references": 100,
    "contributions": 95,
    "metrics": 95,
    "overview": 92,
    "research_question": 90,
    "core_observation": 90,
    "pain_points": 85,
    "research_questions": 80,
    "agenda": 78,
    "rq_results": 70,
    "limitations_future": 70,
    "method_details": 60,
    "evaluation": 60,
    "system_overview": 55,
    "technique_table": 55,
    "figure": 50,
    "paper_table": 50,
    "qa": 45,
    "contribution_summary": 40,
    "literature_table": 40,
    "section_divider": 38,
}
_DEFAULT_PRIORITY = 65


def _trim_to_slide_budget(
    prs: Presentation, *, language: str, paper_count: int, budget_per_paper: int,
) -> None:
    """Drop the lowest-priority slides until the per-paper budget fits.

    For multi-paper decks the budget scales linearly with paper count
    (so ``--max-slides 12`` on a 3-paper deck keeps up to 36 slides
    plus the shared cover / agenda / references). The cover, agenda,
    references and core-deliverable slides are always preferred.
    """
    total_budget = max(1, budget_per_paper * paper_count)
    current = len(prs.slides)
    if current <= total_budget:
        return
    categories = _categorise_slides(prs, language)
    indexed = sorted(
        range(current),
        key=lambda i: (
            _CATEGORY_PRIORITY.get(categories[i], _DEFAULT_PRIORITY),
            -i,  # break ties by dropping later slides first
        ),
    )
    drop_count = current - total_budget
    drop_set = set(indexed[:drop_count])
    import logging

    logging.getLogger("thesisagents.exporters.pptx").info(
        "max_slides trim: budget=%d, current=%d → dropping %d "
        "slides (categories=%s)",
        total_budget, current, drop_count,
        sorted({categories[i] for i in drop_set}),
    )
    sld_id_list = prs.slides._sldIdLst  # noqa: SLF001  # python-pptx exposes only via _ attr
    elements = list(sld_id_list)
    for i in sorted(drop_set, reverse=True):
        sld_id_list.remove(elements[i])


def _categorise_slides(prs: Presentation, language: str) -> list[str]:
    """Tag each slide with a category so the trim can drop by priority.

    Title-based heuristic: each slide's ``title`` shape text is matched
    against i18n strings to recover the category. Slide 0 is always the
    cover (paper title varies so we can't match it).
    """
    strings = strings_for(language)
    label_to_cat = _build_label_to_category_map(strings)
    markers = {
        "limitations": strings.get("section_limitations", ""),
        "future_work": strings.get("section_future_work", ""),
        "results_for": strings.get("section_results_for", ""),
        "paper_n_of_m_prefix": strings["paper_n_of_m"].split("{", 1)[0].strip(),
    }
    out: list[str] = []
    for i, slide in enumerate(prs.slides):
        if i == 0:
            out.append("cover")
            continue
        title = _slide_title_text(slide)
        category = _classify_title(title, label_to_cat, markers)
        # Single-paper decks emit an "overview" slide right after the cover
        # whose title is the paper title (so it doesn't match any i18n key).
        if category == "unknown" and i == 1:
            category = "overview"
        out.append(category)
    return out


def _build_label_to_category_map(strings: dict[str, str]) -> dict[str, str]:
    return {
        strings["agenda"]: "agenda",
        strings["references"]: "references",
        strings["section_pain_points"]: "pain_points",
        strings["section_research_question"]: "research_question",
        strings["section_contributions"]: "contributions",
        strings["label_headline_metrics"]: "metrics",
        strings["section_technique_overview"]: "technique_table",
        strings["section_literature_positioning"]: "literature_table",
        strings["section_system_overview"]: "system_overview",
        strings["section_method_details"]: "method_details",
        strings["section_evaluation"]: "evaluation",
        strings["section_research_questions"]: "research_questions",
        strings["section_contribution_summary"]: "contribution_summary",
        strings["label_core_observation"]: "core_observation",
        strings["section_qa"]: "qa",
        strings["section_figure"]: "figure",
        strings["section_paper_table"]: "paper_table",
    }


def _slide_title_text(slide) -> str:
    for shape in slide.shapes:
        if shape.has_text_frame and shape.name == "title":
            return shape.text_frame.text.strip()
    return ""


def _classify_title(
    title: str, label_to_cat: dict[str, str], markers: dict[str, str],
) -> str:
    limitations = markers["limitations"]
    future_work = markers["future_work"]
    if limitations and future_work and limitations in title and future_work in title:
        return "limitations_future"
    if markers["results_for"] and title.startswith(markers["results_for"]):
        return "rq_results"
    if (
        markers["paper_n_of_m_prefix"]
        and title.startswith(markers["paper_n_of_m_prefix"])
    ):
        return "section_divider"
    # Longest matching label wins ("Research Questions" beats "Research Question").
    category = "unknown"
    best_match_len = 0
    for label, name in label_to_cat.items():
        if label and title.startswith(label) and len(label) > best_match_len:
            category = name
            best_match_len = len(label)
    return category


def _stamp_page_numbers(prs: Presentation, language: str) -> None:
    _ = language  # reserved for future locale-specific formatting
    total = len(prs.slides)
    for index, slide in enumerate(prs.slides):
        if index == 0:
            continue  # no page number on the cover
        _add_textbox(
            slide, name="page_number", text=f"{index}  /  {total - 1}",
            left=_PAGE_NUMBER_X, top=_FOOTER_Y,
            width=_PAGE_NUMBER_WIDTH, height=_FOOTER_HEIGHT,
            font_pt=_FOOTER_PT, colour=_BRAND_LIGHT,
            align=PP_ALIGN.RIGHT,
        )


# ---------------------------------------------------------------------------
# Visual identity passes — typography + accent geometry
# ---------------------------------------------------------------------------


def _apply_typography(
    prs: Presentation,
    language: str,
    *,
    latin: str | None = None,
    east_asian: str | None = None,
) -> None:
    """Set Latin + East-Asian font on every run across every slide.

    Default Calibri is the biggest "AI-generated deck" tell. We walk
    every shape post-build and write both ``<a:latin>`` and ``<a:ea>``
    typeface XML on every run — leaving the east-asian slot at the
    PowerPoint default would make CJK chars render in a font that
    doesn't match the Latin choice.

    ``latin`` / ``east_asian`` are a template config's ``[fonts]``. Each
    replaces the per-language default for its own slot only, so a template
    that names a Latin family keeps the language's East-Asian one.
    """
    default_latin, default_east_asian = _FONT_FAMILIES.get(language, _DEFAULT_FONT_FAMILY)
    latin = latin or default_latin
    east_asian = east_asian or default_east_asian
    for run in _deck_runs(prs):
        run.font.name = latin
        if east_asian:
            _set_east_asian_typeface(run, east_asian)


def _deck_runs(prs: Presentation):
    """Yield every text run on every slide, skipping shapes with no text frame.

    Pictures, connectors and tables have no ``text_frame``, so a deck-wide
    pass that read it unguarded would raise on the first figure slide.
    Example: ``sum(1 for _ in _deck_runs(prs))`` counts the deck's runs.
    """
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                yield from _frame_runs(shape.text_frame)


def _frame_runs(text_frame):
    """Yield every run of ``text_frame``, paragraph by paragraph.

    Shared by the post-build passes (typography, colour swaps) so each walks
    runs the same way instead of nesting its own paragraph loop. Example:
    ``[r.text for r in _frame_runs(box.text_frame)]`` lists the box's runs.
    """
    for paragraph in text_frame.paragraphs:
        yield from paragraph.runs


def _explicit_run_rgb(run) -> RGBColor | None:
    """The run's explicit RGB colour, ``None`` when it has none to read.

    Guards the colour passes against runs whose colour is a theme colour or
    unset: python-pptx raises ``AttributeError`` / ``ValueError`` /
    ``TypeError`` on ``font.color.rgb`` there, and the passes treat such a
    run as having no RGB instead of aborting the deck. Example: a run set
    with ``run.font.color.rgb = _BRAND_DARK`` returns ``_BRAND_DARK``.
    """
    try:
        return run.font.color.rgb
    except (AttributeError, ValueError, TypeError):
        return None


def _set_east_asian_typeface(run, family: str) -> None:
    """Write the ``<a:ea typeface=...>`` element on a run's rPr.

    python-pptx's ``run.font.name`` setter only writes the Latin
    typeface (``<a:latin>``). PowerPoint consults a SEPARATE
    east-asian slot when laying out CJK code points; this helper
    fills it.
    """
    r_pr = run._r.get_or_add_rPr()
    existing = r_pr.find(qn("a:ea"))
    if existing is not None:
        r_pr.remove(existing)
    ea = r_pr.makeelement(qn("a:ea"), {"typeface": family}, nsmap=None)
    r_pr.append(ea)


def _decorate_with_accents(
    prs: Presentation, *, header_band: bool = True, cover_panel: bool = True
) -> None:
    """Place the accent shapes (cover left band, top bar on content slides).

    Idempotent: if the shapes already exist from a previous build pass
    (rare but possible in tests that re-run ``_build``), they're left in
    place — a name match suppresses re-add. The shapes are sent to the
    back of the slide's z-order so they sit BEHIND any text on the slide.

    ``header_band`` / ``cover_panel`` are a template config's ``[chrome]``:
    a template that brings its own header or cover artwork switches the
    exporter's off. A slide whose title sits in the template's title
    placeholder never gets the band, whatever the flag says, because the
    band is drawn for the exporter's own title position.
    """
    for index, slide in enumerate(prs.slides):
        if index == 0:
            if cover_panel:
                _add_cover_left_band(slide)
        elif header_band and not _title_is_placeholder(slide):
            _add_top_accent_bar(slide)


def _title_is_placeholder(slide) -> bool:
    return any(shape.name == "title" and shape.is_placeholder for shape in slide.shapes)


def _recolor_text_without_chrome(prs: Presentation, template: TemplateConfig) -> None:
    """Give light-on-navy text a dark colour where the navy was not drawn.

    The boundary this guards: titles are white because they sit on the navy
    header band, and the cover's text is white / near-white because it sits
    on the navy cover panel. With ``[chrome] header_band = false`` or
    ``cover_panel = false`` that navy is gone, and the same runs would be
    white on the template's light background, the light-on-light failure
    the deck-design contract names.

    Titles become ``_BRAND_DARK`` and the cover's secondary lines
    ``_BRAND_GREY``, both palette colours the dark-mode and template-palette
    passes know how to map.

    Example: with ``header_band = false`` a content slide's title run goes
    from ``#FFFFFF`` to ``#1F3A66``.
    """
    for index, slide in enumerate(prs.slides):
        if index == 0:
            if not template.cover_panel:
                _swap_run_colours(slide, {
                    _rgb_key(_HEADER_TITLE_FG): _BRAND_DARK,
                    _rgb_key(_DARK_BODY_TEXT): _BRAND_GREY,
                })
        elif not template.header_band:
            _swap_run_colours(
                slide, {_rgb_key(_HEADER_TITLE_FG): _BRAND_DARK}, only_named="title"
            )


def _swap_run_colours(slide, mapping: dict, *, only_named: str | None = None) -> None:
    for shape in slide.shapes:
        if not shape.has_text_frame or (only_named and shape.name != only_named):
            continue
        for run in _frame_runs(shape.text_frame):
            rgb = _explicit_run_rgb(run)
            new = mapping.get(_rgb_key(rgb)) if rgb is not None else None
            if new is not None:
                run.font.color.rgb = new


def _apply_template_palette(
    prs: Presentation, colors: dict[str, tuple[int, int, int]]
) -> None:
    """Swap the built-in palette for a template config's ``[colors]``.

    Same approach as the dark-mode pass, and for the same reason: the deck is
    built with the built-in palette, then recoloured by looking each colour
    up, so no builder has to know a template exists. ``primary`` replaces
    navy as text and as fill (header band, cover panel, table header and its
    rule), ``highlight`` the emphasis blue as text and as the accent rule,
    ``muted`` and ``subtle`` the two greys.

    Not applied in dark mode: see ``PptxExporter._build``.

    Example: ``{"primary": (11, 61, 46)}`` turns every navy run, the header
    band and the table header fill dark green, and leaves the blue alone.
    """
    originals = {
        "primary": _BRAND_DARK,
        "highlight": _BRAND_HIGHLIGHT,
        "muted": _BRAND_GREY,
        "subtle": _BRAND_LIGHT,
    }
    text_map = {_rgb_key(originals[key]): value for key, value in colors.items()}
    fill_map = {
        _rgb_key(originals[key]): value
        for key, value in colors.items()
        if key in ("primary", "highlight")
    }
    for slide in prs.slides:
        for shape in slide.shapes:
            _recolor_shape(shape, text_map=text_map, fill_map=fill_map, promote=None)


def _add_cover_left_band(slide) -> None:
    """Cover chrome — a full-bleed navy panel behind the centred white title.

    Kept under the name ``accent_left`` (the cover-band semantic name) even
    though it now spans the whole slide, so pptx_edit / audits that look up
    the cover accent by name still find it. Sent to back so the cover
    title / subtitle / meta (set to white / near-white in ``_add_cover_slide``)
    render on top of the navy.
    """
    if _has_named_shape(slide, "accent_left"):
        return
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Emu(0), Emu(0),
        _SLIDE_WIDTH, _SLIDE_HEIGHT,
    )
    shape.name = "accent_left"
    shape.line.fill.background()
    shape.fill.solid()
    shape.fill.fore_color.rgb = _BRAND_DARK
    _send_shape_to_back(shape, slide)


def _add_top_accent_bar(slide) -> None:
    """Content-slide chrome — the full-width navy header band plus a thin
    teal accent rule along its bottom edge.

    The band keeps the name ``accent_top`` (the content-slide accent
    semantic name) so edit tools / the deck-design audit still locate the
    top accent by name. Both shapes are sent to back so the white title
    placed by ``_new_section_slide`` renders on top of the band. The band
    fill (_BRAND_DARK) and blue rule fill (_BRAND_HIGHLIGHT) both have
    ``_LIGHT_TO_DARK_FILL`` entries, so dark mode lightens them rather than
    leaving them as-is.
    """
    if _has_named_shape(slide, "accent_top"):
        return
    band = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Emu(0), Emu(0),
        _SLIDE_WIDTH, _HEADER_BAND_HEIGHT,
    )
    band.name = "accent_top"
    band.line.fill.background()
    band.fill.solid()
    band.fill.fore_color.rgb = _BRAND_DARK
    _send_shape_to_back(band, slide)
    rule = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Emu(0), _HEADER_BAND_HEIGHT,
        _SLIDE_WIDTH, _ACCENT_RULE_HEIGHT,
    )
    rule.name = "accent_rule"
    rule.line.fill.background()
    rule.fill.solid()
    rule.fill.fore_color.rgb = _HEADER_ACCENT_FILL
    _send_shape_to_back(rule, slide)


def _has_named_shape(slide, name: str) -> bool:
    return any(shape.name == name for shape in slide.shapes)


def _send_shape_to_back(shape, slide) -> None:
    """Move ``shape`` to be the first child of ``spTree`` (= back of z-order)."""
    sp_tree = slide.shapes._spTree
    sp = shape._element
    sp_tree.remove(sp)
    # spTree's first two children are nvGrpSpPr + grpSpPr (group metadata);
    # everything after that is a shape in z-order. Insert at index 2 so the
    # band lands BEHIND every text shape but the metadata stays intact.
    sp_tree.insert(2, sp)


# ---------------------------------------------------------------------------
# Dark-mode pass (opt-in via ExportOptions.dark_mode)
# ---------------------------------------------------------------------------


def _apply_dark_mode(prs: Presentation) -> None:
    """Swap the light palette for the dark palette on every slide.

    The exporter builds the deck with the light palette unconditionally,
    then this post-pass re-colours individual shapes / runs / table cells
    by looking up their current RGB in the light→dark mapping. The
    approach is intentionally non-invasive — we don't refactor the 100+
    direct ``_BRAND_*`` references into a palette-aware lookup; instead
    we walk the rendered tree after the fact.

    Steps per slide:
    1. Solid-fill the slide background with ``_DARK_SLIDE_BG``.
    2. Walk every shape:
       - If it's a table, iterate the table's cells (fills + text + borders).
       - Otherwise recolour the shape's own fill + text frame.
    """
    for slide in prs.slides:
        _set_slide_background(slide, _DARK_SLIDE_BG)
        for shape in slide.shapes:
            _recolor_shape(shape)


def _set_slide_background(slide, colour: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = colour


def _recolor_shape(
    shape,
    *,
    text_map: dict | None = None,
    fill_map: dict | None = None,
    promote: RGBColor | None = _DARK_BODY_TEXT,
) -> None:
    """Single shape: swap its fill, text-run colours, and (if table) its
    per-cell fills + borders + cell-level runs.

    The maps default to the light-to-dark ones. ``_apply_template_palette``
    passes its own, with ``promote=None`` so a run without a colour is left
    alone (promoting it to near-white is right only on the dark slide).
    """
    text_map = _LIGHT_TO_DARK_TEXT if text_map is None else text_map
    fill_map = _LIGHT_TO_DARK_FILL if fill_map is None else fill_map
    if shape.has_table:
        for cell in _iter_table_cells(shape.table):
            _swap_fill(cell, fill_map)
            _swap_text_colors(cell, text_map, promote)
            _swap_cell_border_colors(cell, fill_map)
        return
    _swap_fill(shape, fill_map)
    if shape.has_text_frame:
        _swap_text_colors(shape, text_map, promote)


def _iter_table_cells(table):
    """python-pptx exposes ``iter_cells`` on Table but the API name has
    changed between versions; this wrapper falls through to the manual
    row/col iteration when needed."""
    iter_cells = getattr(table, "iter_cells", None)
    if iter_cells is not None:
        yield from iter_cells()
        return
    for row in table.rows:
        yield from row.cells


def _swap_fill(shape_or_cell, fill_map: dict | None = None) -> None:
    fill_map = _LIGHT_TO_DARK_FILL if fill_map is None else fill_map
    fill = getattr(shape_or_cell, "fill", None)
    if fill is None:
        return
    try:
        rgb = fill.fore_color.rgb
    except (AttributeError, ValueError, TypeError):
        return
    if rgb is None:
        return
    new = fill_map.get(_rgb_key(rgb))
    if new is None:
        return
    fill.solid()
    fill.fore_color.rgb = RGBColor(*new)


def _swap_text_colors(
    shape_or_cell,
    text_map: dict | None = None,
    promote: RGBColor | None = _DARK_BODY_TEXT,
) -> None:
    """Swap every run's text colour for the dark-mode equivalent.

    Safety net for runs that the builders forgot to colour explicitly:
    when ``font.color.rgb`` is ``None`` (theme inheritance, renders as
    near-black on screen) or pure black ``(0,0,0)``, promote to the
    dark-mode body colour ``#E5E7EB``. Without this fallback such runs
    would render as black-on-dark — invisible. See
    ``.claude/agents/rules/deck-design.md`` "Dark-mode contract".
    """
    text_map = _LIGHT_TO_DARK_TEXT if text_map is None else text_map
    text_frame = getattr(shape_or_cell, "text_frame", None)
    if text_frame is None:
        return
    for run in _frame_runs(text_frame):
        rgb = _explicit_run_rgb(run)
        if rgb is None or _rgb_key(rgb) == (0, 0, 0):
            if promote is not None:
                run.font.color.rgb = promote
            continue
        new = text_map.get(_rgb_key(rgb))
        if new is not None:
            run.font.color.rgb = RGBColor(*new)


def _swap_cell_border_colors(cell, fill_map: dict | None = None) -> None:
    """Walk the cell's ``<a:lnX>`` border elements and recolour any
    ``<a:srgbClr>`` whose value matches the light-palette divider /
    header-rule colours."""
    fill_map = _LIGHT_TO_DARK_FILL if fill_map is None else fill_map
    tc_pr = cell._tc.find(qn("a:tcPr"))
    if tc_pr is None:
        return
    for edge in ("L", "R", "T", "B"):
        ln = tc_pr.find(qn(f"a:ln{edge}"))
        if ln is None:
            continue
        solid = ln.find(qn("a:solidFill"))
        if solid is None:
            continue
        clr = solid.find(qn("a:srgbClr"))
        if clr is None:
            continue
        val = clr.get("val", "")
        if len(val) != 6:
            continue
        try:
            key = (int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16))
        except ValueError:
            continue
        new = fill_map.get(key)
        if new is None:
            continue
        clr.set("val", _rgb_hex(new))

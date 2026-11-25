"""Text on slides: boxes, bullets, math, tables, and how high they get.

Every helper that adds a run sets its colour explicitly, because a run without
one is invisible after the dark-mode pass.
"""

from __future__ import annotations

import re
import unicodedata

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import (
    MSO_ANCHOR,
    MSO_AUTO_SIZE,
    PP_ALIGN,
)
from pptx.oxml.ns import qn
from pptx.util import (
    Emu,
    Inches,
    Pt,
)

from thesisagents.core.models import Paper
from thesisagents.exporters.i18n import t
from thesisagents.exporters.pptx_style import (
    _BODY_PT,
    _BODY_WIDTH,
    _BRAND_DARK,
    _BRAND_GREY,
    _BRAND_HIGHLIGHT,
    _BRAND_LIGHT,
    _BRAND_RULE,
    _BULLET_MAX_CHARS,
    _BULLET_MAX_CHARS_COL,
    _BULLETS_PER_CELL_MAX,
    _FOOTER_HEIGHT,
    _FOOTER_PT,
    _FOOTER_Y,
    _HEADER_TITLE_FG,
    _MARGIN_X,
    _RQ_BOX_BORDER,
    _RQ_BOX_FILL,
    _SLIDE_WIDTH,
    _SUBHEAD_PT,
    _TABLE_DIVIDER,
    _TABLE_HEADER_FG,
    _TABLE_HEADER_FILL,
    _TABLE_HEADER_RULE,
    _TABLE_PT,
    _TABLE_ROW_ALT,
    _BuildContext,
    _rgb_hex,
)
from thesisagents.exporters.template import TITLE_AREA_BOTTOM

# ---------------------------------------------------------------------------
# Abstract segmentation (fallback when summary is absent / lightweight only)
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(
    r"\b(BACKGROUND|INTRODUCTION|MOTIVATION|OBJECTIVE[S]?|AIM[S]?|"
    r"METHOD[S]?|APPROACH|DESIGN|MATERIALS?|"
    r"RESULT[S]?|FINDINGS?|EVALUATION|"
    r"CONCLUSION[S]?|DISCUSSION|TAKEAWAYS?|IMPLICATIONS?|"
    r"LIMITATIONS?|FUTURE WORK)\s*:\s*",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_HEADER_KEYS = {
    "background": ("background", "introduction", "motivation"),
    "approach": (
        "objective", "objectives", "aim", "aims",
        "method", "methods", "approach", "design", "material", "materials",
    ),
    "results": (
        "result", "results", "finding", "findings", "evaluation",
        "conclusion", "conclusions", "discussion", "takeaway", "takeaways",
        "implication", "implications", "limitation", "limitations",
        "future work",
    ),
}


def _segment_abstract(abstract: str) -> dict[str, list[str]]:
    cleaned = " ".join((abstract or "").split())
    if not cleaned:
        return {"background": [], "approach": [], "results": []}
    labelled = _labelled_split(cleaned)
    if labelled is not None:
        return labelled
    return _equal_third_split(cleaned)


def _labelled_split(text: str) -> dict[str, list[str]] | None:
    matches = list(_LABEL_RE.finditer(text))
    if len(matches) < 2:
        return None
    buckets: dict[str, list[str]] = {"background": [], "approach": [], "results": []}
    for i, match in enumerate(matches):
        label = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip().rstrip(".")
        if not body:
            continue
        sentences = [s.strip() for s in _SENTENCE_RE.split(body) if s.strip()]
        target = _label_to_bucket(label)
        buckets[target].extend(sentences)
    if not any(buckets.values()):
        return None
    return buckets


def _label_to_bucket(label: str) -> str:
    for bucket_name, keys in _HEADER_KEYS.items():
        if label in keys:
            return bucket_name
    return "results"


def _equal_third_split(text: str) -> dict[str, list[str]]:
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return {"background": [text], "approach": [], "results": []}
    n = len(sentences)
    if n <= 2:
        return {"background": sentences, "approach": [], "results": []}
    third = max(1, n // 3)
    return {
        "background": sentences[:third],
        "approach": sentences[third : 2 * third],
        "results": sentences[2 * third :],
    }


#: The "<paper title> · Paper N of M" line on a lightweight content slide.
_CONTENT_META_PT = _BODY_PT - 4
_CONTENT_META_MIN_IN = 0.5
_CONTENT_META_MAX_LINES = 2
_CONTENT_META_GAP_IN = 0.1
#: Bottom edge of the content slide's body box, the same as before the meta
#: line became adaptive (top 2.1" + height 4.7").
_CONTENT_BODY_BOTTOM = Inches(6.8)
#: python-pptx's default top + bottom inner margin of a textbox (0.05" each).
_TEXTBOX_VERTICAL_MARGINS_IN = 0.1


def _content_meta_height_in(text: str) -> tuple[float, bool]:
    """Height (inches) of the content-slide meta box, and whether it overflows.

    The boundary this guards: a paper title long enough to wrap. The box was
    a fixed 0.5" (one line at 15 pt), so a 112-character title rendered at
    0.6" and failed the overflow check on every content slide of a
    lightweight deck (``progress.md`` #11). The height now follows the
    estimated wrapped line count, the inspector's own model, up to two
    lines. A title needing more than two lines (well over 200 characters)
    gets shrink-to-fit instead, because the body below has no more room.

    Example: a 40-character title gives ``(0.5, False)``, a 112-character
    one ``(0.6, False)``.
    """
    return _wrapped_box_height_in(
        text, font_pt=_CONTENT_META_PT,
        min_in=_CONTENT_META_MIN_IN, max_lines=_CONTENT_META_MAX_LINES,
    )


def _wrapped_box_height_in(
    text: str, *, font_pt: int, min_in: float, max_lines: int
) -> tuple[float, bool]:
    """Height (inches) of a full-width textbox for ``text``, and whether it overflows.

    Sized from the overflow inspector's wrapped-line estimate, never below
    ``min_in`` and never above ``max_lines`` lines. The second value is true
    when the text needs more than ``max_lines`` lines, in which case the
    caller turns on shrink-to-fit because the slide has no more room.

    Example: ``_wrapped_box_height_in("one line", font_pt=15, min_in=0.5,
    max_lines=2)`` gives ``(0.5, False)``.
    """
    lines = _estimate_wrapped_lines(text, width_in=Emu(_BODY_WIDTH).inches, font_pt=font_pt)
    shown = min(lines, max_lines)
    line_in = font_pt * 1.2 / 72
    height = max(min_in, shown * line_in + _TEXTBOX_VERTICAL_MARGINS_IN)
    return round(height, 3), lines > max_lines


def _sentences_to_bullets(sentences: list[str]) -> list[str]:
    """Whitespace-clean each sentence; do not truncate.

    Why no per-bullet ellipsis: a deck whose bullets read like
    "蒐集到 40…" is worse than a deck whose bullets wrap to two lines.
    Word wrap is on for every body box, so authors stay responsible for
    bullet length and the layout never silently mangles a sentence.
    """
    bullets: list[str] = []
    for sentence in sentences:
        stripped = " ".join(sentence.split()).rstrip(".")
        if stripped:
            bullets.append(stripped)
    return bullets


def _cap_bullets(
    bullets,
    max_count: int = _BULLETS_PER_CELL_MAX,
    max_chars: int = _BULLET_MAX_CHARS,  # kept for back-compat; ignored
    *,
    language: str = "en",
) -> list[str]:
    """Cap the *number* of bullets shown; never truncate a bullet's text.

    A trailing localised "(+N more)" marker (the ``more_items`` i18n key) calls
    out genuine overflow by count so authors notice they exceeded the cap,
    without silently chewing characters off a kept bullet. ``language`` selects
    the marker's locale so a zh-tw / ja deck never shows an English "(+N more)";
    it defaults to ``en`` for callers (e.g. height estimators) where the marker
    text is immaterial because only the line *count* matters.
    """
    del max_chars  # intentionally ignored; see docstring
    sliced = [" ".join(b.split()) for b in bullets[:max_count]]
    overflow = len(bullets) - len(sliced)
    if overflow > 0:
        sliced.append(t(language, "more_items", n=overflow))
    return sliced


def _clean(text: str) -> str:
    """Collapse runs of whitespace; never truncate.

    Why no truncation: a slide deck whose titles and subtitles end in
    ``…`` hides information from the reader without warning. We've left
    word-wrap on for every textbox, so long titles can wrap to a second
    line cleanly. Authors are responsible for keeping titles short
    enough to look good; the renderer never silently lops them off.
    """
    return " ".join((text or "").split())


def _add_paper_subtitle(slide, paper: Paper, ctx: _BuildContext) -> None:
    _ = ctx  # reserved for future per-language formatting
    # The right-hand element is the publication venue, NOT the fetcher.
    # ``paper.source`` is internal plumbing (arxiv / openalex / pubmed) and
    # only useful as a fallback when the source didn't fill ``venue`` in.
    publication = paper.venue or paper.source
    text = f"{_clean(paper.title)}  ·  {publication}"
    _add_textbox(
        slide, name="paper_subtitle", text=text,
        # Shared with the template contract: a template's title placeholder
        # must end above this line (template._check_title_placeholder).
        left=_MARGIN_X, top=TITLE_AREA_BOTTOM,
        width=_BODY_WIDTH, height=Inches(0.28),
        font_pt=_BODY_PT - 5, colour=_BRAND_GREY,
        shrink_to_fit=True,
    )


def _add_horizontal_rule(slide, *, top) -> None:
    from pptx.shapes.connector import Connector  # noqa: F401  # not used directly

    line = slide.shapes.add_connector(
        connector_type=1,  # straight
        begin_x=_MARGIN_X, begin_y=top,
        end_x=Emu(_SLIDE_WIDTH - _MARGIN_X), end_y=top,
    )
    line.line.color.rgb = _BRAND_RULE
    line.line.width = Pt(0.75)


# ---------------------------------------------------------------------------
# Inline math rendering. Authoring marks math with $...$; inside it, `_x` /
# `_{xy}` render as a real subscript and `^x` / `^{xy}` as a superscript (via
# the run's OOXML `baseline` attribute, since python-pptx has no Font.subscript),
# and a single-letter token (a variable like z / λ / I) is italicised while a
# multi-letter word (an operator like min / log / softmax) stays upright. See
# slide-deck-rules §12. Plain `_` outside `$...$` (file names, prose) is left
# alone — only $-delimited spans are parsed.
# ---------------------------------------------------------------------------
_SUBSCRIPT_BASELINE = -25000
_SUPERSCRIPT_BASELINE = 30000
#: Pandoc's rule for what is math: no space inside the dollars, and no digit
#: behind the closing one. An abstract that says "from $5 to $10" was read as
#: the formula "5 to" and lost both signs.
_MATH_DELIM = re.compile(r"\$(?=\S)([^$]+)(?<=\S)\$(?!\d)")


def _set_run_baseline(run, baseline: int) -> None:
    """Shift a run's baseline (1/1000 of a percent): negative = subscript,
    positive = superscript. python-pptx exposes no Font.subscript, so set the
    OOXML attribute on the run's character properties directly."""
    run._r.get_or_add_rPr().set("baseline", str(baseline))  # noqa: SLF001


def _add_math_run(
    paragraph, text: str, *, size_pt: int, colour: RGBColor,
    bold: bool, italic: bool = False, baseline: int = 0,
):
    """Append one styled run. Always sets an explicit colour (dark-mode
    contract — a run with ``color.rgb = None`` renders black on the dark slide
    and can't be swapped by the post-pass)."""
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = colour
    if baseline:
        _set_run_baseline(run, baseline)
    return run


def _math_tokens(span: str):
    """Tokenise an inline-math string into (kind, text): ``sub`` / ``sup`` for
    ``_x`` / ``_{xy}`` / ``^x`` / ``^{xy}``, ``word`` for a letter run, ``char``
    for anything else."""
    i, n = 0, len(span)
    while i < n:
        c = span[i]
        if c in "_^" and i + 1 < n:
            content, i = _script_operand(span, i + 1)
            yield ("sub" if c == "_" else "sup"), content
        elif c.isalpha():
            j = _letter_run_end(span, i)
            yield "word", span[i:j]
            i = j
        else:
            yield "char", c
            i += 1


def _script_operand(span: str, start: int) -> tuple[str, int]:
    """Read the sub/superscript operand that begins at ``span[start]``.

    Returns ``(operand, next_index)``. A ``{...}`` group yields everything
    inside the braces, a bare character yields just that character. Guards
    the unclosed brace: ``_{ab`` with no ``}`` takes the rest of the span
    instead of raising or looping. Examples: ``_script_operand("z_{ab}c", 2)
    == ("ab", 6)``, ``_script_operand("z_a", 2) == ("a", 3)``.
    """
    if span[start] != "{":
        return span[start], start + 1
    end = span.find("}", start)
    if end == -1:
        return span[start + 1:], len(span)
    return span[start + 1:end], end + 1


def _letter_run_end(span: str, start: int) -> int:
    """Index just past the run of letters that begins at ``span[start]``.

    A letter run is one math token: a single letter is an italic variable,
    a longer run (``min``, ``log``) an upright operator. Example:
    ``_letter_run_end("min(x)", 0) == 3``.
    """
    end = start
    while end < len(span) and span[end].isalpha():
        end += 1
    return end


def _render_math_span(paragraph, span: str, *, size_pt: int, colour: RGBColor, bold: bool) -> None:
    """Render one ``$...$`` inner string with real sub/superscripts and italic
    single-letter variables (multi-letter operators like ``min`` stay upright)."""
    common = {"size_pt": size_pt, "colour": colour, "bold": bold}
    for kind, text in _math_tokens(span):
        if kind == "sub":
            _add_math_run(paragraph, text, baseline=_SUBSCRIPT_BASELINE, **common)
        elif kind == "sup":
            _add_math_run(paragraph, text, baseline=_SUPERSCRIPT_BASELINE, **common)
        elif kind == "word":
            _add_math_run(paragraph, text, italic=(len(text) == 1), **common)
        else:
            _add_math_run(paragraph, text, **common)


def _render_math_paragraph(
    paragraph, text: str, *, size_pt: int, colour: RGBColor, bold: bool = False,
) -> None:
    """Fill ``paragraph`` with runs, rendering ``$...$`` spans as math. Plain
    text outside ``$...$`` becomes one run. Use instead of ``paragraph.text =
    ...`` wherever a string may contain math notation.

    Example: ``_render_math_paragraph(p, "loss $I(z_a;z_b)$", ...)`` yields
    "loss " + I(italic) + "(" + z(italic) + a(subscript) + ";" + … .
    """
    paragraph.clear()
    _append_math_runs(paragraph, text, size_pt=size_pt, colour=colour, bold=bold)
    if not paragraph.runs:
        _add_math_run(paragraph, "", size_pt=size_pt, colour=colour, bold=bold)


def _append_math_runs(
    paragraph, text: str, *, size_pt: int, colour: RGBColor, bold: bool = False,
) -> None:
    """Append math-aware runs for ``text`` to ``paragraph`` **without clearing
    it** — ``$...$`` spans render as math, plain segments as one run each. Use
    to add a math-aware value to a paragraph that already has runs (e.g. a KPI
    value after its grey label). A string with no ``$`` adds exactly one run."""
    pos = 0
    for m in _MATH_DELIM.finditer(text):
        if m.start() > pos:
            _add_math_run(paragraph, text[pos:m.start()], size_pt=size_pt, colour=colour, bold=bold)
        _render_math_span(paragraph, m.group(1), size_pt=size_pt, colour=colour, bold=bold)
        pos = m.end()
    if pos < len(text):
        _add_math_run(paragraph, text[pos:], size_pt=size_pt, colour=colour, bold=bold)


def _add_textbox(  # NOSONAR keyword-only box properties, regen scripts call it by name
    slide, *, name: str, text: str, left, top, width, height,
    font_pt: int, bold: bool = False, colour: RGBColor | None = None,
    align: PP_ALIGN | None = None,
    anchor: MSO_ANCHOR | None = None,
    shrink_to_fit: bool = False,
    math: bool = False,
) -> None:
    """Render a textbox.

    ``shrink_to_fit`` flips on PowerPoint's "Shrink text on overflow"
    auto-size (``MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE``). Use it on the
    title-area boxes so a long title that we now decline to truncate still
    gets rendered inside its allotted height — PowerPoint shrinks the font
    at open time rather than letting the text bleed past the horizontal
    rule.

    ``math`` routes the text through ``_render_math_paragraph`` so ``$...$``
    spans become real subscripts / superscripts + italic variables (see
    slide-deck-rules §12). Turn it on for content surfaces that carry math
    notation — contribution / method body paragraphs, callouts — so the
    feature actually fires there, not only in bullets / KPIs / table cells.
    A math run always needs an explicit colour for the dark-mode contract,
    so ``colour`` falls back to ``_BRAND_DARK`` when ``None``. The math path
    fills a single paragraph; its callers pass whitespace-collapsed,
    newline-free text, so multi-paragraph splitting is intentionally skipped.
    """
    box = slide.shapes.add_textbox(left, top, width, height)
    box.name = name
    text_frame = box.text_frame
    text_frame.word_wrap = True
    # Vertical anchor lets the header-band title sit visually centred within
    # the band's height instead of top-aligned against the band's top edge.
    if anchor is not None:
        text_frame.vertical_anchor = anchor
    if shrink_to_fit:
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    if math:
        paragraph = text_frame.paragraphs[0]
        if align is not None:
            paragraph.alignment = align
        _render_math_paragraph(
            paragraph, text, size_pt=font_pt, colour=colour or _BRAND_DARK, bold=bold
        )
        return
    text_frame.text = text
    for paragraph in text_frame.paragraphs:
        if align is not None:
            paragraph.alignment = align
        for run in paragraph.runs:
            run.font.size = Pt(font_pt)
            run.font.bold = bold
            if colour is not None:
                run.font.color.rgb = colour


def _add_bullet_box(
    slide, *, name: str, bullets: list[str], left, top, width, height, font_pt: int,
) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    box.name = name
    text_frame = box.text_frame
    text_frame.word_wrap = True
    if not bullets:
        text_frame.text = ""
        return
    for index, bullet in enumerate(bullets):
        paragraph = text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        paragraph.alignment = PP_ALIGN.LEFT
        # Render via _render_math_paragraph so $...$ spans become real
        # subscripts / superscripts + italic variables; a plain bullet is one
        # run. It sets an explicit _BRAND_DARK colour on every run (dark-mode
        # contract — a None-coloured run renders black on the dark slide and the
        # post-pass can't swap it). See deck-design.md "Dark-mode contract".
        _render_math_paragraph(paragraph, f"• {bullet}", size_pt=font_pt, colour=_BRAND_DARK)


def _add_footer(slide, text: str) -> None:
    _add_textbox(
        slide, name="footer", text=text,
        left=_MARGIN_X, top=_FOOTER_Y,
        width=_BODY_WIDTH - Inches(1.5), height=_FOOTER_HEIGHT,
        font_pt=_FOOTER_PT, colour=_BRAND_LIGHT,
    )


# Line-height of a body paragraph at single spacing (PowerPoint ≈ 1.2 × font).
_BODY_LINE_HEIGHT_IN = _BODY_PT * 1.2 / 72
_STACK_HEAD_HEIGHT_IN = 0.42
_STACK_GAP_IN = 0.05
_STACK_BODY_MIN_IN = 0.85
_STACK_BODY_PAD_IN = 0.06   # keep the box just taller than the rendered text
_TEXTBOX_SIDE_MARGIN_IN = 0.1  # python-pptx default left/right inner margin


def _strip_math_markup(text: str) -> str:
    """Reduce ``$...$`` math markup to its visible glyphs for length estimation:
    ``$I(z_a)$`` → ``I(za)``. The delimiters / sub-/superscript markers are not
    rendered as characters, so counting them would over-size the box."""
    cleaned = text.replace("$", "")
    cleaned = re.sub(r"[_^]\{([^}]*)\}", r"\1", cleaned)  # _{xy} / ^{xy} -> xy
    return re.sub(r"[_^](.)", r"\1", cleaned)              # _x / ^x -> x


def _estimate_wrapped_lines(text: str, *, width_in: float, font_pt: int) -> int:
    """Estimate wrapped line count for ``text`` in a box ``width_in`` wide.

    Mirrors ``scripts/check_overflow.py``'s estimator (full-width CJK ≈ 1.0 em,
    half-width Latin ≈ 0.55 em, wrap at the box's inner width) so a body box
    this sizes is one the overflow inspector agrees fits — the exporter and the
    inspector stay on one geometry contract instead of drifting apart.
    """
    inner_pt = max(0.1, width_in - 2 * _TEXTBOX_SIDE_MARGIN_IN) * 72
    line_w = 0.0
    lines = 1
    for ch in text:
        if ch == "\n":
            lines += 1
            line_w = 0.0
            continue
        em = 1.0 if unicodedata.east_asian_width(ch) in ("F", "W") else 0.55
        char_w = em * font_pt
        if line_w + char_w > inner_pt and line_w > 0:
            lines += 1
            line_w = char_w
        else:
            line_w += char_w
    return lines


def _stacked_body_height_in(body: str) -> float:
    """Body-box height (inches) needed for ``body``, adaptive to its wrapped
    line count so a 3-line contribution gets a 3-line box instead of spilling
    into the next subhead. Floors at ``_STACK_BODY_MIN_IN`` so a one-line body
    still has breathing room."""
    text = _strip_math_markup(" ".join((body or "").split()))
    # Length arithmetic returns a plain int (EMU), so re-wrap in Emu to read .inches.
    width_in = Emu(_BODY_WIDTH - Inches(0.2)).inches
    lines = _estimate_wrapped_lines(text, width_in=width_in, font_pt=_BODY_PT)
    return max(_STACK_BODY_MIN_IN, lines * _BODY_LINE_HEIGHT_IN + _STACK_BODY_PAD_IN)


def _stacked_section_height_in(body: str) -> float:
    """Total vertical span of one stacked section (head + body + gap), used by
    the height-aware paginator in ``_add_stacks_slide``."""
    return _STACK_HEAD_HEIGHT_IN + _stacked_body_height_in(body) + _STACK_GAP_IN


def _add_stacked_section(slide, heading: str, body: str, cursor) -> int:
    """Render an inline (heading bold + body grey) block; return next cursor Y.

    Body height is **adaptive** — sized to the body's estimated wrapped line
    count (see ``_stacked_body_height_in``) so a full-sentence contribution
    that needs three lines gets a three-line box rather than overflowing a
    fixed two-line one. Body text is not truncated — see ``_sentences_to_bullets``
    for the rationale. The caller (``_add_stacks_slide``) paginates by the same
    height estimate so the cumulative stack never crosses the footer guard.
    """
    head_height = Inches(_STACK_HEAD_HEIGHT_IN)
    body_height = Inches(_stacked_body_height_in(body))
    gap = Inches(_STACK_GAP_IN)
    _add_textbox(
        slide, name="subhead", text=_clean(heading),
        left=_MARGIN_X, top=cursor,
        width=_BODY_WIDTH, height=head_height,
        font_pt=_SUBHEAD_PT, bold=True, colour=_BRAND_DARK,
    )
    _add_textbox(
        slide, name="body", text=" ".join((body or "").split()),
        left=Inches(0.7), top=cursor + head_height,
        width=_BODY_WIDTH - Inches(0.2), height=body_height,
        font_pt=_BODY_PT, colour=_BRAND_GREY, math=True,
    )
    return cursor + head_height + body_height + gap


def _bullets_box_height_in(bullets, width_in: float) -> float:
    """Estimated height (inches) of a bullet box, adaptive to each bullet's
    wrapped line count rather than a flat per-bullet allowance. A long
    framework-feature bullet that wraps to two lines gets two lines of height
    instead of overflowing a fixed 0.5"/bullet box. Uses the same wrap model as
    the overflow inspector. Floors at 0.5" so a single short bullet still has
    breathing room."""
    total = 0.0
    for bullet in bullets:
        lines = _estimate_wrapped_lines(
            _strip_math_markup(f"• {bullet}"), width_in=width_in, font_pt=_BODY_PT
        )
        total += lines * _BODY_LINE_HEIGHT_IN + 0.06
    return max(0.5, total)


def _add_subsection(
    slide, heading: str, bullets, cursor, *, width, language: str = "en",
) -> int:
    head_height = Inches(0.5)
    # Subsection bullets — show up to 6 so authors don't lose detail.
    # Method/eval slides paginate at the section-list level, so 6 per
    # subsection won't push past the footer in the worst case.
    capped = _cap_bullets(bullets, max_count=6, language=language)
    bullet_height = Inches(_bullets_box_height_in(capped, Emu(width - Inches(0.2)).inches))
    _add_textbox(
        slide, name="subhead", text=_clean(heading),
        left=_MARGIN_X, top=cursor,
        width=width, height=head_height,
        font_pt=_SUBHEAD_PT, bold=True, colour=_BRAND_DARK,
    )
    _add_bullet_box(
        slide, name="body", bullets=capped,
        left=Inches(0.7), top=cursor + head_height,
        width=width - Inches(0.2), height=bullet_height,
        font_pt=_BODY_PT,
    )
    return cursor + head_height + bullet_height + Inches(0.25)


def _render_multi_column(
    slide, *, sections, left, top, width, height, columns: int = 2,
    language: str = "en",
) -> None:
    if not sections:
        return
    cols = columns
    col_w = (width - Inches(0.2 * (cols - 1))) / cols
    rows = (len(sections) + cols - 1) // cols
    if rows == 0:
        return
    row_h = height / rows
    for idx, (heading, bullets) in enumerate(sections):
        r, c = divmod(idx, cols)
        x = left + c * (col_w + Inches(0.2))
        y = top + r * row_h
        _add_textbox(
            slide, name="subhead", text=_clean(heading),
            left=x, top=y,
            width=col_w, height=Inches(0.5),
            font_pt=_SUBHEAD_PT, bold=True, colour=_BRAND_DARK,
        )
        _add_bullet_box(
            slide, name="body",
            bullets=_cap_bullets(
                bullets, max_chars=_BULLET_MAX_CHARS_COL, language=language,
            ),
            left=x, top=y + Inches(0.55),
            width=col_w, height=row_h - Inches(0.65),
            font_pt=_BODY_PT,
        )


def _add_rq_callout(
    slide, text: str, *, left, top, width, height, highlight: bool = False
) -> None:
    """A boxed highlight: filled rectangle + bold text on top.

    ``highlight=False`` (default) is the light off-white RQ-question box
    (navy text + navy border) used for research-question callouts.
    ``highlight=True`` is the **filled takeaway box** — solid navy fill +
    white text, no border — reserved for the single core-observation /
    key-finding slide so the deck's one "punch line" reads as a filled
    panel that mirrors the navy header band, not as just another light box.
    Both fill RGBs (``_BRAND_DARK`` navy, ``_RQ_BOX_FILL`` off-white) have
    ``_LIGHT_TO_DARK_FILL`` entries, so dark mode recolours them and the
    text stays readable in both modes.
    """

    rect = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    rect.name = "rq_box"
    rect.fill.solid()
    if highlight:
        rect.fill.fore_color.rgb = _BRAND_DARK
        rect.line.fill.background()
        text_colour = _HEADER_TITLE_FG
    else:
        rect.fill.fore_color.rgb = _RQ_BOX_FILL
        rect.line.color.rgb = _RQ_BOX_BORDER
        rect.line.width = Pt(1.0)
        text_colour = _BRAND_DARK
    rect.text_frame.word_wrap = True
    rect.text_frame.margin_left = Inches(0.2)
    rect.text_frame.margin_right = Inches(0.2)
    rect.text_frame.margin_top = Inches(0.1)
    rect.text_frame.margin_bottom = Inches(0.1)
    # Math-aware: an RQ / core-observation callout often states the paper's
    # objective formula (e.g. "$I(z_a;z_b|E_p)$"), so render $...$ spans as real
    # subscripts rather than flat ASCII (slide-deck-rules §12).
    _render_math_paragraph(
        rect.text_frame.paragraphs[0], text,
        size_pt=_BODY_PT, colour=text_colour, bold=True,
    )


def _add_kpi_lines(
    slide, metrics, ctx: _BuildContext, *, left, top, width, height,
) -> None:
    """Each metric → one paragraph in a textbox: `Label: VALUE (baseline X)`."""
    box = slide.shapes.add_textbox(left, top, width, height)
    box.name = "kpi"
    text_frame = box.text_frame
    text_frame.word_wrap = True
    text_frame.text = ""
    baseline_label = t(ctx.language, "label_baseline")
    for index, (label, value, baseline) in enumerate(metrics):
        paragraph = (
            text_frame.paragraphs[0] if index == 0 else text_frame.add_paragraph()
        )
        paragraph.text = ""
        run_label = paragraph.add_run()
        run_label.text = f"• {label}: "
        run_label.font.size = Pt(_BODY_PT)
        run_label.font.color.rgb = _BRAND_GREY
        # Value runs are math-aware ($...$ -> real sub/superscripts), so a KPI
        # like "$λ_max$=0.1" renders with a real subscript, while a plain
        # "78% F1" stays one upright run (no $, so the "F" isn't italic-ised).
        # Teal accent: KPI numbers are the slide's punch line (a 2.3x speedup,
        # a 78% F1, etc.). Bold + teal makes them pop without red, which would
        # read as error/warning. See deck-design.md "No red text" contract.
        _append_math_runs(
            paragraph, str(value),
            size_pt=_BODY_PT + 2, colour=_BRAND_HIGHLIGHT, bold=True,
        )
        if baseline:
            run_base = paragraph.add_run()
            run_base.text = f"   ({baseline_label}: {baseline})"
            run_base.font.size = Pt(_BODY_PT - 2)
            run_base.font.color.rgb = _BRAND_LIGHT


def _add_table(
    slide, *, rows, left, top, width, height, col_widths,
) -> None:
    """Render a clean academic-style table.

    Styling rules (mirror published thesis-defence decks, not the default
    PowerPoint table look):

    * No default black grid lines — every cell border is set to noFill
      first, then specific rules are added back where they help readability.
    * Header row: navy fill, white bold text, with a thick (1.5pt) navy
      bottom rule below it for emphasis (the rule sits in the data row's
      top edge, not the header's bottom, so it doesn't double up).
    * Data rows: alternate very-light-blue / white background; thin
      (0.5pt) grey-blue rule between adjacent data rows.
    * Cell vertical alignment: middle, so short labels and longer
      descriptions in the same row sit on a shared baseline.
    * First column of body rows: bold, slightly emphasised — most tables
      in this project use the leftmost cell as a row label.

    Rows are rectangularised before anything is drawn (see
    ``_rectangular_rows``) because ragged input used to crash the render.
    """
    grid = _rectangular_rows(rows)
    if not grid:
        return
    row_count = len(grid)
    col_count = len(grid[0])
    table_shape = slide.shapes.add_table(
        rows=row_count, cols=col_count, left=left, top=top, width=width, height=height,
    )
    table = table_shape.table
    # Widths beyond the real column count would IndexError on
    # ``table.columns[i]``; widths short of it leave python-pptx's own even
    # split in place, which is the right fallback for an extra column.
    for col_index, w in enumerate(col_widths):
        if col_index >= col_count:
            break
        table.columns[col_index].width = w
    for r, row_values in enumerate(grid):
        for c, value in enumerate(row_values):
            _style_table_cell(table.cell(r, c), str(value), r, c)


def _rectangular_rows(rows) -> list[tuple[str, ...]]:
    """Pad every row out to the widest row's column count.

    Why this guard exists: ``_add_table`` sizes the PowerPoint table from the
    header row, then writes cell ``(r, c)`` for each supplied value. A body row
    with MORE cells than the header — trivially easy to produce in a
    hand-authored ``scripts/regen_*.py``, which is this project's documented
    LLM-as-agent path for rich ``PaperSummary`` tables — walked off the end of
    ``table.columns`` and aborted the whole deck with a bare
    ``IndexError: list index out of range``. Padding keeps every authored cell
    on the slide and never drops content.

    Example: ``_rectangular_rows([("Technique", "Role"), ("MoE", "routing",
    "2024")])`` returns a 3-column grid whose header gains one empty cell.

    Anti-pattern: silently truncating the long row to the header's width —
    that ships a deck missing a column the author wrote, with no error.
    """
    grid = [tuple(row) for row in (rows or ()) if row is not None]
    if not grid:
        return []
    width = max(len(row) for row in grid)
    if width == 0:
        return []
    return [row + ("",) * (width - len(row)) for row in grid]


def _style_table_cell(cell, value: str, r: int, c: int) -> None:
    """Apply academic-style formatting to one cell.

    Split out from ``_add_table`` so the cognitive-complexity budget
    fits — borders + fills + font + alignment all live here.
    """
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    text_frame = cell.text_frame
    text_frame.word_wrap = True
    text_frame.margin_left = Inches(0.1)
    text_frame.margin_right = Inches(0.1)
    text_frame.margin_top = Inches(0.05)
    text_frame.margin_bottom = Inches(0.05)
    # Cell text style by position: the header row is bold on the header FG, data
    # rows are _BRAND_DARK with the row-label column (c == 0) slightly heavier.
    if r == 0:
        cell_colour, cell_bold = _TABLE_HEADER_FG, True
    else:
        cell_colour, cell_bold = _BRAND_DARK, (c == 0)
    # Math-aware so a comparison-table cell like "$z_a$" or "O($n^2$)" renders
    # real sub/superscripts; a plain cell is one run, exactly as before. Split
    # on \n so a multi-line cell keeps its paragraphs (cell.text used to do this).
    for line_index, line in enumerate(value.split("\n")):
        paragraph = (
            text_frame.paragraphs[0] if line_index == 0 else text_frame.add_paragraph()
        )
        _render_math_paragraph(
            paragraph, line, size_pt=_TABLE_PT, colour=cell_colour, bold=cell_bold,
        )
    _set_cell_fill(cell, r)
    _clear_cell_borders(cell)
    if r == 1:
        # Heavy rule below the header — drawn as the data row's TOP
        # border so the visual width adds up cleanly.
        _set_cell_border(cell, "T", Pt(1.5), _TABLE_HEADER_RULE)
    elif r > 1:
        # Thin separator between adjacent data rows.
        _set_cell_border(cell, "T", Pt(0.5), _TABLE_DIVIDER)


def _set_cell_fill(cell, r: int) -> None:
    cell.fill.solid()
    if r == 0:
        cell.fill.fore_color.rgb = _TABLE_HEADER_FILL
    elif r % 2 == 0:
        cell.fill.fore_color.rgb = _TABLE_ROW_ALT
    else:
        cell.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _clear_cell_borders(cell) -> None:
    """Set every edge of ``cell`` to noFill so the table style's default
    grid lines disappear. The XML structure for a cell's border is
    ``<a:tcPr>/<a:lnX>/<a:noFill/>`` where X ∈ {L, R, T, B}.
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    for edge in ("L", "R", "T", "B"):
        tag = qn(f"a:ln{edge}")
        existing = tc_pr.find(tag)
        if existing is not None:
            tc_pr.remove(existing)
        ln = tc_pr.makeelement(tag, {"w": "0"}, nsmap=None)
        ln.append(ln.makeelement(qn("a:noFill"), {}, nsmap=None))
        tc_pr.append(ln)


def _set_cell_border(cell, edge: str, width, colour: RGBColor) -> None:
    """Add a solid-fill border on one edge of ``cell``.

    ``edge`` must be one of L / R / T / B; ``width`` is a ``pptx.util.Pt``
    (or any EMU-aware value). Replaces an existing border on that edge.
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    tag = qn(f"a:ln{edge}")
    existing = tc_pr.find(tag)
    if existing is not None:
        tc_pr.remove(existing)
    ln = tc_pr.makeelement(
        tag,
        {"w": str(int(width)), "cap": "flat", "cmpd": "sng", "algn": "ctr"},
        nsmap=None,
    )
    solid = ln.makeelement(qn("a:solidFill"), {}, nsmap=None)
    solid.append(solid.makeelement(qn("a:srgbClr"), {"val": _rgb_hex(colour)}, nsmap=None))
    ln.append(solid)
    ln.append(ln.makeelement(qn("a:prstDash"), {"val": "solid"}, nsmap=None))
    ln.append(ln.makeelement(qn("a:round"), {}, nsmap=None))
    tc_pr.append(ln)


def _equal_col_widths(total: Emu, cols: int) -> tuple[Emu, ...]:
    each = total // cols
    return tuple(each for _ in range(cols))

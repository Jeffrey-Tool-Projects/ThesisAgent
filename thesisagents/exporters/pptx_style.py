"""Measures, colours and fonts of the deck, and the context every builder gets.

The palette rules (dark-mode contract, no red text, light on light) are in the
``deck-design`` subagent. A light fill added here needs its dark counterpart in
``_LIGHT_TO_DARK_FILL``.
"""

from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.util import Inches

# ---------------------------------------------------------------------------
# Layout constants (16:9 widescreen)
# ---------------------------------------------------------------------------

_SLIDE_WIDTH = Inches(13.333)
_SLIDE_HEIGHT = Inches(7.5)

_MARGIN_X = Inches(0.5)
_BODY_WIDTH = Inches(12.333)            # SLIDE_WIDTH - 2*MARGIN
_TITLE_TOP = Inches(0.3)
_TITLE_HEIGHT = Inches(1.0)             # tall enough for a wrapped 2-line title at 30pt
_RULE_TOP = Inches(1.35)
_BODY_TOP = Inches(1.5)
_BODY_HEIGHT = Inches(5.4)
_FOOTER_Y = Inches(7.05)
_FOOTER_HEIGHT = Inches(0.3)
_PAGE_NUMBER_X = Inches(12.0)
_PAGE_NUMBER_WIDTH = Inches(1.2)

# Cover-slide specific (centered block)
_COVER_TITLE_TOP = Inches(1.6)
_COVER_TITLE_HEIGHT = Inches(1.6)
_COVER_SUBTITLE_TOP = Inches(3.3)
_COVER_SUBTITLE_HEIGHT = Inches(1.0)
_COVER_META_TOP = Inches(4.7)
_COVER_META_HEIGHT = Inches(1.6)

# Type sizes — calibrated so a 60-char Chinese bullet fits one wrapped line
# at body width 12.3" in 16:9, with comfortable line height.
_COVER_TITLE_PT = 44
_COVER_SUBTITLE_PT = 24
_COVER_META_PT = 18
_SECTION_TITLE_PT = 30
_SUBHEAD_PT = 22
_BODY_PT = 19
_TABLE_PT = 14
_FOOTER_PT = 10

# Kept for callers of ``_cap_bullets`` whose signature still accepts a
# (now-ignored) ``max_chars`` parameter. Slides rely on word_wrap rather
# than character-level truncation; see ``_clean`` / ``_sentences_to_bullets``.
_BULLET_MAX_CHARS = 60
_BULLET_MAX_CHARS_COL = 28

# Content-density caps to keep one slide from overflowing.
_BULLETS_PER_CELL_MAX = 6      # multi-column / quadrant cells; raised
                                # from 3 so authors don't lose substance
                                # to silent drops.
_METHOD_SECTIONS_PER_SLIDE = 2
_EVALUATION_SECTIONS_PER_SLIDE = 2
_REFERENCES_PER_SLIDE = 8       # split long bib lists across slides

# Colours (mirror the reference deck's palette)
_BRAND_DARK = RGBColor(0x1F, 0x3A, 0x66)
#: WARNING — DO NOT use _BRAND_ACCENT as a TEXT colour.
#: Red text in slide decks is consistently associated with errors,
#: warnings, and AI-generated KPI emphasis ("look at this number!").
#: The project bans red font runs entirely; use _BRAND_HIGHLIGHT (blue)
#: for emphasis instead. The constant is kept around in case a future
#: non-text accent shape (sparkline, badge, etc.) needs it, but every
#: existing TEXT callsite has been migrated to _BRAND_HIGHLIGHT.
#: See .claude/agents/rules/deck-design.md "No red text" contract.
_BRAND_ACCENT = RGBColor(0xC0, 0x39, 0x2B)
#: Emphasis text colour — academic blue-600 (#2563EB). Replaces the banned
#: red _BRAND_ACCENT for KPI values, RQ question callouts, figure
#: captions, and other "this stands out" use cases. Pairs well with
#: bold; sits in the same blue family as _BRAND_DARK navy for a cohesive
#: white + blue academic-paper look (not a competing hue). Dark-mode pass
#: swaps to blue-400 (#60A5FA) via _LIGHT_TO_DARK_TEXT.
_BRAND_HIGHLIGHT = RGBColor(0x25, 0x63, 0xEB)
_BRAND_GREY = RGBColor(0x55, 0x55, 0x55)
_BRAND_LIGHT = RGBColor(0xAA, 0xAA, 0xAA)

# Per-language typography. (latin_family, east_asian_family). The Latin
# family also covers Cyrillic / Greek / Devanagari via Inter; the
# east-asian slot is what PowerPoint consults for CJK code points, so
# leaving it `None` would let PowerPoint pick a default that doesn't
# match the Latin choice. See ``deck-design`` agent doc for the
# full rationale. Inter degrades gracefully to Calibri on hosts without
# Inter installed.
_FONT_FAMILIES: dict[str, tuple[str, str | None]] = {
    "en":     ("Inter", None),
    "es":     ("Inter", None),
    "fr":     ("Inter", None),
    "de":     ("Inter", None),
    "pt":     ("Inter", None),
    "it":     ("Inter", None),
    "vi":     ("Inter", None),
    "id":     ("Inter", None),
    "ru":     ("Inter", None),
    "hi":     ("Inter", "Nirmala UI"),
    "zh-tw":  ("Inter", "Microsoft JhengHei UI"),
    "zh-cn":  ("Inter", "Microsoft YaHei UI"),
    "ja":     ("Inter", "Yu Gothic UI"),
    "ko":     ("Inter", "Malgun Gothic"),
}
_DEFAULT_FONT_FAMILY: tuple[str, str | None] = ("Inter", None)

# Accent geometry — the deck's signature chrome.
#
# Why a band, not a thin bar: a full-width filled navy header band with a
# white title (and a thin teal accent rule along its bottom edge) is what
# makes every content slide read as "designed for a defence" rather than a
# blank layout with a hairline at the top. _BODY_TOP (1.5") already sits
# below _HEADER_BAND_HEIGHT (1.18") so body content never collides with the
# band — no body-position constants need to move.
_HEADER_BAND_HEIGHT = Inches(1.18)
_ACCENT_RULE_HEIGHT = Inches(0.06)
# Legacy cover left-band width; the cover is now a full-bleed navy panel
# (see _add_cover_left_band) but the constant is kept for any external ref.
_ACCENT_LEFT_WIDTH = Inches(0.4)
# Title text sits ON the navy band / navy cover, so it must be white —
# navy _BRAND_DARK on the navy band would be navy-on-navy (invisible).
# White-on-navy is already the established pattern for table headers
# (_TABLE_HEADER_FG), so this reuses that idea rather than adding a hue.
_HEADER_TITLE_FG = RGBColor(0xFF, 0xFF, 0xFF)
# The under-band accent rule + cover accent use the brand blue. It is a
# non-text shape, so the "blue is for emphasis TEXT only" split does not
# bind it; staying on-palette keeps the four-colour discipline.
_HEADER_ACCENT_FILL = _BRAND_HIGHLIGHT

# Dark-mode palette (post-build recolour, opt-in via
# ``ExportOptions.dark_mode``).
_DARK_SLIDE_BG = RGBColor(0x12, 0x15, 0x1B)
# Near-white body-text colour for dark mode. The post-build recolour pass
# promotes any run lacking an explicit colour (theme inheritance → renders
# black on the dark slide) to this, and it's the swap target for _BRAND_DARK
# body text in _LIGHT_TO_DARK_TEXT below. Named so the value lives in one place.
_DARK_BODY_TEXT = RGBColor(0xE5, 0xE7, 0xEB)

# Light-palette RGB → dark-palette RGB mapping for TEXT colours. Keys
# are 3-tuples (R, G, B) since python-pptx's RGBColor is tuple-comparable
# but we want to match by raw int components.
_LIGHT_TO_DARK_TEXT: dict[tuple[int, int, int], tuple[int, int, int]] = {
    (0x1F, 0x3A, 0x66): (0xE5, 0xE7, 0xEB),  # _BRAND_DARK      → near-white text
    (0x55, 0x55, 0x55): (0x9C, 0xA3, 0xAF),  # _BRAND_GREY      → mid grey
    (0xAA, 0xAA, 0xAA): (0x6B, 0x72, 0x80),  # _BRAND_LIGHT     → muted grey
    (0x25, 0x63, 0xEB): (0x60, 0xA5, 0xFA),  # _BRAND_HIGHLIGHT → bright blue-400
    # _BRAND_ACCENT (#C0392B) intentionally NOT mapped — red text was
    # banned per the deck-design "No red text" contract, and the
    # `test_pptx_no_red_text_runs` regression test fails if any run
    # ever writes that colour. If a run shows up with it the test
    # catches it BEFORE we reach this swap layer.
}

# Light-palette RGB → dark-palette RGB mapping for SHAPE / CELL FILLS
# and cell-border lines. Keeps the navy header on tables but lightens
# its tone slightly so it reads against the dark slide background.
_LIGHT_TO_DARK_FILL: dict[tuple[int, int, int], tuple[int, int, int]] = {
    # _BRAND_DARK accent bars + accent_left + table header fill
    (0x1F, 0x3A, 0x66): (0x3B, 0x5A, 0xA0),
    # _TABLE_ROW_ALT → dark row stripe
    (0xF4, 0xF6, 0xF9): (0x1F, 0x23, 0x2C),
    # Pure white table rows → near-black
    (0xFF, 0xFF, 0xFF): (0x16, 0x1A, 0x22),
    # _TABLE_DIVIDER → muted grey-blue rule
    (0xD0, 0xD7, 0xE2): (0x3D, 0x44, 0x52),
    # _RQ_BOX_FILL (research-question callout box) → dark navy tint.
    # Without this swap the box stays near-white while the text inside
    # is re-coloured to near-white = white-on-white = invisible. This
    # specific bug is what the dark-mode contrast contract guards.
    (0xF3, 0xF6, 0xFA): (0x1E, 0x26, 0x38),
    # _HEADER_ACCENT_FILL / blue callout fill (_BRAND_HIGHLIGHT, #2563EB) →
    # brighter blue-400 so the under-band accent rule and any blue-filled
    # callout read on the dark slide, mirroring how blue emphasis TEXT
    # swaps in _LIGHT_TO_DARK_TEXT.
    (0x25, 0x63, 0xEB): (0x60, 0xA5, 0xFA),
}
_BRAND_RULE = RGBColor(0xCC, 0xCC, 0xCC)
_RQ_BOX_FILL = RGBColor(0xF3, 0xF6, 0xFA)
_RQ_BOX_BORDER = RGBColor(0x1F, 0x3A, 0x66)
_TABLE_HEADER_FILL = RGBColor(0x1F, 0x3A, 0x66)
_TABLE_HEADER_FG = RGBColor(0xFF, 0xFF, 0xFF)
_TABLE_ROW_ALT = RGBColor(0xF4, 0xF6, 0xF9)
_TABLE_DIVIDER = RGBColor(0xD0, 0xD7, 0xE2)  # row divider — soft grey-blue
_TABLE_HEADER_RULE = RGBColor(0x1F, 0x3A, 0x66)  # heavy nav rule under header


def _rgb_key(rgb) -> tuple[int, int, int]:
    """An RGBColor as a hashable ``(r, g, b)`` int tuple — the key type the
    light→dark palette maps above are indexed by. Centralises the
    ``(int(rgb[0]), int(rgb[1]), int(rgb[2]))`` idiom used by every swap pass."""
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _rgb_hex(rgb) -> str:
    """6-char uppercase hex (no ``#``) for an RGBColor or ``(r, g, b)`` tuple —
    the form OOXML's ``<a:srgbClr val=...>`` attribute expects."""
    return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


# ---------------------------------------------------------------------------
# Build context
# ---------------------------------------------------------------------------


class _BuildContext:
    __slots__ = ("language", "include_abstract", "_page_total")

    def __init__(self, language: str, include_abstract: bool) -> None:
        self.language = language
        self.include_abstract = include_abstract
        self._page_total = 0

    def set_page_total(self, total: int) -> None:
        self._page_total = total

    @property
    def page_total(self) -> int:
        return self._page_total

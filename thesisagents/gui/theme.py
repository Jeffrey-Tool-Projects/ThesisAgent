"""Design tokens (styles x light / dark) and the application stylesheet.

The boundary this module guards: every colour and corner radius the desktop
UI paints comes from one :class:`Palette`, so a page never hard-codes a hex
value that would be unreadable in the other theme, or a radius that belongs
to one style only. Before this module the window used the platform's default
widgets with no stylesheet, which on Windows looked like a 2010 dialog and
ignored the system's dark mode entirely.

Two independent choices pick the palette:

* **Style** (QSettings key ``ui/style``) is the visual language:

  * ``"classic"`` (the default): a navy sidebar and white bordered cards, in
    the colours of the exported decks.
  * ``"material"``: Material 3 (Google's design system): tonal surfaces from
    one blue seed colour, a pill-shaped indicator on the active sidebar
    entry, borderless filled cards, fully rounded buttons.

* **Theme** (QSettings key ``ui/theme``) is light or dark:

  * ``"system"`` (the default) follows the operating system's colour scheme
    and keeps following it when the user flips it while the app is open.
  * ``"light"`` and ``"dark"`` pin one variant.

The GUI theme is independent of the slide-deck dark mode (the Deck page's
*Dark mode* checkbox): one is how the app looks, the other how the exported
``.pptx`` looks.

Example::

    from thesisagents.gui.theme import apply_theme
    apply_theme(app, "system", "material")   # at boot, again whenever Settings saves
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from thesisagents.gui.font_size import font_scale
from thesisagents.gui.icons import write_glyph

THEME_SYSTEM: Final[str] = "system"
THEME_LIGHT: Final[str] = "light"
THEME_DARK: Final[str] = "dark"
#: Every valid value of the ``ui/theme`` setting, in the order the Settings
#: page lists them.
THEME_CHOICES: Final[tuple[str, ...]] = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

STYLE_CLASSIC: Final[str] = "classic"
STYLE_MATERIAL: Final[str] = "material"
#: Every valid value of the ``ui/style`` setting, in the order the Settings
#: page lists them.
STYLE_CHOICES: Final[tuple[str, ...]] = (STYLE_CLASSIC, STYLE_MATERIAL)


@dataclass(frozen=True)
class Shape:
    """The geometry half of a style: radii, padding and type weights.

    Kept apart from the colours because light and dark of one style share
    it. Radii and padding are pixels, weights CSS font weights.
    """

    card_radius: int
    card_border: bool
    input_radius: int
    input_padding: str
    button_radius: int
    button_padding: str
    check_radius: int
    nav_radius: int
    nav_padding: str
    title_size_pt: int
    title_weight: int
    card_title_weight: int


CLASSIC_SHAPE: Final[Shape] = Shape(
    card_radius=10,
    card_border=True,
    input_radius=6,
    input_padding="5px 8px",
    button_radius=6,
    button_padding="6px 14px",
    check_radius=4,
    nav_radius=8,
    nav_padding="9px 10px",
    title_size_pt=18,
    title_weight=700,
    card_title_weight=700,
)

#: Material 3 shape scale: medium (12 px) cards, extra-small (4 px) text
#: fields, full (pill) buttons and navigation indicators, regular-weight
#: headlines.
MATERIAL_SHAPE: Final[Shape] = Shape(
    card_radius=12,
    card_border=False,
    input_radius=4,
    input_padding="7px 12px",
    button_radius=18,
    button_padding="7px 22px",
    check_radius=2,
    nav_radius=20,
    nav_padding="10px 16px",
    title_size_pt=20,
    title_weight=400,
    # Material's title-medium is weight 500, but Segoe UI has no Medium face
    # and Microsoft JhengHei / YaHei no Semibold, so Qt falls back to
    # Regular for both. Bold is the weight every script renders.
    card_title_weight=700,
)


@dataclass(frozen=True)
class Palette:
    """The colour tokens of one style in light or dark, as ``#RRGGBB`` strings.

    ``window`` is the page background, ``surface`` the card fill drawn on it,
    ``nav`` the sidebar. ``accent`` is the primary-button and selection colour
    (in the classic style the deck's ``_BRAND_HIGHLIGHT`` blue, its dark-mode
    swap ``#60A5FA`` in dark, so the app and its decks share one accent).
    ``muted`` is secondary text (subtitles, placeholders, status lines).
    ``button*`` colour the secondary buttons: bordered white in classic,
    a borderless tonal fill in Material. ``input_border`` outlines text
    fields. ``name`` is unique across every style and variant.
    """

    name: str
    style: str
    dark: bool
    window: str
    surface: str
    surface_alt: str
    border: str
    input_border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    on_accent: str
    button: str
    button_border: str
    button_hover: str
    button_hover_border: str
    nav: str
    nav_text: str
    nav_muted: str
    nav_active: str
    selection: str
    shape: Shape = CLASSIC_SHAPE


LIGHT: Final[Palette] = Palette(
    name=THEME_LIGHT,
    style=STYLE_CLASSIC,
    dark=False,
    window="#F4F6FA",
    surface="#FFFFFF",
    surface_alt="#F8FAFC",
    border="#DDE3EC",
    input_border="#DDE3EC",
    text="#0F172A",
    muted="#5B6678",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    on_accent="#FFFFFF",
    button="#FFFFFF",
    button_border="#DDE3EC",
    button_hover="#FFFFFF",
    button_hover_border="#2563EB",
    # The deck's navy (_BRAND_DARK #1F3A66), so the sidebar and the
    # exported cover share one identity colour.
    nav="#1F3A66",
    nav_text="#FFFFFF",
    nav_muted="#B7C4DB",
    nav_active="#2E4F85",
    selection="#DBE7FE",
)

DARK: Final[Palette] = Palette(
    name=THEME_DARK,
    style=STYLE_CLASSIC,
    dark=True,
    window="#12151B",
    surface="#1A1E26",
    surface_alt="#151920",
    border="#2C3340",
    input_border="#2C3340",
    text="#E5E7EB",
    muted="#9AA3B2",
    accent="#60A5FA",
    accent_hover="#93C5FD",
    on_accent="#0B1220",
    button="#1A1E26",
    button_border="#2C3340",
    button_hover="#1A1E26",
    button_hover_border="#60A5FA",
    nav="#0C0F14",
    nav_text="#E5E7EB",
    nav_muted="#8B95A7",
    nav_active="#1E2633",
    selection="#1E3A5F",
)

# Material 3 schemes generated from one blue seed (the Material Theme
# Builder's tonal palettes): window = surface, cards = surface-container,
# alternating rows = surface-container-high (light) / -low (dark), borders =
# outline-variant, text fields = outline, secondary buttons and the active
# navigation pill = secondary-container. Hover colours are the container with
# Material's 8 % state layer of its on-colour already blended in.
MATERIAL_LIGHT: Final[Palette] = Palette(
    name="material-light",
    style=STYLE_MATERIAL,
    dark=False,
    window="#F9F9FF",
    surface="#EDEDF4",
    surface_alt="#E7E8EE",
    border="#C4C6D0",
    input_border="#74777F",
    text="#191C20",
    muted="#44474E",
    accent="#415F91",
    accent_hover="#526F9E",
    on_accent="#FFFFFF",
    button="#DAE2F9",
    button_border="#DAE2F9",
    button_hover="#CBD3E9",
    button_hover_border="#CBD3E9",
    nav="#F3F3FA",
    nav_text="#191C20",
    nav_muted="#44474E",
    nav_active="#DAE2F9",
    selection="#D6E3FF",
    shape=MATERIAL_SHAPE,
)

MATERIAL_DARK: Final[Palette] = Palette(
    name="material-dark",
    style=STYLE_MATERIAL,
    dark=True,
    window="#111318",
    surface="#1D2024",
    surface_alt="#191C20",
    border="#44474E",
    input_border="#8E9099",
    text="#E2E2E9",
    muted="#C4C6D0",
    accent="#AAC7FF",
    accent_hover="#BBD2FF",
    on_accent="#0A305F",
    button="#3E4759",
    button_border="#3E4759",
    button_hover="#4A5365",
    button_hover_border="#4A5365",
    nav="#191C20",
    nav_text="#E2E2E9",
    nav_muted="#C4C6D0",
    nav_active="#3E4759",
    selection="#284777",
    shape=MATERIAL_SHAPE,
)

#: (style, dark) → palette. Every palette the GUI can paint with.
_PALETTES: Final[dict[tuple[str, bool], Palette]] = {
    (STYLE_CLASSIC, False): LIGHT,
    (STYLE_CLASSIC, True): DARK,
    (STYLE_MATERIAL, False): MATERIAL_LIGHT,
    (STYLE_MATERIAL, True): MATERIAL_DARK,
}
ALL_PALETTES: Final[tuple[Palette, ...]] = tuple(_PALETTES.values())


def resolve_theme(
    choice: str, system_is_dark: bool, style: str = STYLE_CLASSIC
) -> Palette:
    """Map a ``ui/theme`` and ``ui/style`` value to the palette to paint with.

    An unknown theme (an old or hand-edited setting) is treated as
    ``"system"``, and an unknown style as ``"classic"``, rather than raising,
    so a bad registry entry cannot stop the app from starting.

    >>> resolve_theme("system", system_is_dark=True).name
    'dark'
    >>> resolve_theme("light", system_is_dark=True, style="material").name
    'material-light'
    """
    if choice == THEME_LIGHT:
        dark = False
    elif choice == THEME_DARK:
        dark = True
    else:
        dark = system_is_dark
    known_style = style if style in STYLE_CHOICES else STYLE_CLASSIC
    return _PALETTES[(known_style, dark)]


def system_prefers_dark() -> bool:
    """Whether the OS colour scheme is dark (Qt 6.5+ ``styleHints``).

    Returns ``False`` without a ``QGuiApplication`` or when the platform
    reports ``Unknown`` (older Linux desktops), so the light theme is the
    fallback.
    """
    app = QGuiApplication.instance()
    if app is None:
        return False
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def build_palette(tokens: Palette) -> QPalette:
    """A ``QPalette`` matching ``tokens``.

    Widgets the stylesheet does not cover (menus, dialogs, the native file
    picker's Qt fallback) are painted by the Fusion style from this palette.
    Without it a dark theme would draw black text on a dark dialog.
    """
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: tokens.window,
        QPalette.ColorRole.WindowText: tokens.text,
        QPalette.ColorRole.Base: tokens.surface,
        QPalette.ColorRole.AlternateBase: tokens.surface_alt,
        QPalette.ColorRole.Text: tokens.text,
        QPalette.ColorRole.Button: tokens.button,
        QPalette.ColorRole.ButtonText: tokens.text,
        QPalette.ColorRole.Highlight: tokens.accent,
        QPalette.ColorRole.HighlightedText: tokens.on_accent,
        QPalette.ColorRole.ToolTipBase: tokens.surface,
        QPalette.ColorRole.ToolTipText: tokens.text,
        QPalette.ColorRole.PlaceholderText: tokens.muted,
        QPalette.ColorRole.Link: tokens.accent,
        QPalette.ColorRole.Mid: tokens.border,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    disabled = QColor(tokens.muted)
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.WindowText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


@functools.lru_cache(maxsize=1)
def _asset_dir() -> Path:
    """A private per-process directory for the stylesheet's glyph images.

    ``mkdtemp`` creates it readable by this user only, so no other account
    can swap the images, and it is removed when the process exits.
    """
    path = Path(tempfile.mkdtemp(prefix="thesisagents-gui-"))
    atexit.register(shutil.rmtree, path, ignore_errors=True)
    return path


def write_theme_assets(tokens: Palette) -> dict[str, str]:
    """Draw the check-box tick and the arrow glyphs for ``tokens``.

    Returns ``{"check": path, "down": path, "up": path}`` with forward-slash
    paths, the form a stylesheet ``url(...)`` accepts on every platform.
    Each palette's files are drawn once per process.
    """
    specs = {
        "check": ("check", tokens.on_accent),
        "down": ("chevron_down", tokens.muted),
        "up": ("chevron_up", tokens.muted),
    }
    assets: dict[str, str] = {}
    for key, (glyph, colour) in specs.items():
        path = _asset_dir() / f"{tokens.name}-{key}.png"
        if not path.is_file():
            write_glyph(glyph, colour, str(path))
        assets[key] = path.as_posix()
    return assets


def _glyph_rules(p: Palette, assets: dict[str, str]) -> str:
    """Check-box, combo-box and spin-box sub-controls drawn with ``assets``."""
    s = p.shape
    return f"""
QCheckBox::indicator, QTableView::indicator {{
    width: 16px;
    height: 16px;
    border: {2 if p.style == STYLE_MATERIAL else 1}px solid {p.muted};
    border-radius: {s.check_radius}px;
    background: transparent;
}}
QCheckBox::indicator:hover, QTableView::indicator:hover {{
    border-color: {p.accent};
}}
QCheckBox::indicator:checked, QTableView::indicator:checked {{
    background: {p.accent};
    border-color: {p.accent};
    image: url({assets["check"]});
}}
QCheckBox::indicator:disabled, QTableView::indicator:disabled {{
    background: {p.surface_alt};
    border-color: {p.border};
}}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 26px;
    border: none;
}}
QComboBox::down-arrow {{
    image: url({assets["down"]});
    width: 12px;
    height: 12px;
}}
QSpinBox {{
    padding-right: 26px;
}}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border;
    width: 24px;
    border: none;
    border-left: 1px solid {p.border};
    background: transparent;
}}
QSpinBox::up-button {{
    subcontrol-position: top right;
    border-top-right-radius: {s.input_radius}px;
}}
QSpinBox::down-button {{
    subcontrol-position: bottom right;
    border-bottom-right-radius: {s.input_radius}px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {p.surface_alt};
}}
QSpinBox::up-arrow {{
    image: url({assets["up"]});
    width: 10px;
    height: 10px;
}}
QSpinBox::down-arrow {{
    image: url({assets["down"]});
    width: 10px;
    height: 10px;
}}
"""


def build_stylesheet(
    tokens: Palette, assets: dict[str, str] | None = None, *, text_scale: float = 1.0
) -> str:
    """The application-wide Qt stylesheet for ``tokens``.

    Widgets opt into the special looks with object names and dynamic
    properties rather than per-widget stylesheets, so one string themes the
    whole window and a theme or style switch is a single ``setStyleSheet``
    call:

    * ``QPushButton[primary="true"]``: the one main action of a page.
    * ``#NavRail`` / ``#NavButton``: the sidebar.
    * ``#Card``: a rounded panel (``QFrame``) grouping one form section.
    * ``#PageTitle`` / ``#PageSubtitle`` / ``#CardTitle`` / ``#Muted``: type.

    Colours come from ``tokens``, radii, padding and weights from
    ``tokens.shape``. ``text_scale`` enlarges the page titles with the
    interface font (every other text takes the application font, so it
    needs no rule). ``assets`` (from :func:`write_theme_assets`) adds the
    check-box and arrow rules. Without it those controls keep the Fusion
    style's own drawing, which is what tests that only inspect the text use.
    """
    p = tokens
    s = p.shape
    card_border = f"1px solid {p.border}" if s.card_border else "none"
    glyphs = _glyph_rules(p, assets) if assets else ""
    title_pt = round(s.title_size_pt * text_scale)
    # A stylesheet min-height replaces the minimum Qt works out from the font,
    # so a fixed one lets a short window squash large text.
    control_px = max(20, round(18 * text_scale))
    return glyphs + f"""
QWidget {{
    color: {p.text};
}}
QMainWindow, QStackedWidget, #PageBody, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {p.window};
}}
QToolTip {{
    background: {p.surface};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 6px 8px;
    border-radius: 6px;
}}

/* Sidebar ---------------------------------------------------------- */
#NavRail {{
    background: {p.nav};
}}
#NavRail QLabel#NavBrand {{
    color: {p.nav_text};
    font-weight: 700;
    padding: 4px 6px;
}}
#NavButton {{
    background: transparent;
    color: {p.nav_muted};
    border: none;
    border-radius: {s.nav_radius}px;
    padding: {s.nav_padding};
    text-align: left;
}}
#NavButton:hover {{
    background: {p.nav_active};
    color: {p.nav_text};
}}
#NavButton:checked {{
    background: {p.nav_active};
    color: {p.nav_text};
    font-weight: 600;
}}

/* Page chrome ------------------------------------------------------ */
#PageHeader {{
    background: {p.window};
}}
QLabel#PageTitle {{
    font-size: {title_pt}pt;
    font-weight: {s.title_weight};
}}
QLabel#PageSubtitle, QLabel#Muted {{
    color: {p.muted};
}}
QLabel#CardTitle {{
    font-weight: {s.card_title_weight};
}}
#Card {{
    background: {p.surface};
    border: {card_border};
    border-radius: {s.card_radius}px;
}}
#Card QLabel, #Card QCheckBox {{
    background: transparent;
}}

/* Inputs ----------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox {{
    background: {p.window if p.style == STYLE_MATERIAL else p.surface};
    border: 1px solid {p.input_border};
    border-radius: {s.input_radius}px;
    padding: {s.input_padding};
    min-height: {control_px}px;
    selection-background-color: {p.accent};
    selection-color: {p.on_accent};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:read-only {{
    background: {p.surface_alt};
}}
QComboBox QAbstractItemView {{
    background: {p.surface};
    border: 1px solid {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}

/* Buttons ---------------------------------------------------------- */
QPushButton {{
    background: {p.button};
    border: 1px solid {p.button_border};
    border-radius: {s.button_radius}px;
    padding: {s.button_padding};
    min-height: {control_px}px;
}}
QPushButton:hover {{
    background: {p.button_hover};
    border-color: {p.button_hover_border};
}}
QPushButton:disabled {{
    color: {p.muted};
    background: {p.surface_alt};
    border-color: {p.surface_alt};
}}
QPushButton[primary="true"] {{
    background: {p.accent};
    color: {p.on_accent};
    border: 1px solid {p.accent};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: {p.accent_hover};
    border-color: {p.accent_hover};
}}
QPushButton[primary="true"]:disabled {{
    background: {p.border};
    border-color: {p.border};
    color: {p.muted};
}}

/* Tabs and read-only text --------------------------------------------- */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {p.border};
}}
QTabBar::tab {{
    background: transparent;
    color: {p.muted};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 6px 14px;
}}
QTabBar::tab:hover {{
    color: {p.text};
}}
QTabBar::tab:selected {{
    color: {p.text};
    border-bottom: 2px solid {p.accent};
    font-weight: 600;
}}
QTextBrowser {{
    background: {p.surface};
    border: {card_border};
    border-radius: {s.card_radius - 2}px;
    padding: 4px;
}}

/* Tables ----------------------------------------------------------- */
QTableView {{
    background: {p.surface};
    alternate-background-color: {p.surface_alt};
    border: {card_border};
    border-radius: {s.card_radius - 2}px;
    gridline-color: {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}
QHeaderView::section {{
    background: {p.surface_alt};
    color: {p.muted};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background: {p.surface_alt};
    border: none;
}}

/* Status bar, progress, splitter, scroll bars ---------------------- */
QStatusBar {{
    background: {p.nav if p.style == STYLE_MATERIAL else p.surface};
    border-top: 1px solid {p.border};
    color: {p.muted};
}}
#StatusButton {{
    padding: 1px 10px;
    min-height: 16px;
}}
#NoticeBanner {{
    background: {p.accent};
}}
#NoticeBanner QLabel#NoticeText {{
    background: transparent;
    color: {p.on_accent};
    font-weight: 600;
}}
QProgressBar {{
    background: {p.border};
    border: none;
    border-radius: 3px;
    max-height: 6px;
}}
QProgressBar::chunk {{
    background: {p.accent};
    border-radius: 3px;
}}
QSplitter::handle {{
    background: {p.window};
}}
QSplitter::handle:hover {{
    background: {p.border};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle {{
    background: {p.border};
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}}
QScrollBar::handle:hover {{
    background: {p.muted};
}}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
    border: none;
    width: 0;
    height: 0;
}}
"""


#: Set on the application once its Qt style is Fusion (see ``apply_theme``).
_STYLED_PROPERTY: Final[str] = "thesisagents_styled"


def apply_theme(app: QApplication, choice: str, style: str = STYLE_CLASSIC) -> Palette:
    """Paint ``app`` with theme ``choice`` in ``style``; return the palette used.

    Switches the Qt style to Fusion first: the native Windows style ignores
    most palette roles, so a dark palette on it gives dark text on dark
    buttons. Safe to call again at any time (Settings does on save, and the
    system-scheme listener does when the OS flips between light and dark).

    ``setStyle`` and the first ``setStyleSheet`` also rebuild Qt's per-class
    platform fonts, and those beat the application font: lists, tables, menus
    and the status bar drop back to the bare system family, losing the
    per-script fallback families (a Hindi label then makes Qt probe eight
    fonts that cannot shape it) and the interface font size. Setting the
    application font again clears them, so it comes last. That only helps
    widgets built later: the ones already on screen keep the class font they
    were given, so the style is set once and never again. Example: with a
    second ``setStyle`` a theme switch put the tables of an open window back
    to 9 pt.
    """
    tokens = resolve_theme(choice, system_prefers_dark(), style)
    if not app.property(_STYLED_PROPERTY):
        app.setStyle("Fusion")
        app.setProperty(_STYLED_PROPERTY, True)
    app.setPalette(build_palette(tokens))
    app.setStyleSheet(
        build_stylesheet(tokens, write_theme_assets(tokens), text_scale=font_scale())
    )
    app.setFont(app.font())
    app.setProperty("thesisagents_theme", tokens.name)
    return tokens


def current_palette() -> Palette:
    """The palette last applied by :func:`apply_theme` (classic light before that).

    Widgets that paint their own pixels (the sidebar icons) read it so their
    colours follow a theme or style switch.
    """
    app = QApplication.instance()
    name = app.property("thesisagents_theme") if app is not None else None
    for palette in ALL_PALETTES:
        if palette.name == name:
            return palette
    return LIGHT

"""GUI entry point. ``thesisagents-gui`` and ``thesisagents gui``
both resolve here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from thesisagents.gui.pages.settings import (
    apply_saved_env,
    saved_font_size,
    saved_style,
    saved_theme,
    saved_ui_language,
)
from thesisagents.utils.logging import get_logger

if TYPE_CHECKING:
    from PySide6.QtGui import QFont, QIcon


_LOG = get_logger(__name__)

# Package data, so it is found in a checkout, a pip install and the Nuitka
# bundle alike. It used to sit in the repository's assets/ folder, which
# neither of the last two contains, so their windows had no icon.
_ICON_PATH = Path(__file__).resolve().parent / "icon.ico"


def _configure_hidpi_env() -> None:
    """Pin the HiDPI policy BEFORE QApplication is constructed.

    On Qt 6 HiDPI is on by default but fractional scale factors (e.g.
    Windows at 125% / 150%) sometimes render blurry text without
    explicit guidance. Setting the policy to PassThrough lets the OS
    DPI flow into Qt unchanged; the env var version is the
    construction-time-safe knob because the QApplication-attribute
    version of this flag has to be set before QApplication.__init__
    runs and we cannot rely on import order callers will use.
    """
    # Only set if the user has not picked a policy of their own; respect
    # an explicit override.
    os.environ.setdefault(
        "QT_ENABLE_HIGHDPI_SCALING", "1",
    )
    os.environ.setdefault(
        "QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough",
    )


def _silence_font_probe_messages() -> None:
    """Hide Qt's ``OpenType support missing for "X", script N`` lines.

    Qt prints one for every family it tries before the one that can shape a
    script. The language lists hold "हिन्दी", so a machine whose system font
    has no Devanagari (Microsoft JhengHei on a zh-tw Windows) prints one on
    every start although the text renders in Nirmala UI. Reordering the
    families is no way out, since Nirmala UI first would also draw the Latin
    text. The lines are logged at info level, so a ``.warning`` rule does not
    reach them and the category's real warnings stay visible. Setting
    ``QT_LOGGING_RULES="qt.text.font.db.info=true"`` brings them back,
    because Qt applies that variable after these rules.
    """
    from PySide6.QtCore import QLoggingCategory

    QLoggingCategory.setFilterRules("qt.text.font.db.info=false")


def main(argv: list[str] | None = None) -> int:
    """Run the desktop app and return its exit code.

    A failure before the window exists is logged and shown in a dialog. The
    released app is a windowed program, so a traceback printed to the console
    would be seen by nobody and the app would just not open.
    """
    try:
        return _boot(argv)
    except Exception as err:  # noqa: BLE001 - the last place that can report it
        _report_startup_failure(err)
        return 1


def _report_startup_failure(err: Exception) -> None:
    """Log ``err`` and show it, with the place of the log file."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    from thesisagents.gui.activity import log_file, redact
    from thesisagents.gui.i18n import t

    _LOG.error("the desktop app could not start", exc_info=err)
    if QApplication.instance() is None:
        return
    language = saved_ui_language()
    text = t("error.startup", language, error=redact(f"{type(err).__name__}: {err}"))
    QMessageBox.critical(
        None, t("app.title", language), f"{text}\n\n{log_file()}"
    )


def _boot(argv: list[str] | None = None) -> int:
    """Boot the PySide6 desktop UI.

    Returns the Qt event-loop exit code so a non-zero shell exit
    propagates a crash up to the caller.
    """
    _configure_hidpi_env()
    _silence_font_probe_messages()

    # Import inside main so importing the package itself never pays
    # the PySide6 cost (~80 MB) when only the CLI is used.
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QApplication

    from thesisagents.gui.activity import install as install_activity_log
    from thesisagents.gui.font_size import (
        SMALLEST_DEFAULT_PT,
        remember_default_size,
        set_font_size,
    )
    from thesisagents.gui.i18n import normalise_language
    from thesisagents.gui.main_window import MainWindow
    from thesisagents.gui.theme import apply_theme

    # Mirror any saved API keys into os.environ BEFORE the first source
    # plugin is loaded by a search; otherwise the env var lookup that
    # the IEEE / Springer / Anthropic clients perform at fetcher
    # __init__ time will miss them.
    apply_saved_env()

    app_argv = list(sys.argv if argv is None else [sys.argv[0], *argv])
    app = QApplication.instance() or QApplication(app_argv)
    install_activity_log()

    # Window / taskbar / Alt-Tab icon. Setting on QApplication first
    # propagates to every top-level window automatically.
    icon = _load_app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    # Default to a slightly larger point-size than Qt's platform default
    # so text stays readable across HiDPI screens without per-widget
    # font overrides. Point-sized fonts let Qt's HiDPI scaling do the
    # right thing automatically.
    base_font = app.font()
    if base_font.pointSize() < SMALLEST_DEFAULT_PT:
        base_font.setPointSize(SMALLEST_DEFAULT_PT)
        app.setFont(base_font)
    # Tell Qt about every CJK / RTL fallback so we don't get tofu boxes
    # for hi / ko / zh-* when the host font lacks a glyph.
    app.setFont(_with_unicode_fallback(base_font))
    # The size above is the default. One picked under Settings → Font size
    # or with Ctrl++ / Ctrl+- replaces it.
    remember_default_size(app)
    set_font_size(app, saved_font_size())
    # Classic / Material 3 style and light / dark / follow-the-OS theme,
    # saved under Settings → Style and Theme. Applied
    # before the window exists so it never flashes in the wrong colours.
    apply_theme(app, saved_theme(), saved_style())

    # First-run language: settings override → OS locale → English.
    language = saved_ui_language(default=normalise_language(QLocale().name()))
    window = MainWindow(ui_language=language)
    window.show()
    window.check_for_updates()
    return app.exec()


def _load_app_icon() -> QIcon | None:
    """Return the bundled QIcon, or None when the .ico isn't reachable.

    Soft-fails because a repackaging can leave package data out, and the
    default Qt icon is better than a crash.
    """
    if not _ICON_PATH.is_file():
        return None
    # Imported lazily to avoid pulling PySide6 in at module import time.
    from PySide6.QtGui import QIcon

    return QIcon(str(_ICON_PATH))


def _with_unicode_fallback(font: QFont) -> QFont:
    """Add families that ship on Windows + commonly elsewhere to cover
    every script the UI may render. Qt walks the family list in order,
    so the original family stays the primary choice.
    """
    # Qt expects a comma-separated CSS-like family list when set via
    # setFamilies (Qt6+); the order is preference order.
    fallbacks = [
        font.family(),
        "Segoe UI",
        "Microsoft JhengHei UI",  # zh-tw on Windows
        "Microsoft YaHei UI",      # zh-cn on Windows
        "Yu Gothic UI",            # ja on Windows
        "Malgun Gothic",           # ko on Windows
        "Nirmala UI",              # hi / devanagari on Windows
        "Arial",
    ]
    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered = [f for f in fallbacks if not (f in seen or seen.add(f))]
    font.setFamilies(ordered)
    return font


if __name__ == "__main__":
    raise SystemExit(main())

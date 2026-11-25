"""Settings page.

Stores API keys in the system credential store (``gui/credentials.py``)
and the rest (contact email, cookies-file path, appearance) locally via
``QSettings`` (native registry on Windows / plist on macOS / ini on
Linux). On startup the values are also pushed into ``os.environ`` so
the existing source plugins pick them up — saving here is equivalent
to setting the corresponding env var before launching the CLI.

The page deliberately does NOT validate the keys against the live
APIs — that would require a network round-trip per field, and would
leak the key into HTTP logs. Empty strings clear the env var.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui import credentials
from thesisagents.gui.font_size import (
    MAX_FONT_PT,
    MIN_FONT_PT,
    clamp_font_size,
    default_font_size,
    layout_scale,
)
from thesisagents.gui.i18n import (
    LANGUAGE_DISPLAY_NAMES,
    SUPPORTED_LANGUAGES,
    t,
)
from thesisagents.gui.theme import STYLE_CHOICES, STYLE_CLASSIC, THEME_CHOICES, THEME_SYSTEM
from thesisagents.gui.widgets.responsive import Breakpoint, adapt_form_rows, make_card

# QSettings key (under organization/app) → env var name. The page reads
# both directions: load() pulls from QSettings into the form fields,
# save() writes back AND mirrors into os.environ for the current
# process.
_SETTINGS_FIELDS: Final[tuple[tuple[str, str, str], ...]] = (
    # (qsettings_key, env_var, label_i18n_key)
    ("api/anthropic", "ANTHROPIC_API_KEY", "settings.anthropic_key"),
    (
        "api/semantic_scholar",
        "THESISAGENTS_S2_API_KEY",
        "settings.s2_key",
    ),
    ("api/ncbi", "THESISAGENTS_NCBI_API_KEY", "settings.ncbi_key"),
    ("api/ieee", "THESISAGENTS_IEEE_API_KEY", "settings.ieee_key"),
    (
        "api/springer",
        "THESISAGENTS_SPRINGER_API_KEY",
        "settings.springer_key",
    ),
    (
        "api/crossref_plus",
        "THESISAGENTS_CROSSREF_PLUS_TOKEN",
        "settings.crossref_token",
    ),
    (
        "api/core",
        "THESISAGENTS_CORE_API_KEY",
        "settings.core_key",
    ),
    (
        "contact/email",
        "THESISAGENTS_CONTACT_EMAIL",
        "settings.contact_email",
    ),
)

#: The fields whose value is a secret and belongs in the credential store.
_SECRET_KEYS: Final[frozenset[str]] = frozenset(
    key for key, _env, _label in _SETTINGS_FIELDS if key.startswith("api/")
)

_COOKIES_KEY: Final[str] = "pdf/cookies_file"
_COOKIES_ENV: Final[str] = "THESISAGENTS_PDF_COOKIES_FILE"
_CHROME_PROFILE_KEY: Final[str] = "browser/chrome_profile_dir"
_CHROME_PROFILE_ENV: Final[str] = "THESISAGENTS_CHROME_PROFILE_DIR"
_UI_LANG_KEY: Final[str] = "ui/language"
#: One of ``theme.THEME_CHOICES``; applied as soon as Settings saves, with no
#: restart (unlike the interface language, which every label reads once).
_THEME_KEY: Final[str] = "ui/theme"
#: One of ``theme.STYLE_CHOICES`` (classic navy or Material 3), applied on
#: save like the theme.
_STYLE_KEY: Final[str] = "ui/style"
#: Interface font size in points. Absent means the default size, so a
#: user who never picked one keeps following the system's.
_FONT_SIZE_KEY: Final[str] = "ui/font_size"
#: Whether the app asks PyPI once a day for a newer release.
_UPDATES_KEY: Final[str] = "updates/check"
#: Whether the user has institutional / VPN access to paywalled publishers.
#: The PDF stage (``gui/pdf_stage.py``) leaves IEEE PDFs out while it is off.
_VPN_KEY: Final[str] = "access/vpn"

_ORG: Final[str] = "ThesisAgents"
_APP: Final[str] = "ThesisAgents"


def settings_store() -> QSettings:
    """Return the QSettings handle for the GUI.

    Uses ``QSettings.defaultFormat()`` (the registry on Windows unless
    changed), so tests can redirect storage to a temporary directory with
    ``QSettings.setDefaultFormat(IniFormat)`` + ``setPath(...)``. The
    two-argument ``QSettings(org, app)`` constructor always uses the
    native format and would ignore that redirect.
    """
    return QSettings(QSettings.defaultFormat(), QSettings.UserScope, _ORG, _APP)


def apply_saved_env() -> None:
    """Push every saved value into ``os.environ`` for this process.

    Called on app startup so the CLI / fetchers see the same values
    the user typed in Settings without needing a shell restart.
    """
    store = settings_store()
    credentials.migrate(store, _SECRET_KEYS)
    for key, env_var, _label in _SETTINGS_FIELDS:
        value = _saved_value(store, key)
        if value:
            os.environ[env_var] = value
        else:
            os.environ.pop(env_var, None)
    cookies = store.value(_COOKIES_KEY, "", type=str)
    if cookies:
        os.environ[_COOKIES_ENV] = cookies
    else:
        os.environ.pop(_COOKIES_ENV, None)
    chrome_profile = store.value(_CHROME_PROFILE_KEY, "", type=str)
    if chrome_profile:
        os.environ[_CHROME_PROFILE_ENV] = chrome_profile
    else:
        os.environ.pop(_CHROME_PROFILE_ENV, None)


def _saved_value(store: QSettings, key: str) -> str:
    """The saved value of one form field, wherever it is kept."""
    if key in _SECRET_KEYS:
        return credentials.read(store, key)
    return store.value(key, "", type=str)


def saved_ui_language(default: str = "en") -> str:
    """Read the persisted UI language, defaulting if unset."""
    store = settings_store()
    value = store.value(_UI_LANG_KEY, default, type=str)
    return value if value in SUPPORTED_LANGUAGES else default


def saved_theme() -> str:
    """The persisted GUI theme (``system`` / ``light`` / ``dark``).

    An unset or unknown value reads as ``system``, so a hand-edited setting
    falls back to following the OS instead of failing.
    """
    value = settings_store().value(_THEME_KEY, THEME_SYSTEM, type=str)
    return value if value in THEME_CHOICES else THEME_SYSTEM


def saved_style() -> str:
    """The persisted GUI style (``classic`` / ``material``).

    An unset or unknown value reads as ``classic``, the look the app had
    before styles were selectable.
    """
    value = settings_store().value(_STYLE_KEY, STYLE_CLASSIC, type=str)
    return value if value in STYLE_CHOICES else STYLE_CLASSIC


def saved_font_size() -> int:
    """The interface font size in points, the default when none is saved.

    A value outside the supported range (a hand-edited setting) is moved
    into it, and one that is not a number counts as unset.
    """
    value = settings_store().value(_FONT_SIZE_KEY)
    try:
        return clamp_font_size(int(value))
    except (TypeError, ValueError):
        return default_font_size()


def saved_update_check() -> bool:
    """Whether the app may look for a newer release (on by default)."""
    return bool(settings_store().value(_UPDATES_KEY, True, type=bool))


def saved_vpn_access() -> bool:
    """Whether Settings declares institutional / VPN access (off by default).

    Off is the safe default: the project's rule is to know about VPN access
    before any paywalled-publisher download, and an unanswered question must
    not count as a yes.
    """
    return bool(settings_store().value(_VPN_KEY, False, type=bool))


class _FontSizeBox(QSpinBox):
    """A spin box the mouse wheel only turns once it has the focus.

    The page scrolls, and scrolling past an ordinary spin box changes it.
    For this one that would resize the whole window by accident.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setRange(MIN_FONT_PT, MAX_FONT_PT)
        self.setSuffix(" pt")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Typing "16" must not apply the "1" on the way.
        self.setKeyboardTracking(False)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt override
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class SettingsPage(QWidget):
    """Form for API keys + cookies-file + UI language + theme + font size."""

    #: The theme saved by the user, emitted on every save (after the theme
    #: and the style are stored) so the window repaints at once.
    theme_changed = Signal(str)
    #: The interface font size in points, stored before it is emitted. Unlike
    #: the rest of the page it needs no Save, since a size is found by
    #: looking at it.
    font_size_changed = Signal(int)
    #: A different interface language was saved. The main window rebuilds
    #: itself in it, carrying the current work over.
    language_changed = Signal(str)
    #: The VPN / institutional access switch as saved, emitted on every save.
    #: The Search page locks or unlocks the ``ieee`` source with it.
    access_changed = Signal(bool)

    def __init__(self, ui_language: str = "en", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ui_language = ui_language
        self._field_inputs: dict[str, QLineEdit] = {}
        self._build_ui()
        self._load_from_store()

    def _build_ui(self) -> None:
        """Interface and browser cards in one column, API keys in the other.

        The two columns sit side by side on medium and expanded windows and
        stack on a compact one (``apply_breakpoint`` flips the direction of
        ``self._columns``).
        """
        language = self._ui_language
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 6, 0)
        outer.setSpacing(12)
        self._columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._columns.setSpacing(12)
        outer.addLayout(self._columns)

        left = QVBoxLayout()
        left.setSpacing(12)
        ui_card, ui_layout = make_card(t("settings.title", language), self)
        ui_form = QFormLayout()
        ui_layout.addLayout(ui_form)
        self._ui_lang_combo = QComboBox(self)
        # Show the language's own native name (繁體中文, Español, …)
        # but store the code as the item data so save() reads back a
        # clean BCP-47 token.
        for code in SUPPORTED_LANGUAGES:
            display = LANGUAGE_DISPLAY_NAMES.get(code, code)
            self._ui_lang_combo.addItem(display, code)
        ui_form.addRow(t("settings.ui_language", language), self._ui_lang_combo)
        self._theme_combo = QComboBox(self)
        for choice in THEME_CHOICES:
            self._theme_combo.addItem(t(f"settings.theme_{choice}", language), choice)
        ui_form.addRow(t("settings.theme_label", language), self._theme_combo)
        self._style_combo = QComboBox(self)
        for choice in STYLE_CHOICES:
            self._style_combo.addItem(t(f"settings.style_{choice}", language), choice)
        ui_form.addRow(t("settings.style_label", language), self._style_combo)
        self._add_font_size_rows(ui_form)
        self._updates_check = QCheckBox(t("settings.check_updates", language), self)
        ui_form.addRow(self._updates_check)
        adapt_form_rows(ui_card, ui_form)
        left.addWidget(ui_card)

        browser_card, browser_layout = make_card(t("settings.card_browser", language), self)
        browser_form = QFormLayout()
        browser_layout.addLayout(browser_form)
        self._cookies_input = self._path_row(
            browser_form, "settings.cookies_file", self._on_browse_cookies
        )
        self._chrome_profile_input = self._path_row(
            browser_form, "settings.chrome_profile_dir", self._on_browse_chrome_profile
        )
        self._vpn_check = QCheckBox(t("settings.vpn_access", language), self)
        browser_form.addRow(self._vpn_check)
        adapt_form_rows(browser_card, browser_form)
        left.addWidget(browser_card)
        left.addStretch(1)
        self._columns.addLayout(left, stretch=1)

        api_card, api_layout = make_card(t("settings.api_keys_group", language), self)
        api_form = QFormLayout()
        api_layout.addLayout(api_form)
        for key, _env_var, label_key in _SETTINGS_FIELDS:
            edit = QLineEdit(self)
            # Mask secret-shaped fields; contact email stays plain.
            if key in _SECRET_KEYS:
                edit.setEchoMode(QLineEdit.PasswordEchoOnEdit)
            api_form.addRow(t(label_key, language), edit)
            self._field_inputs[key] = edit
        self._storage_note = QLabel("", self)
        self._storage_note.setObjectName("Muted")
        self._storage_note.setWordWrap(True)
        self._show_storage(credentials.available())
        api_layout.addWidget(self._storage_note)
        adapt_form_rows(api_card, api_form)
        self._columns.addWidget(api_card, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)

        save_row = QHBoxLayout()
        self._status_label = QLabel("", self)
        self._status_label.setObjectName("Muted")
        self._status_label.setWordWrap(True)
        save_row.addWidget(self._status_label, stretch=1)
        save_button = QPushButton(t("settings.save_button", language), self)
        save_button.setProperty("primary", True)
        save_button.clicked.connect(self._on_save)
        save_row.addWidget(save_button)
        outer.addLayout(save_row)
        outer.addStretch(1)

    def _add_font_size_rows(self, form: QFormLayout) -> None:
        """The font size box, its Reset button and the keyboard hint."""
        language = self._ui_language
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self._font_size_box = _FontSizeBox(self)
        self._font_size_box.setAccessibleName(t("settings.font_size_label", language))
        self._font_size_box.setValue(saved_font_size())
        self._font_size_box.valueChanged.connect(self.set_font_size)
        reset = QPushButton(t("settings.font_size_reset", language), self)
        reset.clicked.connect(self.reset_font_size)
        layout.addWidget(self._font_size_box, stretch=1)
        layout.addWidget(reset)
        form.addRow(t("settings.font_size_label", language), row)
        hint = QLabel(t("settings.font_size_hint", language), self)
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        form.addRow(hint)

    def _path_row(self, form: QFormLayout, label_key: str, on_browse) -> QLineEdit:
        """A read-only path field with a Browse button, added to ``form``."""
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        field = QLineEdit(self)
        field.setReadOnly(True)
        browse = QPushButton(t("settings.browse_button", self._ui_language), self)
        browse.clicked.connect(on_browse)
        layout.addWidget(field, stretch=1)
        layout.addWidget(browse)
        form.addRow(t(label_key, self._ui_language), row)
        return field

    def apply_breakpoint(self, breakpoint: Breakpoint) -> None:
        """Two columns side by side, or stacked on a compact window.

        Enlarged text stacks them on a medium window too: the long labels of
        the two cards then need more than its width.
        """
        stacked = breakpoint is Breakpoint.COMPACT or (
            breakpoint is Breakpoint.MEDIUM and layout_scale() > 1.0
        )
        direction = (
            QBoxLayout.Direction.TopToBottom
            if stacked
            else QBoxLayout.Direction.LeftToRight
        )
        self._columns.setDirection(direction)

    def columns_direction(self) -> QBoxLayout.Direction:
        return self._columns.direction()

    def set_font_size(self, points: int) -> None:
        """Store ``points`` as the interface font size and announce it.

        The box calls this while the user turns it, and the window for its
        ``Ctrl++`` / ``Ctrl+-`` shortcuts, so the two never disagree.
        """
        points = clamp_font_size(points)
        settings_store().setValue(_FONT_SIZE_KEY, points)
        self._show_font_size(points)
        self.font_size_changed.emit(points)

    def reset_font_size(self) -> None:
        """Forget the picked size, so the default applies again."""
        settings_store().remove(_FONT_SIZE_KEY)
        points = default_font_size()
        self._show_font_size(points)
        self.font_size_changed.emit(points)

    def _show_font_size(self, points: int) -> None:
        self._font_size_box.blockSignals(True)
        self._font_size_box.setValue(points)
        self._font_size_box.blockSignals(False)

    def font_size_box(self) -> QSpinBox:
        return self._font_size_box

    def theme_combo(self) -> QComboBox:
        return self._theme_combo

    def updates_checkbox(self) -> QCheckBox:
        return self._updates_check

    def vpn_checkbox(self) -> QCheckBox:
        return self._vpn_check

    def language_combo(self) -> QComboBox:
        return self._ui_lang_combo

    def style_combo(self) -> QComboBox:
        return self._style_combo

    def _show_storage(self, in_store: bool) -> None:
        """Say where the keys are kept, in particular when that is plain text."""
        key = "settings.keys_in_store" if in_store else "settings.keys_plain"
        self._storage_note.setText(t(key, self._ui_language))

    def storage_note(self) -> str:
        return self._storage_note.text()

    def _on_browse_cookies(self) -> None:
        start = self._cookies_input.text() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.cookies_dialog_title", self._ui_language),
            start,
            "Cookies (*.txt);;All files (*.*)",
        )
        if path:
            self._cookies_input.setText(path)

    def _on_browse_chrome_profile(self) -> None:
        start = self._chrome_profile_input.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self,
            t("settings.chrome_profile_dialog_title", self._ui_language),
            start,
        )
        if path:
            self._chrome_profile_input.setText(path)

    def _on_save(self) -> None:
        store = settings_store()
        in_store = credentials.available()
        for key, env_var, _label in _SETTINGS_FIELDS:
            value = self._field_inputs[key].text().strip()
            if key in _SECRET_KEYS:
                in_store = credentials.write(store, key, value) and in_store
            else:
                store.setValue(key, value)
            if value:
                os.environ[env_var] = value
            else:
                os.environ.pop(env_var, None)
        self._show_storage(in_store)
        cookies = self._cookies_input.text().strip()
        store.setValue(_COOKIES_KEY, cookies)
        if cookies:
            os.environ[_COOKIES_ENV] = cookies
        else:
            os.environ.pop(_COOKIES_ENV, None)
        chrome_profile = self._chrome_profile_input.text().strip()
        store.setValue(_CHROME_PROFILE_KEY, chrome_profile)
        if chrome_profile:
            os.environ[_CHROME_PROFILE_ENV] = chrome_profile
        else:
            os.environ.pop(_CHROME_PROFILE_ENV, None)
        lang = self._ui_lang_combo.currentData() or "en"
        store.setValue(_UI_LANG_KEY, lang)
        theme = self._theme_combo.currentData() or THEME_SYSTEM
        store.setValue(_THEME_KEY, theme)
        store.setValue(_STYLE_KEY, self._style_combo.currentData() or STYLE_CLASSIC)
        store.setValue(_VPN_KEY, self._vpn_check.isChecked())
        store.setValue(_UPDATES_KEY, self._updates_check.isChecked())
        store.sync()
        self.theme_changed.emit(theme)
        self.access_changed.emit(self._vpn_check.isChecked())
        self._status_label.setText(
            t("settings.saved_message", self._ui_language)
        )
        if lang != self._ui_language:
            self.language_changed.emit(lang)

    def _load_from_store(self) -> None:
        store = settings_store()
        for key, _env_var, _label in _SETTINGS_FIELDS:
            self._field_inputs[key].setText(_saved_value(store, key))
        self._cookies_input.setText(store.value(_COOKIES_KEY, "", type=str))
        self._chrome_profile_input.setText(
            store.value(_CHROME_PROFILE_KEY, "", type=str),
        )
        saved_lang = store.value(_UI_LANG_KEY, self._ui_language, type=str)
        for idx in range(self._ui_lang_combo.count()):
            if self._ui_lang_combo.itemData(idx) == saved_lang:
                self._ui_lang_combo.setCurrentIndex(idx)
                break
        theme_index = self._theme_combo.findData(saved_theme())
        self._theme_combo.setCurrentIndex(max(0, theme_index))
        self._vpn_check.setChecked(saved_vpn_access())
        self._updates_check.setChecked(saved_update_check())
        style_index = self._style_combo.findData(saved_style())
        self._style_combo.setCurrentIndex(max(0, style_index))

    # --- accessors used by tests ----------------------------------------

    def field_input(self, qsettings_key: str) -> QLineEdit:
        return self._field_inputs[qsettings_key]

    def cookies_input(self) -> QLineEdit:
        return self._cookies_input

    def chrome_profile_input(self) -> QLineEdit:
        return self._chrome_profile_input

    def status_text(self) -> str:
        return self._status_label.text()

    def trigger_save(self) -> None:
        self._on_save()

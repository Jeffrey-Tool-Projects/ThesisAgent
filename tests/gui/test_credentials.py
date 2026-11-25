"""API keys live in the system credential store, and are never lost on the way."""

from __future__ import annotations

import os
import sys

import pytest

from thesisagents.gui import credentials
from thesisagents.gui.credentials import SERVICE
from thesisagents.gui.pages.settings import SettingsPage, apply_saved_env, settings_store

_KEY = "api/ieee"
_ENV = "THESISAGENTS_IEEE_API_KEY"


class _Broken:
    """A store that fails the way a locked keychain does."""

    def __init__(self, *failing: str) -> None:
        self._failing = failing
        self.saved: dict[tuple[str, str], str] = {}

    def _maybe_fail(self, what: str) -> None:
        if what in self._failing:
            raise RuntimeError("locked: secret-value")

    def get_password(self, service, key):
        self._maybe_fail("get")
        return self.saved.get((service, key))

    def set_password(self, service, key, value):
        self._maybe_fail("set")
        if "lose" not in self._failing:
            self.saved[service, key] = value

    def delete_password(self, service, key):
        self._maybe_fail("delete")
        del self.saved[service, key]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.setenv(_ENV, "x")
    monkeypatch.delenv(_ENV)


def test_saving_puts_the_key_in_the_store_and_not_in_the_settings(qtbot, credential_store):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.field_input(_KEY).setText("secret-1")
    page.field_input("contact/email").setText("me@example.org")
    page.trigger_save()
    assert credential_store.saved[SERVICE, _KEY] == "secret-1"
    assert not settings_store().contains(_KEY)
    # The e-mail is no secret and stays with the other settings.
    assert settings_store().value("contact/email") == "me@example.org"
    assert (SERVICE, "contact/email") not in credential_store.saved
    assert page.storage_note() == "Kept in this system's credential store."
    again = SettingsPage(ui_language="en")
    qtbot.addWidget(again)
    assert again.field_input(_KEY).text() == "secret-1"


def test_clearing_the_field_removes_the_key(qtbot, credential_store):
    credentials.write(settings_store(), _KEY, "secret-1")
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.field_input(_KEY).setText("")
    page.trigger_save()
    assert credential_store.saved == {}
    assert _ENV not in os.environ


def test_plain_text_keys_are_moved_at_start(credential_store):
    settings_store().setValue(_KEY, "old-plain")
    settings_store().setValue("contact/email", "me@example.org")
    apply_saved_env()
    assert credential_store.saved == {(SERVICE, _KEY): "old-plain"}
    assert not settings_store().contains(_KEY)
    assert os.environ[_ENV] == "old-plain"
    assert settings_store().value("contact/email") == "me@example.org"


def test_moving_again_changes_nothing(credential_store):
    settings_store().setValue(_KEY, "old-plain")
    assert credentials.migrate(settings_store(), [_KEY]) == 1
    assert credentials.migrate(settings_store(), [_KEY]) == 0
    assert credentials.read(settings_store(), _KEY) == "old-plain"


@pytest.mark.parametrize("failing", [("set",), ("get",), ("lose",), ("get", "set", "delete")])
def test_a_store_that_fails_never_loses_a_plain_key(failing, caplog):
    credentials.STORE.replace(_Broken(*failing))
    settings_store().setValue(_KEY, "old-plain")
    apply_saved_env()
    assert settings_store().value(_KEY) == "old-plain"
    assert os.environ[_ENV] == "old-plain"
    # The store's message may quote the key.
    assert "secret-value" not in caplog.text


def test_without_a_store_keys_stay_in_the_settings_and_the_page_says_so(qtbot):
    credentials.STORE.replace(None)
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert "plain text" in page.storage_note()
    page.field_input(_KEY).setText("secret-1")
    page.trigger_save()
    assert settings_store().value(_KEY) == "secret-1"
    assert "plain text" in page.storage_note()
    page.field_input(_KEY).setText("")
    page.trigger_save()
    assert not settings_store().contains(_KEY)


def test_the_note_turns_when_one_key_could_not_be_stored(qtbot):
    credentials.STORE.replace(_Broken("set"))
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    page.field_input(_KEY).setText("secret-1")
    page.trigger_save()
    assert "plain text" in page.storage_note()
    assert credentials.read(settings_store(), _KEY) == "secret-1"


def test_a_new_key_wins_over_an_old_one_the_store_kept():
    store = _Broken()
    credentials.STORE.replace(store)
    credentials.write(settings_store(), _KEY, "old")
    store._failing = ("set",)  # noqa: SLF001 - the store locks now
    assert credentials.write(settings_store(), _KEY, "new") is False
    assert credentials.read(settings_store(), _KEY) == "new"


def test_a_missing_keyring_package_means_no_store(monkeypatch):
    for name in ("Windows", "macOS", "SecretService"):
        monkeypatch.setitem(sys.modules, f"keyring.backends.{name}", None)
    assert credentials._platform_backend() is None  # noqa: SLF001


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows store")
def test_windows_uses_the_credential_manager():
    backend = credentials._platform_backend()  # noqa: SLF001
    assert type(backend).__name__ == "WinVaultKeyring"

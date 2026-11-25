"""GUI test fixtures.

Skips the entire ``tests/gui/`` tree when PySide6 isn't installed —
the suite stays runnable on a dev machine without the ``[gui]`` extra.
Every GUI test gets its own QSettings location, so pages and windows
that save state never touch the user's real registry / config file, and
an in-memory credential store.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6", reason="install thesisagents[gui]")
pytest.importorskip("pytestqt", reason="install thesisagents[dev]")

from PySide6.QtCore import QSettings  # noqa: E402 - after the skip guard

from thesisagents.gui import credentials  # noqa: E402 - after the skip guard


class MemoryCredentials:
    """A credential store for tests, so none reads or writes the user's own."""

    def __init__(self) -> None:
        self.saved: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, key: str) -> str | None:
        return self.saved.get((service, key))

    def set_password(self, service: str, key: str, value: str) -> None:
        self.saved[service, key] = value

    def delete_password(self, service: str, key: str) -> None:
        del self.saved[service, key]


@pytest.fixture(autouse=True)
def credential_store():
    store = MemoryCredentials()
    credentials.STORE.replace(store)
    yield store
    credentials.STORE.replace(None)


@pytest.fixture(autouse=True)
def _isolated_qsettings(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path))

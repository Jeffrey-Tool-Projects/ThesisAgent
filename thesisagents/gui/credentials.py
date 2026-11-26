"""API keys in the system credential store instead of a settings file.

Settings used to keep keys with everything else in ``QSettings``, which on
Windows is plain text in the registry, readable by any program the user
runs. They now go to the Windows Credential Manager, the macOS Keychain or
the Secret Service (GNOME Keyring, KWallet) through ``keyring``.

Where there is no store (a headless Linux box, a locked keychain, the
``keyring`` package missing) keys stay in ``QSettings`` as before, and the
Settings page says so. A key must never be lost, so :func:`migrate` removes
the plain copy only after reading the stored one back.

Example::

    migrate(settings_store())                       # once, at boot
    write(settings_store(), "api/ieee", "abc")
    read(settings_store(), "api/ieee")              # "abc"
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from typing import Any, Final

from PySide6.QtCore import QSettings

from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

SERVICE: Final[str] = "ThesisAgents"


def _platform_backend() -> Any:
    """The credential store of this system, or None.

    Named per platform rather than discovered: ``keyring`` finds its
    backends through package metadata, which a Nuitka bundle may not carry,
    and an auto-discovered backend could be one that stores plain text.
    """
    try:
        if sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring as Backend
        elif sys.platform == "darwin":
            from keyring.backends.macOS import Keyring as Backend
        else:
            from keyring.backends.SecretService import Keyring as Backend
        # The class property raises where the store cannot be used.
        if Backend.priority <= 0:
            return None
        return Backend()
    except Exception as err:  # noqa: BLE001 - any failure means "no store here"
        _LOG.info("no system credential store: %s", err)
        return None


class _Store:
    """Finds the backend once, and remembers when it stops working."""

    def __init__(self) -> None:
        self._looked = False
        self._backend: Any = None

    def backend(self) -> Any:
        if not self._looked:
            self._looked = True
            self._backend = _platform_backend()
        return self._backend

    def replace(self, backend: Any) -> None:
        """Use ``backend`` (None for "there is no store"). Tests call this."""
        self._looked = True
        self._backend = backend


STORE: Final[_Store] = _Store()


def available() -> bool:
    """Whether keys are kept in the system credential store."""
    return STORE.backend() is not None


def _get(key: str) -> str | None:
    backend = STORE.backend()
    if backend is None:
        return None
    try:
        return backend.get_password(SERVICE, key)
    except Exception as err:  # noqa: BLE001 - a locked store, a refused prompt
        _LOG.warning("the credential store could not be read: %s", type(err).__name__)
        return None


def _set(key: str, value: str) -> bool:
    """Store ``value`` and read it back. False when it is not there afterwards."""
    backend = STORE.backend()
    if backend is None:
        return False
    try:
        backend.set_password(SERVICE, key, value)
        return backend.get_password(SERVICE, key) == value
    except Exception as err:  # noqa: BLE001 - see _get
        # The message could quote the value, so only its type is logged.
        _LOG.warning("the credential store could not be written: %s", type(err).__name__)
        return False


def _delete(key: str) -> bool:
    """Remove ``key``. False when a value is still there afterwards."""
    backend = STORE.backend()
    if backend is None:
        return True
    try:
        if backend.get_password(SERVICE, key) is not None:
            backend.delete_password(SERVICE, key)
        return True
    except Exception as err:  # noqa: BLE001 - see _get
        _LOG.warning("a key could not be removed: %s", type(err).__name__)
        return False


def read(settings: QSettings, key: str) -> str:
    """The saved value of ``key``, empty when there is none."""
    stored = _get(key)
    return stored if stored is not None else settings.value(key, "", type=str)


def write(settings: QSettings, key: str, value: str) -> bool:
    """Save ``value`` for ``key`` (empty removes it).

    Returns whether it is stored safely: in the credential store, or
    removed from both places.
    """
    if not value:
        settings.remove(key)
        return _delete(key)
    if _set(key, value):
        settings.remove(key)
        return True
    # A stale value in the store would win over the new one on reading.
    _delete(key)
    settings.setValue(key, value)
    return False


def migrate(settings: QSettings, keys: Iterable[str]) -> int:
    """Move plain-text ``keys`` into the credential store, return how many moved."""
    moved = 0
    for key in keys:
        value = settings.value(key, "", type=str)
        if value and available() and write(settings, key, value):
            moved += 1
    if moved:
        settings.sync()
        _LOG.info("moved %d API key(s) to the system credential store", moved)
    return moved

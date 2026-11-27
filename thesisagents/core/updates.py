"""Is there a newer release? One request, nothing else.

A pip install asks PyPI: the package is what it updates. The Windows build
asks GitHub for its latest published release and counts it only when the
installer is attached. Every release reaches PyPI about an hour before the
Windows build is done, so asking PyPI there announced a version whose
download button opened the previous release, or one whose build failed.
The request carries no identifier beyond the ordinary User-Agent.

Example::

    newer = await newer_version("0.1.26")     # "0.1.30", or None
"""

from __future__ import annotations

import re
import sys
from typing import Final

from thesisagents.fetchers.http import scoped_client
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

PYPI_URL: Final[str] = "https://pypi.org/pypi/thesisagents/json"
RELEASES_URL: Final[str] = "https://github.com/Jeffrey-Tool-Projects/ThesisAgent/releases/latest"
#: The latest published release. Drafts and pre-releases are never returned.
GITHUB_LATEST_URL: Final[str] = (
    "https://api.github.com/repos/Jeffrey-Tool-Projects/ThesisAgent/releases/latest"
)
#: What the Windows build needs in a release before it is announced.
INSTALLER_ASSET: Final[str] = "thesisagents-setup-windows-x86_64.exe"

_PLAIN_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """``"1.2.3"`` as numbers, or None for anything else.

    A pre-release ("1.2.3rc1") or a local build is None on purpose: it is
    never announced, and a user running one is never told to go "up" to a
    release that may be older.
    """
    match = _PLAIN_VERSION.fullmatch(text.strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def is_newer(candidate: str, current: str) -> bool:
    """Whether ``candidate`` is a later release than ``current``.

    >>> is_newer("0.1.10", "0.1.9"), is_newer("0.1.9", "0.1.9")
    (True, False)
    """
    new, old = parse_version(candidate), parse_version(current)
    return new is not None and old is not None and new > old


def is_desktop_build() -> bool:
    """Whether this is the compiled Windows app rather than a pip install.

    Nuitka sets ``__compiled__`` in every compiled module, other freezers
    set ``sys.frozen``.
    """
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def download_page(version: str) -> str:
    """The page of ``version``, where its files are.

    The page of one release rather than ``/latest``, which moves on: it
    named another version than the one announced.
    """
    return f"https://github.com/Jeffrey-Tool-Projects/ThesisAgent/releases/tag/v{version}"


async def newer_version(current: str, *, desktop: bool | None = None) -> str | None:
    """The latest release when it is newer than ``current``, else None.

    ``desktop`` (the compiled app when not given) asks GitHub, see the
    module docstring. Never raises: a machine without network must not
    hear about it.
    """
    desktop = is_desktop_build() if desktop is None else desktop
    try:
        async with scoped_client("updates") as client:
            latest = await (_latest_installer(client) if desktop else _latest_package(client))
    except Exception as err:  # noqa: BLE001 - offline, proxy, changed format
        _LOG.info("update check failed: %s", err)
        return None
    return latest if latest and is_newer(latest, current) else None


async def _latest_package(client) -> str:
    response = await client.get(PYPI_URL)
    response.raise_for_status()
    return str(response.json()["info"]["version"])


async def _latest_installer(client) -> str | None:
    """The version of the latest published release that has its installer."""
    response = await client.get(
        GITHUB_LATEST_URL, headers={"Accept": "application/vnd.github+json"}
    )
    response.raise_for_status()
    release = response.json()
    if release.get("draft") or release.get("prerelease"):
        return None
    names = {str(asset.get("name", "")) for asset in release.get("assets") or ()}
    if INSTALLER_ASSET not in names:
        return None
    return str(release["tag_name"]).removeprefix("v")

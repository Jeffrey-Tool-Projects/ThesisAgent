"""Is there a newer release? One request to PyPI, nothing else.

PyPI is asked rather than GitHub because the project's name there does not
change when the repository moves, and every release is published to it
before the Windows build. The request carries no identifier beyond the
ordinary User-Agent.

Example::

    newer = await newer_version("0.1.26")     # "0.1.30", or None
"""

from __future__ import annotations

import re
from typing import Final

from thesisagents.fetchers.http import scoped_client
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

PYPI_URL: Final[str] = "https://pypi.org/pypi/thesisagents/json"
RELEASES_URL: Final[str] = "https://github.com/Jeffrey-Tool-Projects/ThesisAgent/releases/latest"

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


async def newer_version(current: str) -> str | None:
    """The latest release when it is newer than ``current``, else None.

    Never raises: a machine without network must not hear about it.
    """
    try:
        async with scoped_client("updates") as client:
            response = await client.get(PYPI_URL)
            response.raise_for_status()
            latest = str(response.json()["info"]["version"])
    except Exception as err:  # noqa: BLE001 - offline, proxy, changed format
        _LOG.info("update check failed: %s", err)
        return None
    return latest if is_newer(latest, current) else None

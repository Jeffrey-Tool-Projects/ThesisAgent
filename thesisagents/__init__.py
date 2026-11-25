"""ThesisAgents: keyword-driven paper search and export assistant."""

from importlib import metadata as _metadata


def _installed_version() -> str:
    """The version of the installed package.

    Read from the package metadata, because the release workflow bumps only
    ``pyproject.toml``: a constant here still said 0.1.0 at v0.1.26. A source
    tree that was never installed has no metadata and reports 0.0.0.
    """
    try:
        return _metadata.version("thesisagents")
    except _metadata.PackageNotFoundError:
        return "0.0.0"


__version__ = _installed_version()

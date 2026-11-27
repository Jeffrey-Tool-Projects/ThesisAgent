"""Query normalisation. Always run user keywords through here before building a URL."""

from __future__ import annotations

import re
import unicodedata

from thesisagents.core.constants import MAX_KEYWORD_LENGTH

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")


def normalize_query(raw: str) -> str:
    """Normalise a user-supplied keyword string.

    - NFC-normalise so visually identical inputs hash the same.
    - Drop control characters.
    - Collapse whitespace.
    - Cap length.
    """
    if raw is None:
        raise ValueError("query cannot be None")
    normalised = unicodedata.normalize("NFC", raw)
    normalised = _CONTROL_CHARS.sub(" ", normalised)
    normalised = _WHITESPACE.sub(" ", normalised).strip()
    if not normalised:
        raise ValueError("query is empty after normalisation")
    if len(normalised) > MAX_KEYWORD_LENGTH:
        normalised = normalised[:MAX_KEYWORD_LENGTH].rstrip()
    return normalised


def year_in_range(
    year: int | None, year_from: int | None, year_to: int | None
) -> bool:
    """True if ``year`` is within ``[year_from, year_to]`` (a None bound is open).

    This is the one year rule for the whole search path. The pipeline's
    post-merge filter and every source plugin that filters by year on its own
    (arXiv, DBLP, DOAJ, Europe PMC, HAL, CORE) call it, so a paper never
    survives one source and vanishes in another just because of which plugin
    returned it.

    A paper whose year is unknown passes. **Failure mode prevented**: a plugin
    that dropped year-less records removed a paper before the pipeline could
    merge it with another source's copy that does carry the year, so the same
    search lost the paper or kept it depending on the source mix.

    Example::

        >>> year_in_range(2025, 2024, 2026)
        True
        >>> year_in_range(2023, 2024, None)
        False
        >>> year_in_range(None, 2024, 2026)
        True
    """
    if year is None:
        return True
    if year_from is not None and year < year_from:
        return False
    return not (year_to is not None and year > year_to)

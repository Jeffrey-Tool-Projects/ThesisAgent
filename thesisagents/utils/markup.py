"""Plain text from the markup that bibliographic services put into titles and abstracts.

Crossref sends JATS (``<jats:p>``), Europe PMC HTML (``<h4>``), DBLP entities
(``&amp;``). Every source had its own ``<[^>]+>`` for it, which also removed
real text: "n<5 and m>3" came out as "n3".

Example::

    plain_text("On <i>E. coli</i> &amp; friends")     # "On E. coli & friends"
"""

from __future__ import annotations

import html
import re
from typing import Final

#: A tag: a name, optional ``name="value"`` attributes, and nothing else. A
#: comparison such as ``n<5`` or ``x <y and z> w`` is none.
_TAG: Final[re.Pattern[str]] = re.compile(
    r"</?([A-Za-z][\w:.-]*)(?:\s+[\w:.-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*\s*/?>"
)
#: Tags that stand inside a word or sentence. Any other one separates words.
_INLINE: Final[frozenset[str]] = frozenset({
    "a", "b", "bold", "em", "i", "italic", "monospace", "roman", "sans-serif", "sc", "scp",
    "span", "strong", "styled-content", "sub", "sup", "tt", "u", "underline",
})
_MATH_PREFIX: Final[str] = "mml:"


def plain_text(value: str | None) -> str:
    """``value`` without tags, with entities resolved and whitespace collapsed.

    Entities come first, because some services escape the tags themselves
    (``&lt;i&gt;``).

    >>> plain_text("If n<5 and m>3.<p>H<sub>2</sub>O &amp; more</p>")
    'If n<5 and m>3. H2O & more'
    """
    return " ".join(_TAG.sub(_replacement, html.unescape(value or "")).split())


def _replacement(match: re.Match[str]) -> str:
    name = match.group(1).lower()
    if name.startswith(_MATH_PREFIX):
        return ""
    return "" if name.removeprefix("jats:") in _INLINE else " "

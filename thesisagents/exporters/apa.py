"""APA 7 citations and references, the project's default without a venue.

The form is the one ``paper_rule`` specifies. Titles are left as their
source wrote them: turning a title into sentence case needs to know which
words are names, and guessing would misspell them.

Example::

    labels = citation_labels(papers)
    labels[0].in_text            # "(Vaswani et al., 2017)"
    reference(papers[0])         # [("Vaswani, A., & Shazeer, N. (2017). …", False), …]
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from thesisagents.core.models import Paper

_MAX_AUTHORS = 20
_NO_DATE = "n.d."
_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}

#: One piece of a reference and whether it is set in italics.
Segment = tuple[str, bool]


def _is_cjk(name: str) -> bool:
    return any("CJK" in unicodedata.name(c, "") or "HANGUL" in unicodedata.name(c, "")
               or "HIRAGANA" in unicodedata.name(c, "") or "KATAKANA" in unicodedata.name(c, "")
               for c in name)


def split_name(name: str) -> tuple[str, str]:
    """``(family, given)``. A name in CJK characters is kept whole.

    >>> split_name("Ashish Vaswani"), split_name("Vaswani, Ashish"), split_name("王小明")
    (('Vaswani', 'Ashish'), ('Vaswani', 'Ashish'), ('王小明', ''))
    """
    name = " ".join(name.split())
    if _is_cjk(name):
        return name, ""
    family, comma, given = name.partition(",")
    if comma:
        return family.strip(), given.strip()
    tokens = name.split()
    if len(tokens) < 2:
        return name, ""
    suffix = tokens.pop() if tokens[-1].lower() in _SUFFIXES and len(tokens) > 2 else ""
    given = " ".join(tokens[:-1])
    return tokens[-1], f"{given}, {suffix}" if suffix else given


def _initials(given: str) -> str:
    """``"Jean-Paul M."`` as ``"J.-P. M."``."""
    given, _comma, suffix = given.partition(",")
    parts = []
    for word in given.split():
        letters = [piece[0].upper() + "." for piece in word.split("-") if piece]
        parts.append("-".join(letters))
    return " ".join(parts) + (f", {suffix.strip()}" if suffix.strip() else "")


def _listed(name: str) -> str:
    family, given = split_name(name)
    initials = _initials(given)
    return f"{family}, {initials}" if initials else family


def _family(name: str) -> str:
    return split_name(name)[0]


@dataclass(frozen=True, slots=True)
class CitationLabel:
    """How one paper is cited in the text."""

    names: str
    year: str

    @property
    def in_text(self) -> str:
        return f"({self.names}, {self.year})"

    @property
    def narrative(self) -> str:
        return f"{self.names.replace(' & ', ' and ')} ({self.year})"


def _names(paper: Paper) -> str:
    families = [_family(author) for author in paper.authors if author.strip()]
    if not families:
        # Without an author APA cites the title.
        words = paper.title.split()
        return "“" + " ".join(words[:4]) + ("…" if len(words) > 4 else "") + "”"
    if len(families) == 1:
        return families[0]
    if len(families) == 2:
        return f"{families[0]} & {families[1]}"
    return f"{families[0]} et al."


def citation_labels(papers: Sequence[Paper]) -> list[CitationLabel]:
    """One label per paper. Papers that would look alike get a, b, c after the year."""
    plain = [(_names(paper), str(paper.year) if paper.year else _NO_DATE) for paper in papers]
    counts = Counter(plain)
    seen: Counter[tuple[str, str]] = Counter()
    labels = [CitationLabel(names, year) for names, year in plain]
    # The letters follow the order of the reference list.
    for index in reference_order(papers):
        names, year = plain[index]
        if counts[names, year] > 1:
            letter = chr(ord("a") + seen[names, year] % 26)
            seen[names, year] += 1
            dated = f"{year}-{letter}" if year == _NO_DATE else year + letter
            labels[index] = CitationLabel(names, dated)
    return labels


def _author_list(paper: Paper) -> str:
    authors = [_listed(author) for author in paper.authors if author.strip()]
    if len(authors) > _MAX_AUTHORS:
        return ", ".join(authors[: _MAX_AUTHORS - 1]) + ", … " + authors[-1]
    if len(authors) > 1:
        return ", ".join(authors[:-1]) + ", & " + authors[-1]
    return authors[0] if authors else ""


def reference(paper: Paper, label: CitationLabel | None = None) -> list[Segment]:
    """The reference as segments, the venue (or a title without one) in italics."""
    year = label.year if label else (str(paper.year) if paper.year else _NO_DATE)
    title = paper.title.rstrip(". ")
    authors = _author_list(paper)
    if authors and not authors.endswith("."):
        authors += "."
    head = f"{authors} ({year}). " if authors else ""
    tail = f" ({year})." if not authors else ""
    locator = _locator(paper)
    if paper.venue:
        return [
            (f"{head}{title}.{tail} ", False), (paper.venue.rstrip("."), True),
            (f". {locator}".rstrip(), False),
        ]
    if paper.arxiv_id:
        return [
            (head, False), (title, True),
            (f" (arXiv:{paper.arxiv_id}).{tail} arXiv. {locator}".rstrip(), False),
        ]
    return [(head, False), (title, True), (f".{tail} {locator}".rstrip(), False)]


def _locator(paper: Paper) -> str:
    """The DOI, else the arXiv page, else the URL."""
    if paper.doi:
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", paper.doi.strip(), flags=re.I)
        return f"https://doi.org/{doi}"
    if paper.arxiv_id:
        return f"https://arxiv.org/abs/{paper.arxiv_id}"
    return paper.url


def reference_order(papers: Sequence[Paper]) -> list[int]:
    """Indexes of ``papers`` in the order of an APA reference list."""

    def key(index: int) -> tuple[str, str, str]:
        paper = papers[index]
        authors = [_listed(a) for a in paper.authors if a.strip()]
        first = " ".join(authors) or paper.title
        # Accents do not change the place of a letter. A name in another script
        # has no ASCII form: what is left of it (the spaces between the authors)
        # would put all such papers in one place.
        plain = unicodedata.normalize("NFKD", first).encode("ascii", "ignore").decode()
        if not any(char.isalnum() for char in plain) or _is_cjk(first):
            plain = first
        return plain.casefold(), str(paper.year or ""), paper.title.casefold()

    return sorted(range(len(papers)), key=key)

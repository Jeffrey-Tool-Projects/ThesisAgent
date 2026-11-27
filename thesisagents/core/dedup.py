"""Multi-key de-duplication with field-merge across sources.

When two sources return the same paper, the earlier source's record is the
canonical one — its ``source``, ``source_id``, and ``url`` win so users
searching with ``arxiv`` first keep the arXiv URL. But for *optional* fields
that may be missing on one source and present on another (``pdf_url``,
``doi``, ``arxiv_id``, ``venue``, ``citation_count``, ``abstract``), the
merged record takes the first non-empty value across all duplicates.

This matters for the PDF download flow: ACM/Crossref records don't
carry a ``pdf_url`` field but OpenAlex usually has the OA mirror under
``best_oa_location.pdf_url``. Pre-merge, a first-wins ACM record would
drop OpenAlex's PDF link and the downloader would skip the paper with
``no_pdf_url``. Post-merge, the ACM record keeps its canonical
metadata but inherits the OpenAlex PDF URL.

Why matching is on ALL identity keys, not one
---------------------------------------------
Every paper carries up to three identities — DOI, arXiv ID, fuzzy title hash
— and each source populates a different subset. Matching only on the
*strongest* key each record happens to have (``Paper.dedup_key()``) meant a
DOI-less ACM record keyed on ``hash:…`` and the same paper's OpenAlex record
keyed on ``doi:10.1145/x`` never compared at all: both shipped, the user saw
the paper twice, and the ACM record never inherited OpenAlex's PDF URL — the
exact failure the field-merge above exists to prevent. Grouping on
:meth:`Paper.identity_keys` fixes that: papers sharing ANY key are one paper,
and a record that arrives later can transitively join two earlier groups (an
arXiv record and a publisher record joined by a third that carries both IDs).

The restraint is :func:`accept_matches`: two records that carry different
DOIs are never merged, and of the records a paper shares a key with, a DOI
or arXiv match is decided before a title match and wins over it. Same title
+ same first author + same year with two different DOIs is how a workshop
paper and its extended journal version look, and merging those would
silently drop one from the results. The guard is checked against every
candidate at once, not pair by pair: a DOI-less record whose title matches
paper A and whose arXiv ID matches paper B agrees with each of them alone,
and joining it to both used to make one record of A and B.

:func:`dedupe` holds the whole list, so it decides the groups in a fixed
order (records with a DOI first, then those with an arXiv ID, then the rest)
and the input order only chooses each group's canonical record. Without that,
the DOI-less record above arriving before B was merged into A on its title,
and A then carried B's arXiv ID.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from thesisagents.core.models import FieldProvenance, Paper, _canon_title

#: Prefix of the fuzzy (title + author + year) identity key. Links made on it
#: are the ones the conflict guard polices — DOI / arXiv keys are exact.
FUZZY_KEY_PREFIX = "hash:"

#: Prefix of the DOI identity key (``Paper.doi_key``). A match on it is never
#: refused, see :func:`accept_matches`.
_DOI_KEY_PREFIX = "doi:"


def dedupe(papers: Iterable[Paper]) -> list[Paper]:
    """Collapse duplicate Papers, merging optional fields across sources.

    Iteration order matters: the first occurrence of a paper is treated as the
    canonical record; later duplicates contribute only their non-empty optional
    fields. Callers concatenate sources in the user-supplied ``--source`` order
    so the canonical record reflects the user's source preference.

    Which papers form one group does not depend on the order: the records are
    matched strongest identifier first (see :func:`_identifier_rank`), then
    each group is merged in input order, so its first record is canonical.

    Example: ``dedupe([acm_no_doi, openalex_with_doi, crossref_same_doi])``
    returns one paper, sourced ``acm``, carrying OpenAlex's ``pdf_url`` and
    the DOI both later records supplied.
    """
    held = list(papers)
    index = IdentityIndex()
    slots = [0] * len(held)
    for position in sorted(range(len(held)), key=lambda i: (_identifier_rank(held[i]), i)):
        slots[position], _ = index.add(held[position])
    groups: dict[int, list[Paper]] = {}
    for position, slot in enumerate(slots):
        groups.setdefault(index.resolve(slot), []).append(held[position])
    # Insertion order of ``groups`` is the order of each group's first record.
    merged: list[Paper] = []
    for members in groups.values():
        record = members[0]
        for other in members[1:]:
            record = merge_papers(record, other)
        merged.append(record)
    return merged


def _identifier_rank(paper: Paper) -> int:
    """0 for a paper with a DOI, 1 for one with only an arXiv ID, 2 otherwise.

    The failure this prevents: a record without a DOI that matches paper A by
    title and paper B by arXiv ID is ambiguous until B has been seen. Matching
    the records that carry identifiers first lets the arXiv match decide, in
    whatever order the sources returned them.
    """
    if paper.doi_key() is not None:
        return 0
    return 1 if paper.arxiv_key() is not None else 2


class IdentityIndex:
    """De-duplication one paper at a time, for callers that keep adding.

    :func:`dedupe` answers "which of these papers are the same" for a list it
    holds in full. Snowballing and the literature library meet papers one by
    one and must ask of each "have I seen this one?" before deciding what to
    do with it. This class is the same matching (every identity key, the fuzzy
    guard, the field merge) with that question exposed.

    A paper is referred to by its **slot**, the integer :meth:`add` returns.
    Slots are handles, not list positions to rely on: when a later paper joins
    two earlier ones (it carries the DOI of one and the arXiv ID of the
    other), the two slots become one and the absorbed slot redirects to the
    survivor. Pass any slot through :meth:`resolve` before comparing it with
    another.

    Example::

        index = IdentityIndex(seeds)
        slot, is_new = index.add(candidate)
        if is_new:
            discovered.append(slot)
        canonical = index.get(slot)   # merged record, fields backfilled
    """

    def __init__(self, papers: Iterable[Paper] = ()) -> None:
        self._slots: list[Paper | None] = []    # None once absorbed
        self._keys: dict[str, int] = {}         # identity key -> slot
        self._redirect: dict[int, int] = {}     # absorbed slot -> survivor
        for paper in papers:
            self.add(paper)

    def add(self, paper: Paper) -> tuple[int, bool]:
        """Register ``paper`` and return ``(slot, is_new)``.

        ``is_new`` is False when the paper matched one already held, in which
        case its non-empty optional fields were merged into that record.
        """
        keys = paper.identity_keys()
        matches = _matching_slots(self._slots, self._keys, paper, keys)
        if not matches:
            self._slots.append(paper)
            position = len(self._slots) - 1
        else:
            position = min(matches)
            for absorbed in sorted(matches - {position}):
                self._slots[position] = merge_papers(
                    self._slots[position], self._slots[absorbed]
                )
                self._slots[absorbed] = None
                self._redirect[absorbed] = position
                _repoint(self._keys, absorbed, position)
            self._slots[position] = merge_papers(self._slots[position], paper)
        # ``setdefault``: a key already claimed by a DIFFERENT slot was rejected
        # by the conflict guard, so it must stay with the slot that owns it.
        for key in keys:
            self._keys.setdefault(key, position)
        return position, not matches

    def find(self, paper: Paper) -> int | None:
        """Slot of the held paper ``paper`` is the same as, or ``None``.

        Does not add or merge anything.
        """
        matches = _matching_slots(
            self._slots, self._keys, paper, paper.identity_keys()
        )
        return min(matches) if matches else None

    def resolve(self, slot: int) -> int:
        """The slot ``slot`` stands for now, following any merges."""
        while slot in self._redirect:
            slot = self._redirect[slot]
        return slot

    def get(self, slot: int) -> Paper:
        """The current (merged) record of ``slot``."""
        paper = self._slots[self.resolve(slot)]
        if paper is None:  # unreachable: resolve() never lands on an absorbed slot
            raise KeyError(slot)
        return paper

    def papers(self) -> list[Paper]:
        """Every distinct paper, in order of first appearance."""
        return [paper for paper in self._slots if paper is not None]

    def __len__(self) -> int:
        return sum(1 for paper in self._slots if paper is not None)


def _matching_slots(
    slots: list[Paper | None],
    index: dict[str, int],
    paper: Paper,
    keys: tuple[str, ...],
) -> set[int]:
    """Slots ``paper`` belongs to: those sharing a key that :func:`accept_matches` allows."""
    candidates: list[tuple[str, int, Paper]] = []
    for key in keys:
        position = index.get(key)
        if position is None:
            continue
        occupant = slots[position]
        if occupant is None:
            continue
        candidates.append((key, position, occupant))
    return accept_matches(paper, candidates)


def accept_matches(
    paper: Paper, candidates: Iterable[tuple[str, int, Paper]]
) -> set[int]:
    """Which of the records ``paper`` shares a key with it may be merged with.

    The failure this prevents: a record C without a DOI, whose title, first
    author and year match paper A and whose arXiv ID matches paper B, agrees
    with A and with B taken one at a time. Merging it with both made one
    record of A and B, which carried A's DOI and B's arXiv ID, and one of the
    two papers was gone.

    ``candidates`` are ``(key, handle, record)`` in the order of
    ``paper.identity_keys()``, so DOI first, then arXiv ID, then title hash.
    ``handle`` is whatever names the record to the caller (a slot, a row id).
    Each candidate is checked against ``paper`` merged with the candidates
    accepted before it, so a strong-identifier match is decided first and
    wins over a title match:

    * a DOI match is always accepted. The key names that record, even when
      its own DOI is another one because two papers were merged by hand
      (``Library.merge``),
    * an arXiv match is refused when the two carry different DOIs,
    * a title match is refused on any DOI or arXiv disagreement and for an
      empty title (:func:`fuzzy_link_allowed`).

    Example: with A = (DOI 10.1/a, title T) and B = (DOI 10.1/b, arXiv
    2401.00001) held, C = (title T, arXiv 2401.00001) is accepted by B. A is
    refused, because B gave the merged record the DOI 10.1/b. The result is
    B's handle alone.
    """
    accepted: set[int] = set()
    merged = paper
    for key, handle, record in candidates:
        if handle in accepted:
            continue
        if key.startswith(_DOI_KEY_PREFIX):
            allowed = True
        elif key.startswith(FUZZY_KEY_PREFIX):
            allowed = fuzzy_link_allowed(record, merged)
        else:
            allowed = not _dois_conflict(record, merged)
        if allowed:
            accepted.add(handle)
            merged = merge_papers(merged, record)
    return accepted


def fuzzy_link_allowed(existing: Paper, candidate: Paper) -> bool:
    """Whether a title-hash match alone may merge these two records.

    Blocked in two cases:

    * **Conflicting strong identifiers.** Both carry a DOI (or both an arXiv
      ID) and they disagree, see the module docstring's workshop-vs-journal
      example. The exact-key path still merges them if a DOI does match.
    * **An empty canonical title.** ``_canon_title`` strips every
      non-alphanumeric character, so a paper titled ``"..."`` — or one whose
      title the source left blank — hashes identically to every other such
      paper. Without this check the fuzzy key becomes a magnet that collapses
      unrelated title-less records into one.
    """
    if not _canon_title(existing.title) or not _canon_title(candidate.title):
        return False
    return not _identifiers_conflict(existing, candidate)


def _dois_conflict(a: Paper, b: Paper) -> bool:
    """True when both papers carry a DOI and the two are different."""
    left, right = a.doi_key(), b.doi_key()
    return left is not None and right is not None and left != right


def _identifiers_conflict(a: Paper, b: Paper) -> bool:
    """True when both papers name the same identifier type but disagree on it."""
    for left, right in ((a.doi_key(), b.doi_key()), (a.arxiv_key(), b.arxiv_key())):
        if left is not None and right is not None and left != right:
            return True
    return False


def _repoint(index: dict[str, int], absorbed: int, target: int) -> None:
    """Redirect every key pointing at an absorbed slot to the surviving one."""
    for key, position in index.items():
        if position == absorbed:
            index[key] = target


# Fields backfilled across duplicates. ``source`` / ``source_id`` / ``url`` /
# ``title`` are intentionally excluded — they stay with the canonical record
# so links and citation handling stay stable across runs.
_MERGEABLE_FIELDS: tuple[str, ...] = (
    "pdf_url", "doi", "arxiv_id", "venue", "citation_count",
    "year", "abstract", "authors", "summary",
)


def _is_missing(value: object) -> bool:
    """``None`` and empty strings/tuples count as missing for merge purposes."""
    if value is None:
        return True
    if isinstance(value, (str, tuple)):
        return len(value) == 0
    return False


def merge_papers(canonical: Paper, other: Paper) -> Paper:
    """Return a copy of ``canonical`` with optional fields backfilled from ``other``.

    Only fills fields where ``canonical`` is missing data — never
    overwrites a populated field. ``source`` / ``source_id`` / ``url`` /
    ``title`` / ``authors`` stay with the canonical record so links and
    citation handling stay stable.
    """
    updates: dict[str, object] = {}
    added_provenance: list[FieldProvenance] = []
    for name in _MERGEABLE_FIELDS:
        canonical_value = getattr(canonical, name)
        other_value = getattr(other, name)
        if _is_missing(canonical_value) and not _is_missing(other_value):
            updates[name] = other_value
            added_provenance.append(
                FieldProvenance(
                    field=name,
                    source=other.source,
                    source_id=other.source_id,
                )
            )
    if not updates:
        return canonical
    updates["provenance"] = canonical.provenance + tuple(added_provenance)
    return replace(  # NOSONAR dataclasses.replace returns the same dataclass type
        canonical, **updates
    )

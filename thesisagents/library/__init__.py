"""Persistent literature library: papers, sightings, citation links, verdicts.

See :mod:`thesisagents.library.store` for the API and
:mod:`thesisagents.library.schema` for the tables and their versioning.
"""

from thesisagents.library.curation import (
    DECISIONS,
    READING_STATUSES,
    STAGES,
    Annotation,
    Screening,
)
from thesisagents.library.prisma import PrismaFlow, prisma_flow, prisma_svg
from thesisagents.library.saved import SavedSearch, SavedSearchOutcome, run_saved_search
from thesisagents.library.schema import SCHEMA_VERSION
from thesisagents.library.store import (
    LIBRARY_SOURCE,
    VERIFIED_FOR,
    AddReport,
    Library,
    LibraryEntry,
    LibraryRun,
    LibraryStats,
    LibraryVerificationCache,
)

__all__ = [
    "DECISIONS",
    "LIBRARY_SOURCE",
    "READING_STATUSES",
    "SCHEMA_VERSION",
    "STAGES",
    "VERIFIED_FOR",
    "AddReport",
    "Annotation",
    "Library",
    "LibraryEntry",
    "LibraryRun",
    "LibraryStats",
    "LibraryVerificationCache",
    "PrismaFlow",
    "SavedSearch",
    "SavedSearchOutcome",
    "Screening",
    "prisma_flow",
    "prisma_svg",
    "run_saved_search",
]

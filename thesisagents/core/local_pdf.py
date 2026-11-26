"""Turn local PDF files into the papers of a run, without search or download.

The boundary this guards: who may build a collection from local PDFs. The
logic used to live in ``cli_local_pdf.build_from_local_pdf``, which takes the
CLI's ``argparse.Namespace``, so the GUI (``progress.md`` #29) would have had
to fake a namespace to reach it. It now takes paths and a
:class:`LocalPdfOverrides`, and the CLI's ``--pdf`` mode is a thin wrapper.

Each file is validated, read once, and described by what its own front
matter says (title, authors, year, DOI, arXiv ID, abstract). Text extraction
needs the ``[intelligence]`` extra (``pypdf``), imported only when a PDF is
read, so importing this module costs nothing.

Example::

    collection = build_local_collection(["thesis.pdf"], "exports")
    collection.papers[0].title
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Paper, PaperCollection, Query
from thesisagents.utils.logging import get_logger
from thesisagents.utils.path_safety import ensure_export_dir, safe_filename

_LOG = get_logger(__name__)

#: ``Paper.source`` of a paper read from a local file.
LOCAL_SOURCE: Final[str] = "local"
#: A local PDF bigger than this is refused before it is read.
MAX_LOCAL_PDF_BYTES: Final[int] = 100 * 1024 * 1024


@dataclass(frozen=True)
class LocalPdfOverrides:
    """Metadata that replaces what the PDF's front matter says.

    Applied only when exactly one PDF is read: for a batch, one set of
    values would overwrite every file's real metadata. ``authors`` is a
    comma-separated string, like the CLI's ``--authors``.

    Example: ``LocalPdfOverrides(title="My thesis", year=2026)``.
    """

    title: str | None = None
    authors: str | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None


def resolve_pdf_inputs(raw: str | Path) -> list[Path]:
    """Expand a path to a sorted list of ``.pdf`` files.

    A directory is walked one level deep, a file is returned as-is. Raises
    :class:`ThesisAgentsError` for a path that does not exist.
    """
    root = Path(raw).expanduser().resolve()
    if root.is_dir():
        return sorted(p for p in root.glob("*.pdf") if p.is_file())
    if root.is_file():
        return [root]
    raise ThesisAgentsError(f"PDF path does not exist: {root}")


def build_local_collection(
    pdf_paths: Sequence[str | Path],
    out_dir: str | Path,
    overrides: LocalPdfOverrides | None = None,
) -> PaperCollection:
    """Build a ``PaperCollection`` with one ``Paper`` per local PDF.

    Each file is:

    1. validated (existence, size cap, ``%PDF`` magic, not encrypted), so a
       bad file is a :class:`ThesisAgentsError` naming it, not a pypdf
       stack trace;
    2. read once, with its text extracted by ``intelligence.pdf._extract_text``;
       the text feeds the metadata heuristic and a later enrichment;
    3. described by :func:`intelligence.pdf_metadata.extract_metadata`, with
       ``overrides`` winning for a single file;
    4. copied into ``{out_dir}/pdfs/`` (not when it is already there).

    Raises :class:`ThesisAgentsError` when ``pdf_paths`` is empty or a file
    is unusable, and ``ImportError`` without the ``[intelligence]`` extra.
    """
    paths = [Path(p).expanduser().resolve() for p in pdf_paths]
    if not paths:
        raise ThesisAgentsError("no PDF files were given")
    out_root = ensure_export_dir(out_dir)
    pdf_dir = ensure_export_dir(out_root / "pdfs")
    applied = overrides if (overrides is not None and len(paths) == 1) else LocalPdfOverrides()
    papers = tuple(_build_one(path, applied, pdf_dir) for path in paths)
    keywords = papers[0].title if len(papers) == 1 else f"{len(papers)} local PDFs"
    query = Query(
        keywords=keywords,
        sources=(LOCAL_SOURCE,),
        max_results=Query.clamp_max_results(len(papers)),
    )
    return PaperCollection(query=query, papers=papers)


def _build_one(pdf_path: Path, overrides: LocalPdfOverrides, pdf_dir: Path) -> Paper:
    """Read, parse, and stage one local PDF; return the resulting Paper."""
    body = read_pdf_safely(pdf_path)
    from thesisagents.intelligence.pdf import _extract_text
    from thesisagents.intelligence.pdf_metadata import extract_metadata

    extracted, page_count = _extract_text(body, source=LOCAL_SOURCE)
    metadata = extract_metadata(extracted)
    title = _pick(
        overrides.title,
        metadata.title,
        pdf_path.stem.replace("_", " ").replace("-", " ").strip(),
    )
    authors = _resolve_authors(overrides.authors, metadata.authors)
    abstract = metadata.abstract or " ".join(extracted.split())[:1500]
    digest = hashlib.sha256(body, usedforsecurity=False).hexdigest()[:16]
    target = _copy_target(pdf_dir, title, digest)
    if pdf_path.resolve() != target.resolve():
        shutil.copyfile(pdf_path, target)
    _LOG.info(
        "Local PDF: %s (%d bytes, %d chars, %d pages) -> %s",
        pdf_path.name, len(body), len(extracted), page_count, target,
    )
    return Paper(
        source=LOCAL_SOURCE,
        source_id=digest,
        title=title,
        authors=authors,
        year=_pick(overrides.year, metadata.year),
        venue=_pick(overrides.venue),
        abstract=abstract,
        url=f"file:///{pdf_path.as_posix().lstrip('/')}",
        doi=_pick(overrides.doi, metadata.doi),
        arxiv_id=_pick(overrides.arxiv_id, metadata.arxiv_id),
        pdf_url=None,
        raw={"extracted_text": extracted, "page_count": page_count},
    )


def _copy_target(pdf_dir: Path, title: str, digest: str) -> Path:
    """Where the copy goes: named by the title, and by the content as well
    when another file has that name already.

    The failure this prevents: two PDFs whose front matter gives one title
    (a thesis and its draft) were copied over each other.
    """
    target = pdf_dir / f"{safe_filename(title)}.pdf"
    if not target.exists():
        return target
    present = hashlib.sha256(target.read_bytes(), usedforsecurity=False).hexdigest()
    if present.startswith(digest):
        return target
    return pdf_dir / f"{safe_filename(title)}-{digest[:8]}.pdf"


def read_pdf_safely(pdf_path: Path) -> bytes:
    """Read a PDF off disk with a size cap and a magic check, raising friendly errors."""
    try:
        size = pdf_path.stat().st_size
    except OSError as err:
        raise ThesisAgentsError(f"could not read {pdf_path}: {err}") from err
    if size == 0:
        raise ThesisAgentsError(f"PDF file is empty: {pdf_path}")
    if size > MAX_LOCAL_PDF_BYTES:
        raise ThesisAgentsError(
            f"PDF file exceeds the {MAX_LOCAL_PDF_BYTES // (1024 * 1024)} MB safety cap: "
            f"{pdf_path} ({size} bytes)"
        )
    body = pdf_path.read_bytes()
    if not body.startswith(b"%PDF"):
        raise ThesisAgentsError(f"not a PDF file (no %PDF magic): {pdf_path}")
    if b"/Encrypt" in body[:4096]:
        raise ThesisAgentsError(f"PDF is encrypted; decrypt it first (qpdf / pdftk): {pdf_path}")
    return body


def _pick(*candidates):
    """Return the first non-empty candidate (or None)."""
    for candidate in candidates:
        if candidate not in (None, "", ()):
            return candidate
    return None


def _resolve_authors(override: str | None, extracted: tuple[str, ...]) -> tuple[str, ...]:
    if override:
        return tuple(a.strip() for a in override.split(",") if a.strip())
    return extracted

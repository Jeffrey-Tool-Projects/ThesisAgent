"""The GUI's PDF download stage, with the institutional-access gate (``progress.md`` #24).

The boundary this guards: the project's HARD rule on paywalled publishers
(``CLAUDE.md`` "IEEE / Publisher CDN"). Before any download that involves a
paywalled publisher, the user's VPN / institutional access must be known,
because without it IEEE answers with an abstract page or a 403 and the
download fails after opening a browser window for nothing. The CLI and MCP
learn it from the session; the GUI learns it from a Settings switch, *I have
institutional / VPN access* (QSettings ``access/vpn``, off by default), as
the owner decided on 2026-11-19.

With the switch off, IEEE papers are left out of the batch and counted, and
everything else downloads. With it on, every paper is attempted. The
download itself is ``core.pdf_download.download_pdfs``, the function the CLI
(``--export pdf``) and the MCP ``download_pdfs`` tool use, which already
routes paywalled publisher URLs through a visible Chrome window.

Example::

    report = run_pdf_stage(collection, "exports", vpn_access=False)
    report.saved, report.skipped, report.held   # 12, 3, 2
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from thesisagents.core.models import Paper, PaperCollection
from thesisagents.core.pdf_download import (
    ROUTE_BROWSER,
    ROUTE_DIRECT_BROWSER_FAILED,
    ROUTE_DIRECT_NO_BROWSER,
    PdfDownloadResult,
    download_pdfs,
)
from thesisagents.fetchers.http import shutdown_clients

#: Sources and hosts that need institutional access for their PDFs. IEEE is
#: the one the access rule names: the other publishers' open-access PDFs often
#: download without it, and their failures cost no more than a skipped paper.
_GATED_SOURCES: Final[frozenset[str]] = frozenset({"ieee"})
_GATED_HOST_SUFFIXES: Final[tuple[str, ...]] = ("ieee.org",)
#: Subfolder ``download_pdfs`` writes into, under the export folder.
PDF_SUBDIR: Final[str] = "pdfs"


@dataclass(frozen=True)
class PdfStageReport:
    """What the PDF stage did: ``saved`` on disk (new or already there),
    ``skipped`` by the downloader (no PDF link, HTTP error, not a PDF), and
    ``held`` back because they need institutional access the user has not
    declared.

    The route counts surface the browser rule (``progress.md`` #31):
    ``via_browser`` PDFs came through visible Chrome, ``without_browser``
    publisher PDFs were tried with a direct request because browser
    automation was unavailable, and ``browser_failed`` ones because Chrome
    could not fetch them. The last two are what the Deck page warns about.
    """

    folder: Path
    saved: int
    skipped: int
    held: int
    via_browser: int = 0
    without_browser: int = 0
    browser_failed: int = 0


def needs_institutional_access(paper: Paper) -> bool:
    """Whether ``paper``'s PDF sits behind IEEE's paywall.

    >>> needs_institutional_access(Paper(source="ieee", source_id="1", title="t",
    ...     authors=(), year=None, venue=None, abstract="", url="https://x"))
    True
    """
    if paper.source in _GATED_SOURCES:
        return True
    host = (urlsplit(paper.pdf_url or "").hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in _GATED_HOST_SUFFIXES)


def run_pdf_stage(
    collection: PaperCollection, out_dir: str | Path, *, vpn_access: bool
) -> PdfStageReport:
    """Download the PDFs of ``collection`` into ``{out_dir}/pdfs``. Blocking.

    Runs its own event loop, so call it from a worker thread. The shared HTTP
    clients are closed afterwards even when a download raises.
    """
    held = 0 if vpn_access else sum(needs_institutional_access(p) for p in collection.papers)
    batch = tuple(
        paper for paper in collection.papers
        if vpn_access or not needs_institutional_access(paper)
    )

    async def download() -> list[PdfDownloadResult]:
        try:
            subset = replace(collection, papers=batch)
            return await download_pdfs(
                subset,  # NOSONAR dataclasses.replace returns the same dataclass type
                out_dir,
            )
        finally:
            await shutdown_clients()

    results = asyncio.run(download()) if batch else []
    saved = sum(1 for result in results if result.path is not None)

    def routed(route: str) -> int:
        return sum(1 for result in results if result.route == route)

    return PdfStageReport(
        folder=Path(out_dir) / PDF_SUBDIR,
        saved=saved,
        skipped=len(batch) - saved,
        held=held,
        via_browser=routed(ROUTE_BROWSER),
        without_browser=routed(ROUTE_DIRECT_NO_BROWSER),
        browser_failed=routed(ROUTE_DIRECT_BROWSER_FAILED),
    )

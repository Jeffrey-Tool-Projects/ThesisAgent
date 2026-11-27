"""Every plugin that filters by year on its own keeps a paper of unknown year.

The pipeline's post-merge year filter keeps a paper whose year is unknown, but
arXiv, DBLP, DOAJ, Europe PMC, HAL and CORE used to run their own local filter
that dropped such a paper as soon as ``year_from`` or ``year_to`` was set. The
same search then lost the paper or kept it depending on which source returned
it, and the paper never reached the merge step where another source's copy
could fill in the year (code review R10).

Each ``unknown_year`` fixture is the source's recorded ``llm_security`` fixture
plus one extra record whose year field is removed (for arXiv, the
``<published>`` date). The tests ask for ``year_from=2025`` and check that the
undated record survives while the dated out-of-range one is still dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.sources._mock import MockTransport, install_mock
from thesisagents.core.models import Query
from thesisagents.core.query import year_in_range
from thesisagents.fetchers import http as http_module

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
_UNDATED_TITLE = "Undated Preprint On LLM Security Without A Publication Year"


@pytest.fixture(autouse=True)
def _clean_registry(monkeypatch):
    # CORE is opt-in and refuses to construct without its key.
    monkeypatch.setenv("THESISAGENTS_CORE_API_KEY", "test-key")
    yield
    http_module._CLIENTS.clear()  # noqa: SLF001  # tests reach into the registry on purpose


def _fetcher(source: str):
    """Import lazily so the CORE key set above is present at construction."""
    if source == "arxiv":
        from thesisagents.sources.arxiv.fetcher import ArxivFetcher

        return ArxivFetcher()
    if source == "dblp":
        from thesisagents.sources.dblp.fetcher import DblpFetcher

        return DblpFetcher()
    if source == "doaj":
        from thesisagents.sources.doaj.fetcher import DoajFetcher

        return DoajFetcher()
    if source == "europepmc":
        from thesisagents.sources.europepmc.fetcher import EuropePmcFetcher

        return EuropePmcFetcher()
    if source == "hal":
        from thesisagents.sources.hal.fetcher import HalFetcher

        return HalFetcher()
    from thesisagents.sources.core.fetcher import CoreFetcher

    return CoreFetcher()


@pytest.mark.parametrize(
    ("source", "fixture", "out_of_range_year"),
    [
        ("arxiv", "arxiv/unknown_year.xml", 2017),
        ("dblp", "dblp/unknown_year.json", 2018),
        ("doaj", "doaj/unknown_year.json", None),
        ("europepmc", "europepmc/unknown_year.json", None),
        ("hal", "hal/unknown_year.json", None),
        ("core", "core/unknown_year.json", None),
    ],
)
async def test_undated_record_survives_year_from(
    monkeypatch, source: str, fixture: str, out_of_range_year: int | None
):
    body = (_FIXTURES / fixture).read_bytes()
    transport = MockTransport(200, body)
    install_mock(monkeypatch, f"thesisagents.sources.{source}.fetcher", transport)
    papers = await _fetcher(source).search(
        Query(keywords="LLM Security", sources=(source,), max_results=10, year_from=2025)
    )
    undated = [p for p in papers if p.title.startswith(_UNDATED_TITLE)]
    assert len(undated) == 1, f"{source} dropped the paper of unknown year"
    assert undated[0].year is None
    # The local filter still removes a dated paper that is out of range.
    assert all(p.year is None or p.year >= 2025 for p in papers)
    if out_of_range_year is not None:
        assert out_of_range_year not in {p.year for p in papers}


def test_shared_rule_keeps_unknown_year_and_bounds_known_years():
    assert year_in_range(None, 2024, 2026) is True
    assert year_in_range(None, None, None) is True
    assert year_in_range(2025, 2024, 2026) is True
    assert year_in_range(2023, 2024, 2026) is False
    assert year_in_range(2027, 2024, 2026) is False
    assert year_in_range(2025, None, None) is True

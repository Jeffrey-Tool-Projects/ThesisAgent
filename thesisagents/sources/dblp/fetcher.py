"""DBLP fetcher.

Endpoint:
- Search: GET https://dblp.org/search/publ/api?q=KEY&format=json&h=N

DBLP is the de-facto CS bibliography. No API key, no authentication. The
``publ`` endpoint returns publication metadata; we get the JSON variant via
``format=json``. Year filtering is not directly supported by the API — we
post-filter in the parser layer because DBLP's `year:YYYY` operator only
matches exact years and the operator's behaviour is undocumented for ranges.

Rate limit: DBLP has no published per-second cap but their ops page asks for
"reasonable" use; we stay under 2 req/s with a small burst.
"""

from __future__ import annotations

from thesisagents.core.exceptions import (
    ParseError,
    RateLimitError,
    SourceUnavailableError,
)
from thesisagents.core.models import Paper, Query
from thesisagents.core.query import year_in_range
from thesisagents.fetchers.base import Fetcher, FetcherConfig
from thesisagents.fetchers.http import get_client
from thesisagents.fetchers.rate_limit import RateLimit
from thesisagents.utils.logging import get_logger

from .parser import parse_hit

_LOG = get_logger(__name__)
_SOURCE_NAME = "dblp"
_SEARCH_ENDPOINT = "https://dblp.org/search/publ/api"
_MAX_HITS_PER_PAGE = 1000


class DblpFetcher(Fetcher):
    """Strategy implementation for DBLP."""

    config = FetcherConfig(
        name=_SOURCE_NAME,
        # DBLP rejects sustained traffic with transient 5xx from a single IP.
        # 1 req per 2s with jitter stays well below the threshold I've
        # observed in practice.
        rate_limit=RateLimit(requests_per_second=0.5, burst=1, jitter_seconds=0.3),
        requires_api_key=False,
        enabled_by_default=False,  # plugin: needs explicit --source dblp
    )

    async def search(self, query: Query) -> list[Paper]:
        params = self._build_search_params(query)
        data = await self._request(_SEARCH_ENDPOINT, params=params)
        hits = (
            (data.get("result") or {})
            .get("hits", {})
            .get("hit", [])
        )
        papers = [parse_hit(hit) for hit in hits]
        if query.year_from is not None or query.year_to is not None:
            papers = [
                p for p in papers
                if year_in_range(p.year, query.year_from, query.year_to)
            ]
        _LOG.info(
            "DBLP returned %d papers for query=%r (max=%d)",
            len(papers),
            query.keywords,
            query.max_results,
        )
        return papers[: query.max_results]

    def _build_search_params(self, query: Query) -> dict[str, str]:
        per_page = min(query.max_results * 2, _MAX_HITS_PER_PAGE)
        return {
            "q": query.keywords,
            "format": "json",
            "h": str(per_page),
        }

    async def _request(self, url: str, *, params: dict[str, str]) -> dict:
        await self.bucket.acquire()
        client = await get_client(_SOURCE_NAME)
        try:
            response = await client.get(url, params=params)
        except Exception as err:
            raise SourceUnavailableError(
                _SOURCE_NAME, f"network error: {err}"
            ) from err
        if response.status_code == 429:
            raise RateLimitError(_SOURCE_NAME, "DBLP rate limit hit")
        if response.status_code >= 500:
            # DBLP's FAQ explicitly notes the search API returns transient
            # 5xx when the service is heavily loaded — treat 5xx as a soft
            # rate-limit so the pipeline's exponential-backoff retry kicks
            # in instead of failing the whole source.
            raise RateLimitError(
                _SOURCE_NAME, f"transient server error {response.status_code}"
            )
        if response.status_code >= 400:
            raise ParseError(
                _SOURCE_NAME,
                f"client error {response.status_code}: {response.text[:256]}",
            )
        try:
            return response.json()
        except ValueError as err:
            raise _non_json_error(response) from err


#: Signs of the bot-check page DBLP served on 2026-11-19 (an Anubis
#: proof-of-work wall: HTTP 202, text/html, "Making sure you're not a bot!",
#: assets under ``/.within.website/``). It needs a JavaScript browser to
#: pass, so retrying the API request cannot help.
_BOT_CHECK_MARKERS = ("not a bot", ".within.website", "anubis")


def _non_json_error(response) -> RateLimitError | ParseError | SourceUnavailableError:
    """The error for a 2xx DBLP reply whose body is not JSON.

    Why (``progress.md`` #12): one search on 2026-10-08 failed with
    ``[dblp] invalid JSON: Expecting value: line 1 column 1 (char 0)``,
    and nothing in that message said what DBLP had sent. On 2026-11-19 a
    live check showed one cause: DBLP served an Anubis bot-check page
    (HTTP 202, text/html) in place of the API answer. Three cases are told
    apart now, and every message carries the status, the content type and
    the first bytes of the body, so the next one can be diagnosed from the
    Sources line alone:

    * the bot-check page is a :class:`SourceUnavailableError`: it needs a
      JavaScript browser to pass, so a retry cannot help and the source is
      reported as failed at once;
    * any other empty body or HTML page (maintenance, overload) is a
      :class:`RateLimitError`, which the pipeline retries with backoff, the
      same treatment the FAQ-documented transient 5xx gets above;
    * anything else (truncated JSON, a format change) stays a
      :class:`ParseError`.

    Example: a 200 with ``text/html`` and ``<html>Service unavailable``
    gives ``RateLimitError("... not JSON (status 200, text/html): <html>...")``.
    """
    content_type = response.headers.get("content-type", "") or "no content type"
    body = response.text.strip()
    snippet = " ".join(body[:120].split()) or "<empty body>"
    detail = f"not JSON (status {response.status_code}, {content_type}): {snippet}"
    if any(marker in body.lower() for marker in _BOT_CHECK_MARKERS):
        return SourceUnavailableError(
            _SOURCE_NAME,
            "DBLP is showing a bot-check page instead of search results, a retry cannot "
            f"pass it, try again later or leave dblp out of the sources, {detail}",
        )
    looks_like_a_page = not body or body.startswith("<") or "html" in content_type.lower()
    if looks_like_a_page:
        return RateLimitError(_SOURCE_NAME, f"answered with a page instead of results, {detail}")
    return ParseError(_SOURCE_NAME, f"invalid JSON, {detail}")

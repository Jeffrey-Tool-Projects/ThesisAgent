"""Concurrent searches of one source share its rate and burst (code review R18).

Every search loads a new fetcher, and each fetcher used to build its own token
bucket that started full. Two searches running at the same time therefore each
sent their first request at once, although Semantic Scholar's policy is one
request per second with a burst of one. Now every fetcher of a source draws on
one bucket per process (``shared_bucket``).

The tests run on a virtual clock: ``VirtualClock.sleep`` parks the caller until
the driver moves the clock to its wake-up time, so the send times are exact and
no test waits in real time.
"""

from __future__ import annotations

import asyncio
import heapq
import itertools
import threading

import httpx
import pytest

from tests.sources._mock import install_mock
from thesisagents.core.models import Query
from thesisagents.fetchers import rate_limit
from thesisagents.fetchers.base import load_fetcher
from thesisagents.fetchers.rate_limit import RateLimit, TokenBucket, shared_bucket

_S2_BODY = b'{"total": 0, "data": []}'


class VirtualClock:
    """A clock that only moves when every task is waiting on it."""

    def __init__(self) -> None:
        self.now = 0.0
        self._sleepers: list[tuple[float, int, asyncio.Future[None]]] = []
        self._order = itertools.count()

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        if delay <= 0:
            await asyncio.sleep(0)
            return
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        heapq.heappush(self._sleepers, (self.now + delay, next(self._order), future))
        await future

    async def run(self, *coros):
        """Run ``coros`` together, moving the clock whenever all of them wait."""
        tasks = [asyncio.ensure_future(coro) for coro in coros]
        while not all(task.done() for task in tasks):
            for _ in range(20):  # let every runnable task reach its next wait
                await asyncio.sleep(0)
            # A sleeper whose task was cancelled has nothing left to wake.
            while self._sleepers and self._sleepers[0][2].done():
                heapq.heappop(self._sleepers)
            if self._sleepers and not all(task.done() for task in tasks):
                wake, _, future = heapq.heappop(self._sleepers)
                self.now = max(self.now, wake)
                future.set_result(None)
        return [task.result() for task in tasks]


@pytest.fixture
def clock(monkeypatch) -> VirtualClock:
    virtual = VirtualClock()
    monkeypatch.setattr(rate_limit, "_monotonic", virtual)
    monkeypatch.setattr(rate_limit, "_sleep", virtual.sleep)
    # Jitter would shift each send by a random amount and blur the spacing.
    monkeypatch.setattr(rate_limit.random, "uniform", lambda _low, _high: 0.0)
    return virtual


class _TimedTransport(httpx.AsyncBaseTransport):
    """Answer every request and note the virtual time it was sent at."""

    def __init__(self, clock: VirtualClock) -> None:
        self._clock = clock
        self.sent_at: list[float] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.sent_at.append(self._clock())
        return httpx.Response(200, content=_S2_BODY, request=request)

    async def aclose(self) -> None:
        return None


async def test_two_concurrent_searches_share_one_semantic_scholar_quota(monkeypatch, clock):
    transport = _TimedTransport(clock)
    install_mock(monkeypatch, "thesisagents.sources.semantic_scholar.fetcher", transport)

    async def one_search(keywords: str) -> None:
        # What the pipeline does per search: load a fresh fetcher, then search.
        fetcher = load_fetcher("semantic_scholar")
        for page in range(2):
            await fetcher.search(
                Query(keywords=f"{keywords} {page}", sources=("semantic_scholar",))
            )

    await clock.run(one_search("graph networks"), one_search("vision transformers"))
    # One request per second with a burst of one, across both searches.
    assert transport.sent_at == [0.0, 1.0, 2.0, 3.0]


async def test_burst_is_shared_and_refills_at_the_rate(clock):
    policy = RateLimit(requests_per_second=2.0, burst=3)
    first = shared_bucket("example", policy)
    second = shared_bucket("example", policy)
    assert first is second
    sent: list[float] = []

    async def requests(count: int) -> None:
        for _ in range(count):
            await shared_bucket("example", policy).acquire()
            sent.append(clock())

    await clock.run(requests(3), requests(3))
    # Three at once from the burst of three, then one every half second.
    assert sorted(sent) == [0.0, 0.0, 0.0, 0.5, 1.0, 1.5]


def test_one_bucket_serves_several_event_loops_in_threads():
    """GUI workers each run their own loop. The bucket must not bind to one."""
    bucket = TokenBucket(RateLimit(requests_per_second=50.0, burst=1))
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            asyncio.run(bucket.acquire())
        except BaseException as err:  # noqa: BLE001  # the assertion below reports it
            errors.append(err)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert errors == []
    assert all(not thread.is_alive() for thread in threads)


async def test_a_cancelled_waiter_returns_its_slot(clock):
    bucket = TokenBucket(RateLimit(requests_per_second=1.0, burst=1))
    await bucket.acquire()  # takes the burst at t=0

    async def cancelled_waiter() -> None:
        waiter = asyncio.ensure_future(bucket.acquire())  # would get t=1
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

    async def later() -> float:
        await bucket.acquire()
        return clock()

    await clock.run(cancelled_waiter())
    [sent] = await clock.run(later())
    assert sent == 1.0


def test_a_changed_policy_gets_a_new_bucket():
    old = shared_bucket("example", RateLimit(requests_per_second=1.0))
    new = shared_bucket("example", RateLimit(requests_per_second=10.0))
    assert new is not old
    assert new.policy.requests_per_second == 10.0


def test_sources_on_the_same_upstream_share_one_bucket():
    """ACM searches through the Crossref API, so it draws on Crossref's quota."""
    crossref = load_fetcher("crossref")
    assert load_fetcher("acm").bucket is crossref.bucket
    assert load_fetcher("semantic_scholar").bucket is load_fetcher("semantic_scholar").bucket
    assert load_fetcher("arxiv").bucket is not crossref.bucket

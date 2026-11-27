"""Per-source token-bucket rate limit, shared by every search of the process.

Retries go through it too. One bucket exists per upstream service (see
:func:`shared_bucket`), so two searches running at the same time, from the
MCP server, the CLI or two GUI worker threads, draw on one quota instead of
each getting the full burst.
"""

from __future__ import annotations

import asyncio
import random
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

#: The clock and the sleep a new bucket uses unless it is given its own. Read
#: when the bucket is built, so a test can swap them for a virtual clock
#: before the fetchers it exercises are loaded.
_monotonic: Callable[[], float] = time.monotonic
_sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass(frozen=True, slots=True)
class RateLimit:
    """Declarative rate-limit policy for a single source."""

    requests_per_second: float
    burst: int = 1
    jitter_seconds: float = 0.0


class TokenBucket:
    """Token bucket that is safe to share across threads and event loops.

    The state is guarded by a ``threading.Lock`` that is held only for the
    arithmetic, never across an ``await``, and the wait itself is an
    ``asyncio.sleep`` on the caller's own loop. **Failure mode prevented**: the
    old bucket held an ``asyncio.Lock``, which belongs to the loop that first
    used it, so one bucket could not be shared by GUI workers that each run
    their own loop with ``asyncio.run``. Each search therefore built a fresh,
    full bucket and two concurrent searches together sent twice the burst.

    ``acquire`` reserves the next free slot under the lock and then sleeps
    until it, so callers are served in arrival order. A caller cancelled while
    it waits hands its slot back.

    Example::

        bucket = TokenBucket(RateLimit(requests_per_second=1.0, burst=1))
        await bucket.acquire()   # at once, the bucket starts full
        await bucket.acquire()   # about one second later
    """

    def __init__(
        self,
        policy: RateLimit,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if policy.requests_per_second <= 0:
            raise ValueError("requests_per_second must be > 0")
        self._policy = policy
        self._clock = clock if clock is not None else _monotonic
        self._sleep = sleep if sleep is not None else _sleep
        self._capacity = float(max(1, policy.burst))
        self._tokens = self._capacity
        self._last_refill = self._clock()
        self._lock = threading.Lock()

    @property
    def policy(self) -> RateLimit:
        """The policy this bucket enforces."""
        return self._policy

    async def acquire(self) -> None:
        """Wait until a request may be sent, then take its token."""
        wait, cost = self._reserve()
        if wait > 0:
            try:
                await self._sleep(wait)
            except asyncio.CancelledError:
                self._refund(cost)
                raise

    def _reserve(self) -> tuple[float, float]:
        """Take a token, possibly one not refilled yet. Returns the wait and its cost.

        The token count may go below zero: each negative unit is a slot that a
        waiting caller has already claimed, so the next caller's wait already
        includes the callers ahead of it.

        The jitter is part of the slot. **Failure mode prevented**: added as
        a sleep after the token was taken, a caller delayed by its jitter
        could send right before the next caller's slot, closer to it than
        ``1 / requests_per_second``. Charged here, it pushes the slots behind
        it back by the same amount.
        """
        jitter = (
            random.uniform(0, self._policy.jitter_seconds)  # noqa: S311  # nosec B311  # jitter only, not security-relevant
            if self._policy.jitter_seconds > 0 else 0.0
        )
        with self._lock:
            now = self._clock()
            elapsed = max(0.0, now - self._last_refill)
            self._last_refill = now
            rate = self._policy.requests_per_second
            self._tokens = min(self._capacity, self._tokens + elapsed * rate)
            cost = 1.0 + jitter * rate
            self._tokens -= cost
            until_token = max(0.0, -(self._tokens + jitter * rate) / rate)
            return until_token + jitter, cost

    def _refund(self, cost: float) -> None:
        """Give back the slot of a caller that was cancelled while waiting."""
        with self._lock:
            self._tokens = min(self._capacity, self._tokens + cost)


_SHARED: dict[str, TokenBucket] = {}
_SHARED_LOCK = threading.Lock()


def shared_bucket(upstream: str, policy: RateLimit) -> TokenBucket:
    """The one bucket for ``upstream`` in this process, built on first use.

    Every fetcher and citation provider of the same upstream service asks for
    it by the same name, so their requests share one rate and one burst.
    **Failure mode prevented**: each search loaded a new fetcher with a new,
    full bucket, so two MCP searches could both send a Semantic Scholar
    request at once although the policy allows one per second with a burst of
    one.

    A bucket built for a different policy (the policy changed during the
    session) is replaced, so the newest policy applies to new requests.

    Example::

        first = shared_bucket("semantic_scholar", RateLimit(1.0))
        assert shared_bucket("semantic_scholar", RateLimit(1.0)) is first
    """
    with _SHARED_LOCK:
        bucket = _SHARED.get(upstream)
        if bucket is None or bucket.policy != policy:
            bucket = TokenBucket(policy)
            _SHARED[upstream] = bucket
        return bucket


def clear_shared_buckets() -> None:
    """Forget every shared bucket, so the next request starts with a full one.

    For tests, which must not wait for a quota an earlier test used up.
    """
    with _SHARED_LOCK:
        _SHARED.clear()

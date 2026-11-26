"""HTTPS-only shared HTTP client registry.

All outbound HTTP goes through `get_client(source)`. The transport rejects any
non-HTTPS request (including redirect targets) so a misconfigured endpoint or a
malicious redirect cannot exfiltrate over plain HTTP. It also rejects addresses
of this machine and of private networks: PDF links come from third-party
metadata, and a link to `https://192.168.1.1/` would make the app call the
user's router. Only literal addresses are checked, not what a name resolves
to, because a university proxy commonly has a private address.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from thesisagents import __version__
from thesisagents.core.constants import HTTP_TIMEOUT_SECONDS
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)


def is_local_host(host: str) -> bool:
    """True for this machine's names and for non-public IP address literals.

    >>> is_local_host("localhost"), is_local_host("10.0.0.5"), is_local_host("arxiv.org")
    (True, True, False)
    """
    name = host.strip("[]").rstrip(".").lower()
    if name == "localhost" or name.endswith(".localhost"):
        return True
    try:
        return not ipaddress.ip_address(name).is_global
    except ValueError:
        return False


class HttpsOnlyTransport(httpx.AsyncBaseTransport):
    """Wrap an underlying transport, reject non-HTTPS and local-network requests."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        scheme = request.url.scheme
        if scheme != "https":
            raise httpx.RequestError(
                f"refusing non-HTTPS request to {request.url}",
                request=request,
            )
        if is_local_host(request.url.host):
            raise httpx.RequestError(
                f"refusing a request to the local network: {request.url}",
                request=request,
            )
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


@dataclass(frozen=True, slots=True)
class _ClientKey:
    """A client is shared within one event loop, the one its sockets belong to.

    The desktop app gives every worker a loop of its own. With the source
    alone as the key, the second paper of an enrichment run got the first
    one's client and failed with "Event loop is closed", and the end of one
    worker closed the clients of another that was still searching.
    """

    source: str
    loop: asyncio.AbstractEventLoop


_CLIENTS: dict[_ClientKey, httpx.AsyncClient] = {}
#: A thread lock, held for dictionary work only: loops run on several threads.
_LOCK = threading.Lock()


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

_LLM_TIMEOUT_SECONDS = 600.0

# Sources that are scraped from human-facing pages must look like a browser
# or the upstream returns 403 / 418. The HTTPS-only + rate-limit guardrails
# still apply.
_BROWSER_UA_SOURCES = frozenset({"ieee", "scholar"})


def _user_agent_for(source: str) -> str:
    if source in _BROWSER_UA_SOURCES:
        return _BROWSER_UA
    return f"ThesisAgents/{__version__} (source={source})"


def _build_client(source: str) -> httpx.AsyncClient:
    inner = httpx.AsyncHTTPTransport(retries=0)
    transport = HttpsOnlyTransport(inner)
    return httpx.AsyncClient(
        transport=transport,
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={
            "User-Agent": _user_agent_for(source),
            "Accept-Encoding": "gzip, deflate",
        },
    )


async def get_client(source: str) -> httpx.AsyncClient:
    """Return the shared async client of ``source`` in the running loop, built lazily."""
    key = _ClientKey(source=source, loop=asyncio.get_running_loop())
    with _LOCK:
        client = _CLIENTS.get(key)
        if client is None:
            # Clients whose loop ended cannot be used or closed any more.
            for stale in [known for known in _CLIENTS if known.loop.is_closed()]:
                del _CLIENTS[stale]
            client = _build_client(source)
            _CLIENTS[key] = client
            _LOG.debug("Constructed HTTP client for source=%s", source)
    return client


@contextlib.asynccontextmanager
async def scoped_client(source: str) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTPS-only client that lives for one ``async with`` block.

    Same transport, timeout and User-Agent rules as :func:`get_client`, but the
    client is not put in the shared registry and is closed when the block ends.

    Why it exists: a registry client belongs to the event loop that created
    it. Code that may run on a private, short-lived loop (the export preflight
    under ``run_blocking``, which starts a fresh loop per call) would leave a
    client in the registry bound to a loop that has already closed, and the
    next caller would fail with ``Event loop is closed``.

    Example::

        async with scoped_client("identifier_preflight") as client:
            response = await client.get("https://doi.org/api/handles/10.1/x")

    Anti-pattern: ``httpx.AsyncClient()`` built by hand for the same purpose.
    That skips the HTTPS-only transport, which is the guarantee every outbound
    request in this package relies on.
    """
    client = _build_client(source)
    try:
        yield client
    finally:
        await client.aclose()


class _LlmTransport(httpx.BaseTransport):
    """Lets requests through to one host only, the model server the user chose.

    Plain HTTP is allowed when that host is this computer or a private
    address, where a local model server listens. Anywhere else it must be
    HTTPS: the request carries an API key and the text of a paper.
    """

    def __init__(self, inner: httpx.BaseTransport, host: str) -> None:
        self._inner = inner
        self._host = host

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host != self._host:
            raise httpx.RequestError(f"refusing a request to {host}", request=request)
        if request.url.scheme != "https" and not is_local_host(host):
            raise httpx.RequestError(
                f"refusing non-HTTPS request to {request.url}", request=request
            )
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


def llm_client(base_url: str) -> httpx.Client:
    """A blocking client for the language model server at ``base_url``.

    The one sanctioned sibling of :func:`get_client` that may reach this
    computer, because a local model runs there. It is bound to the host of
    ``base_url`` and follows no redirect, so neither a key nor a paper goes
    anywhere else. A local model can take minutes to answer, hence the
    timeout.

    Example::

        with llm_client("http://localhost:11434/v1") as client:
            client.post("http://localhost:11434/v1/chat/completions", json=body)
    """
    return httpx.Client(
        transport=_LlmTransport(httpx.HTTPTransport(retries=0), httpx.URL(base_url).host),
        timeout=httpx.Timeout(_LLM_TIMEOUT_SECONDS, connect=HTTP_TIMEOUT_SECONDS),
        follow_redirects=False,
        # A proxy from the environment would see local requests.
        trust_env=not is_local_host(httpx.URL(base_url).host),
        headers={"User-Agent": _user_agent_for("llm")},
    )


async def shutdown_clients() -> None:
    """Close the running loop's shared clients. Call at the end of a run.

    Clients of another loop that is still running belong to another
    worker and are left alone. Those of a loop that has already closed
    cannot be closed from here, so they are only dropped from the
    registry and the OS reclaims the dangling sockets.
    """
    current = asyncio.get_running_loop()
    with _LOCK:
        own = [key for key in _CLIENTS if key.loop is current]
        clients = [_CLIENTS.pop(key) for key in own]
        for key in [known for known in _CLIENTS if known.loop.is_closed()]:
            del _CLIENTS[key]
    for client in clients:
        try:
            await client.aclose()
        except RuntimeError as err:
            # "Event loop is closed" / "got Future <...> attached to a
            # different loop" — the client outlived its loop. Nothing
            # we can do at this point that's safer than letting GC
            # reap the connection pool.
            _LOG.debug("client.aclose() raised %r; dropping silently", err)

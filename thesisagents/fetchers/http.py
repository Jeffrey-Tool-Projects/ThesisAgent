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
    source: str


_CLIENTS: dict[_ClientKey, httpx.AsyncClient] = {}
_LOCK = asyncio.Lock()


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
    """Return the per-source shared async client, lazily constructed."""
    key = _ClientKey(source=source)
    client = _CLIENTS.get(key)
    if client is not None:
        return client
    async with _LOCK:
        client = _CLIENTS.get(key)
        if client is None:
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
    """Close all shared clients. Call from app shutdown / CLI exit.

    Tolerates clients whose original event loop has already closed —
    that happens in the test suite where each ``asyncio.run`` spins
    its own loop, and a client cached during an earlier test cannot
    be re-closed in a later loop's context. We drop those clients
    from the registry; the OS will reclaim the dangling sockets.
    """
    async with _LOCK:
        clients = list(_CLIENTS.values())
        _CLIENTS.clear()
    for client in clients:
        try:
            await client.aclose()
        except RuntimeError as err:
            # "Event loop is closed" / "got Future <...> attached to a
            # different loop" — the client outlived its loop. Nothing
            # we can do at this point that's safer than letting GC
            # reap the connection pool.
            _LOG.debug("client.aclose() raised %r; dropping silently", err)

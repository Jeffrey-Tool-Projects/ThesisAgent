"""The HTTPS-only transport must refuse plain HTTP requests."""

from __future__ import annotations

import httpx
import pytest

from thesisagents.fetchers.http import HttpsOnlyTransport, is_local_host


class _PassthroughTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request):
        return httpx.Response(200, content=b"ok")

    async def aclose(self):
        return None


async def test_rejects_http():
    transport = HttpsOnlyTransport(_PassthroughTransport())
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.RequestError):
            await client.get("http://example.com/path")


async def test_accepts_https():
    transport = HttpsOnlyTransport(_PassthroughTransport())
    async with httpx.AsyncClient(transport=transport) as client:
        resp = await client.get("https://example.com/path")
    assert resp.status_code == 200


async def test_scoped_client_refuses_plain_http_and_stays_out_of_the_registry():
    """``scoped_client`` must keep the HTTPS-only guarantee of ``get_client``
    while never registering the client it hands out."""
    from thesisagents.fetchers import http as http_module

    http_module._CLIENTS.clear()  # noqa: SLF001  # start from an empty registry
    async with http_module.scoped_client("identifier_preflight") as client:
        assert isinstance(client._transport, HttpsOnlyTransport)  # noqa: SLF001
        assert client.headers["User-Agent"].startswith("ThesisAgents/")
        with pytest.raises(httpx.RequestError, match="refusing non-HTTPS"):
            await client.get("http://example.com/path")
        assert http_module._CLIENTS == {}  # noqa: SLF001
    assert client.is_closed


async def test_scoped_client_is_closed_when_the_block_raises():
    from thesisagents.fetchers import http as http_module

    with pytest.raises(RuntimeError, match="boom"):  # NOSONAR the exit on a raise is under test
        async with http_module.scoped_client("identifier_preflight") as client:
            raise RuntimeError("boom")
    assert client.is_closed


@pytest.mark.parametrize("host", [
    "localhost", "LOCALHOST.", "db.localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1",
    "172.16.3.4", "169.254.169.254", "0.0.0.0",  # noqa: S104 - a value to refuse
    "::1", "[::1]", "fe80::1", "fd00::7",
])
def test_local_hosts_are_recognised(host):
    assert is_local_host(host)


@pytest.mark.parametrize("host", ["arxiv.org", "localhost.example", "8.8.8.8", "2606:4700::1111"])
def test_public_hosts_are_not_local(host):
    assert not is_local_host(host)


async def test_transport_refuses_the_local_network_also_after_a_redirect():
    """A PDF link is third-party metadata: one to the user's router, or a
    redirect to a cloud metadata address, must not be requested."""
    asked = []

    class _Redirecting(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            asked.append(request.url.host)
            return httpx.Response(
                302, headers={"location": "https://169.254.169.254/latest"}, request=request
            )

    transport = HttpsOnlyTransport(_Redirecting())
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        with pytest.raises(httpx.RequestError, match="local network"):
            await client.get("https://192.168.1.1/admin")
        with pytest.raises(httpx.RequestError, match="local network"):
            await client.get("https://arxiv.org/pdf/1.pdf")
    assert asked == ["arxiv.org"]

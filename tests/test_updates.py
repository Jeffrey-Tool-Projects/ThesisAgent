"""The update check: which versions count, and that it never fails loudly."""
from __future__ import annotations

import tomllib
from contextlib import asynccontextmanager
from importlib import metadata
from pathlib import Path

import httpx
import pytest

import thesisagents
from thesisagents.core import updates

_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("candidate", "current", "expected"), [
    ("0.1.27", "0.1.26", True),
    ("0.1.10", "0.1.9", True),
    ("1.0.0", "0.99.99", True),
    ("0.1.26", "0.1.26", False),
    ("0.1.25", "0.1.26", False),
    ("0.2.0rc1", "0.1.26", False),
    ("", "0.1.26", False),
    ("0.1.27", "0.1.26.dev3", False),
])
def test_only_later_plain_releases_are_newer(candidate, current, expected):
    assert updates.is_newer(candidate, current) is expected


def _answer(monkeypatch, handler):
    @asynccontextmanager
    async def fake_client(source):
        assert source == "updates"
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            yield client

    monkeypatch.setattr(updates, "scoped_client", fake_client)


async def test_the_latest_release_is_reported(monkeypatch):
    asked = []

    def handler(request):
        asked.append(str(request.url))
        return httpx.Response(200, json={"info": {"version": "0.2.0"}})

    _answer(monkeypatch, handler)
    assert await updates.newer_version("0.1.26") == "0.2.0"
    assert await updates.newer_version("0.2.0") is None
    assert asked == [updates.PYPI_URL] * 2


@pytest.mark.parametrize("response", [
    httpx.Response(503), httpx.Response(200, text="<html>"), httpx.Response(200, json={}),
])
async def test_an_odd_answer_means_no_news(monkeypatch, response):
    _answer(monkeypatch, lambda _request: response)
    assert await updates.newer_version("0.1.26") is None


async def test_being_offline_means_no_news(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    _answer(monkeypatch, handler)
    assert await updates.newer_version("0.1.26") is None


def test_the_version_comes_from_the_installed_package(monkeypatch):
    # The constant still said 0.1.0 at v0.1.26, so no update check could work.
    assert thesisagents.__version__ == metadata.version("thesisagents")

    def missing(_name):
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(thesisagents._metadata, "version", missing)  # noqa: SLF001
    assert thesisagents._installed_version() == "0.0.0"  # noqa: SLF001


def test_the_release_bundles_the_version_and_the_credential_backends():
    release = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "--include-distribution-metadata=thesisagents " in release
    assert "--include-package=keyring.backends " in release


def test_the_installer_is_built_from_a_pinned_compiler_and_cleans_only_its_own_folder():
    release = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "INNO_SHA256: " in release
    built = release.index("packaging/windows/thesisagents.iss")
    assert release.index("split_windows_exe.py") < built
    script = (_ROOT / "packaging" / "windows" / "thesisagents.iss").read_text(encoding="utf-8")
    # A wildcard delete without the check would empty whatever folder the
    # user picked to install into.
    assert "[InstallDelete]" not in script
    assert script.count("DelTree(") == 1
    assert script.index("or not IsOwnFolder then") < script.index("DelTree(")
    assert "PrivilegesRequired=lowest" in script
    version = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert updates.parse_version(version["project"]["version"]) is not None

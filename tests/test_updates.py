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
    assert await updates.newer_version("0.1.26", desktop=False) == "0.2.0"
    assert await updates.newer_version("0.2.0", desktop=False) is None
    assert asked == [updates.PYPI_URL] * 2


@pytest.mark.parametrize("response", [
    httpx.Response(503), httpx.Response(200, text="<html>"), httpx.Response(200, json={}),
])
async def test_an_odd_answer_means_no_news(monkeypatch, response):
    _answer(monkeypatch, lambda _request: response)
    assert await updates.newer_version("0.1.26", desktop=False) is None
    assert await updates.newer_version("0.1.26", desktop=True) is None


async def test_being_offline_means_no_news(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("offline", request=request)

    _answer(monkeypatch, handler)
    assert await updates.newer_version("0.1.26") is None


def _github(release):
    return lambda request: (
        httpx.Response(200, json=release) if request.url == updates.GITHUB_LATEST_URL
        else httpx.Response(200, json={"info": {"version": "0.9.9"}})
    )


@pytest.mark.parametrize(("release", "expected"), [
    # PyPI already has 0.9.9, but the Windows build of it is not out yet.
    ({"tag_name": "v0.1.27", "assets": [{"name": updates.INSTALLER_ASSET}]}, "0.1.27"),
    ({"tag_name": "v0.1.28", "assets": [{"name": "thesisagents-windows-x86_64.zip"}]}, None),
    ({"tag_name": "v0.1.28", "draft": True, "assets": [{"name": updates.INSTALLER_ASSET}]}, None),
    ({"tag_name": "v0.1.26", "assets": [{"name": updates.INSTALLER_ASSET}]}, None),
])
async def test_the_desktop_app_announces_only_a_release_with_its_installer(
    monkeypatch, release, expected
):
    _answer(monkeypatch, _github(release))
    assert await updates.newer_version("0.1.26", desktop=True) == expected


def test_a_pip_install_is_not_the_desktop_build():
    assert updates.is_desktop_build() is False


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


def _installer_script() -> str:
    return (_ROOT / "packaging" / "windows" / "thesisagents.iss").read_text(encoding="utf-8")


def test_the_installer_is_built_from_a_pinned_compiler():
    release = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "INNO_SHA256: " in release
    built = release.index("packaging/windows/thesisagents.iss")
    assert release.index("split_windows_exe.py") < built
    assert "PrivilegesRequired=lowest" in _installer_script()


def test_an_update_removes_only_the_files_the_last_version_installed():
    # It emptied the whole folder, a library or PDFs saved there included.
    script = _installer_script()
    assert "[InstallDelete]" not in script
    assert "DelTree(" not in script and "FindFirst(" not in script
    assert "AfterInstall: RecordFile" in script
    assert r"InstalledFiles.SaveToFile(ExpandConstant('{app}\{#Manifest}'))" in script
    removal = script[script.index("procedure RemovePreviousFiles"):]
    assert removal.index("LoadStringsFromFile") < removal.index("DeleteFile(")
    assert removal.index("InProgramFolder(Lines[Index])") < removal.index("DeleteFile(")
    assert r'Type: files; Name: "{app}\{#Manifest}"' in script


def test_uninstalling_leaves_a_path_entry_the_installer_did_not_add():
    script = _installer_script()
    note, path = (
        script.index('ValueName: "AddedToPath"'), script.index('ValueName: "Path"'),
    )
    # The note comes first: once the path is added, NotOnPath is false.
    assert note < path
    uninstall = script[script.index("procedure CurUninstallStepChanged"):]
    assert "'AddedToPath'" in uninstall
    assert "not RemoveFromPath then" in uninstall
    assert uninstall.index("RegQueryDWordValue") < uninstall.index("RegWriteExpandStringValue")


def test_the_release_is_built_from_the_commit_ci_passed():
    # Checking out main released a newer commit whose CI was still running.
    release = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    bump = release[release.index("  bump-version:"):release.index("  publish-pypi:")]
    assert "ref: ${{ github.event.workflow_run.head_sha }}" in bump
    assert "ref: main" not in bump
    assert 'if [ "$(git rev-parse origin/main)" != "$PASSED_SHA" ]; then' in bump
    assert "git push origin HEAD:main" in bump and "--force" not in bump
    version = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert updates.parse_version(version["project"]["version"]) is not None

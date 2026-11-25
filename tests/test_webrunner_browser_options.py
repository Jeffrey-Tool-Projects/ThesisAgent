"""How the project starts Chrome: visible, sandboxed, Safe Browsing left on."""
from __future__ import annotations

import pytest

from thesisagents.fetchers import webrunner_browser


def test_chrome_is_visible_and_sandboxed_on_a_desktop(monkeypatch):
    monkeypatch.delenv("THESISAGENTS_CHROME_PROFILE_DIR", raising=False)
    monkeypatch.setattr(webrunner_browser, "_is_root_on_linux", lambda: False)
    arguments = webrunner_browser.chrome_arguments()
    assert not any(a.startswith("--headless") for a in arguments)
    assert "--no-sandbox" not in arguments
    assert "--disable-blink-features=AutomationControlled" in arguments
    assert not any(a.startswith("--user-data-dir=") for a in arguments)


def test_the_profile_dir_is_passed_on(monkeypatch):
    monkeypatch.setenv("THESISAGENTS_CHROME_PROFILE_DIR", "D:/scholar-profile")
    arguments = webrunner_browser.chrome_arguments()
    assert "--user-data-dir=D:/scholar-profile" in arguments
    assert not any(a.startswith("--headless") for a in arguments)


@pytest.mark.parametrize(("platform", "uid", "expected"), [
    ("linux", 0, True), ("linux", 1000, False), ("win32", 0, False), ("darwin", 0, False),
])
def test_the_sandbox_is_off_only_for_root_on_linux(monkeypatch, platform, uid, expected):
    monkeypatch.setattr(webrunner_browser.sys, "platform", platform)
    monkeypatch.setattr(webrunner_browser.os, "geteuid", lambda: uid, raising=False)
    assert ("--no-sandbox" in webrunner_browser.chrome_arguments()) is expected


def test_downloads_do_not_switch_safe_browsing_off(monkeypatch, tmp_path):
    webdriver = pytest.importorskip("selenium.webdriver")
    seen = {}
    monkeypatch.setattr(webdriver, "Chrome", lambda options: seen.update(
        prefs=options.experimental_options.get("prefs"), arguments=options.arguments))
    webrunner_browser.make_driver(download_dir=str(tmp_path))
    assert "safebrowsing.enabled" not in seen["prefs"]
    assert seen["prefs"]["download.default_directory"] == str(tmp_path)
    assert seen["arguments"] == webrunner_browser.chrome_arguments()

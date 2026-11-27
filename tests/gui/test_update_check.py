"""The GUI side of the update check: once a day, off when told so, one button."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import QThreadPool

from thesisagents.gui import update_check
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.settings import SettingsPage, saved_update_check, settings_store
from thesisagents.gui.update_check import UpdateCheck


@pytest.fixture
def pypi(monkeypatch):
    """PyPI's answer, and how often it was asked."""
    state = {"asked": 0, "answer": "0.2.0"}

    async def fake(_current):
        state["asked"] += 1
        return state["answer"]

    monkeypatch.setattr(update_check, "newer_version", fake)
    return state


def _start(qtbot, current="0.1.26"):
    check = UpdateCheck()
    heard = []
    check.found.connect(heard.append)
    if check.start(current):
        QThreadPool.globalInstance().waitForDone(3000)
        # The answer is queued to this thread.
        qtbot.wait(20)
    return heard


def test_a_release_is_reported_and_remembered_for_the_day(qtbot, pypi):
    assert _start(qtbot) == ["0.2.0"]
    assert _start(qtbot) == ["0.2.0"]
    assert pypi["asked"] == 1


def test_it_asks_again_the_next_day(qtbot, pypi):
    _start(qtbot)
    old = datetime.now(UTC) - timedelta(days=1, minutes=1)
    settings_store().setValue("updates/last_check", old.isoformat())
    _start(qtbot)
    assert pypi["asked"] == 2


@pytest.mark.parametrize("stamp", ["soon", "2999-01-01T00:00:00+00:00", "2026-01-01T00:00:00"])
def test_a_bad_time_stamp_does_not_stop_the_check(qtbot, pypi, stamp):
    settings_store().setValue("updates/last_check", stamp)
    _start(qtbot)
    assert pypi["asked"] == 1


def test_nothing_is_said_after_updating(qtbot, pypi):
    _start(qtbot)
    assert _start(qtbot, current="0.2.0") == []


def test_no_news_is_no_message(qtbot, pypi):
    pypi["answer"] = None
    assert _start(qtbot) == []


def test_switched_off_it_asks_nobody(qtbot, pypi):
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    assert page.updates_checkbox().isChecked()
    page.updates_checkbox().setChecked(False)
    page.trigger_save()
    assert saved_update_check() is False
    assert _start(qtbot) == []
    assert pypi["asked"] == 0


def test_the_window_offers_the_download_page(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(
        update_check.QDesktopServices, "openUrl", lambda url: opened.append(url.toString())
    )
    window = MainWindow(ui_language="zh-tw")
    qtbot.addWidget(window)
    assert window.update_button().isHidden()
    window.show_update("0.2.0")
    assert window.update_button().text() == "新版本 0.2.0"
    assert not window.update_button().isHidden()
    window.update_button().click()
    # The page of the version announced: /latest may be another one by then.
    assert opened == ["https://github.com/Jeffrey-Tool-Projects/ThesisAgent/releases/tag/v0.2.0"]

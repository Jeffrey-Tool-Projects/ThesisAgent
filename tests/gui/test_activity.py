"""The log window, the log file, the captcha banner and start-up failures."""

from __future__ import annotations

import logging
import sys
import threading

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from thesisagents import cli
from thesisagents.fetchers import webrunner_browser
from thesisagents.gui import activity as activity_module
from thesisagents.gui import app as gui_app
from thesisagents.gui.activity import Activity, activity, redact
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.widgets.log_dialog import LogDialog
from thesisagents.gui.widgets.notice_banner import NoticeBanner
from thesisagents.utils import notices, windows_console
from thesisagents.utils.notices import (
    CAPTCHA_CLEARED,
    CAPTCHA_TIMED_OUT,
    CAPTCHA_WAITING,
    Notice,
)


@pytest.fixture
def installed(qtbot, tmp_path, monkeypatch):
    """The activity log, writing to ``tmp_path`` and removed afterwards."""
    monkeypatch.setattr(activity_module, "log_directory", lambda: tmp_path / "logs")
    monkeypatch.setattr(activity_module, "_STATE", {})
    logger = logging.getLogger("thesisagents")
    handlers = list(logger.handlers)
    subscribers = list(notices._SUBSCRIBERS)  # noqa: SLF001
    hooks = sys.excepthook, threading.excepthook
    activity_module.install()
    yield activity()
    for handler in list(logger.handlers):
        if handler not in handlers:
            logger.removeHandler(handler)
            handler.close()
    notices._SUBSCRIBERS[:] = subscribers  # noqa: SLF001
    sys.excepthook, threading.excepthook = hooks


# --- secrets ----------------------------------------------------------------


@pytest.mark.parametrize("text", [
    "GET https://api.example/?apikey=SECRET123&q=x",
    "api_key=SECRET123",
    "https://x.example/?q=1&api-key=SECRET123 failed",
    "token=SECRET123",
])
def test_url_parameters_with_keys_are_hidden(text):
    assert "SECRET123" not in redact(text)
    assert "***" in redact(text)


def test_key_values_from_the_environment_are_hidden(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abc123")
    monkeypatch.setenv("THESISAGENTS_CROSSREF_PLUS_TOKEN", "plus-token-9")
    assert redact("Bearer sk-ant-abc123, plus-token-9") == "Bearer ***, ***"


def test_ordinary_text_is_left_alone(monkeypatch):
    monkeypatch.setenv("X_API_KEY", "a")  # too short to be a key, would hide every "a"
    assert redact("a search for keyword = attention") == "a search for keyword = attention"


# --- collecting --------------------------------------------------------------


def test_log_lines_reach_the_window_and_the_file(installed, tmp_path, monkeypatch):
    monkeypatch.setenv("THESISAGENTS_S2_API_KEY", "s2-secret-key")
    logging.getLogger("thesisagents.test").warning("搜尋 failed with s2-secret-key")
    assert "搜尋 failed with ***" in installed.text()
    for handler in logging.getLogger("thesisagents").handlers:
        handler.flush()
    written = (tmp_path / "logs" / "thesisagents.log").read_text(encoding="utf-8")
    assert "搜尋 failed with ***" in written
    assert "s2-secret-key" not in written


def test_installing_twice_does_not_double_the_lines(installed):
    activity_module.install()
    logging.getLogger("thesisagents.test").warning("once")
    assert installed.text().count("once") == 1


def test_a_profile_that_cannot_be_written_only_loses_the_file(
    qtbot, tmp_path, monkeypatch
):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(activity_module, "log_directory", lambda: blocker / "logs")
    monkeypatch.setattr(activity_module, "_STATE", {})
    logger = logging.getLogger("thesisagents")
    before = list(logger.handlers)
    hooks = sys.excepthook, threading.excepthook
    subscribers = list(notices._SUBSCRIBERS)  # noqa: SLF001
    try:
        activity_module.install()
        logging.getLogger("thesisagents.test").warning("still shown")
        assert "still shown" in activity().text()
    finally:
        for handler in list(logger.handlers):
            if handler not in before:
                logger.removeHandler(handler)
        notices._SUBSCRIBERS[:] = subscribers  # noqa: SLF001
        sys.excepthook, threading.excepthook = hooks


def test_memory_is_bounded(qtbot):
    target = Activity()
    for i in range(activity_module.MAX_LINES + 5):
        target.add_line(str(i))
    lines = target.text().split("\n")
    assert len(lines) == activity_module.MAX_LINES
    assert lines[0] == "5"
    target.clear()
    assert target.text() == ""


def test_uncaught_errors_are_logged_and_announced(installed, qtbot):
    heard = []
    installed.unexpected_error.connect(heard.append)
    try:
        raise ValueError("boom api_key=SECRET123")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    def fail():
        raise KeyError("in a thread")

    thread = threading.Thread(target=fail)
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: len(heard) == 2, timeout=2000)
    assert heard[0] == "ValueError: boom api_key=***"
    assert "Traceback" in installed.text()
    assert "in a thread" in installed.text()


def test_ctrl_c_is_not_an_error(installed, monkeypatch):
    passed_on = []
    monkeypatch.setattr(sys, "__excepthook__", lambda *args: passed_on.append(args[0]))
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert passed_on == [KeyboardInterrupt]
    assert "unexpected" not in installed.text()


# --- the log window ------------------------------------------------------------


def test_log_window_shows_old_and_new_lines_and_copies(installed, qtbot):
    installed.add_line("before")
    dialog = LogDialog("en")
    qtbot.addWidget(dialog)
    installed.add_line("after")
    assert dialog.text() == "before\nafter"
    next(b for b in dialog.findChildren(QPushButton) if b.text() == "Copy").click()
    assert QApplication.clipboard().text() == "before\nafter"


def test_the_window_opens_one_log(installed, qtbot):
    window = MainWindow(ui_language="zh-tw")
    qtbot.addWidget(window)
    first = window.show_log()
    assert first.windowTitle() == "執行紀錄"
    assert window.show_log() is first
    assert any(b.text() == "紀錄" for b in window.statusBar().findChildren(QPushButton))


# --- notices ----------------------------------------------------------------------


def test_subscribers_come_and_go(monkeypatch):
    monkeypatch.setattr(notices, "_SUBSCRIBERS", [])
    heard: list[Notice] = []

    def broken(_notice):
        raise RuntimeError("window is gone")

    notices.subscribe(broken)
    stop = notices.subscribe(heard.append)
    notices.publish(Notice(CAPTCHA_CLEARED))
    stop()
    stop()
    notices.publish(Notice(CAPTCHA_CLEARED))
    assert heard == [Notice(CAPTCHA_CLEARED)]


class _Driver:
    """A browser on a captcha page that clears after ``solved_after`` looks."""

    current_url = "https://scholar.google.com/sorry/index"
    page_source = ""

    def __init__(self, solved_after: int | None) -> None:
        self._left = solved_after

    def look(self, _driver) -> bool:
        if self._left is None:
            return True
        self._left -= 1
        return self._left >= 0


@pytest.mark.parametrize(("solved_after", "kinds"), [
    (2, [CAPTCHA_WAITING, CAPTCHA_CLEARED]),
    (None, [CAPTCHA_WAITING, CAPTCHA_TIMED_OUT]),
    (0, []),
])
def test_waiting_for_a_captcha_publishes_what_happens(monkeypatch, solved_after, kinds):
    monkeypatch.setattr(notices, "_SUBSCRIBERS", [])
    heard: list[Notice] = []
    notices.subscribe(heard.append)
    driver = _Driver(solved_after)
    monkeypatch.setattr(webrunner_browser, "is_captcha_page", driver.look)
    webrunner_browser.wait_for_captcha_solved(
        driver, max_wait_seconds=0.05, poll_interval=0.001
    )
    assert [n.kind for n in heard] == kinds
    assert {n.site for n in heard} <= {"scholar.google.com"}


def test_banner_counts_down_and_goes_away(qtbot):
    banner = NoticeBanner("en")
    qtbot.addWidget(banner)
    assert banner.isHidden()
    banner.show_notice(Notice(CAPTCHA_WAITING, site="scholar.google.com", seconds=61))
    assert not banner.isHidden()
    assert "scholar.google.com" in banner.text()
    assert "1:01" in banner.text()
    banner._count_down()  # noqa: SLF001
    assert "1:00" in banner.text()
    banner.show_notice(Notice(CAPTCHA_CLEARED))
    assert "Verified" in banner.text()
    banner.clear()
    assert banner.isHidden()


def test_banner_keeps_a_timeout_until_it_is_closed(qtbot):
    banner = NoticeBanner("en")
    qtbot.addWidget(banner)
    banner.show_notice(Notice(CAPTCHA_TIMED_OUT, site="ieee.org"))
    assert "ieee.org" in banner.text()
    assert not banner._hide.isActive()  # noqa: SLF001
    banner.findChild(QPushButton).click()
    assert banner.isHidden()


def test_banner_ignores_unknown_notices(qtbot):
    banner = NoticeBanner("en")
    qtbot.addWidget(banner)
    banner.show_notice(Notice("something_new"))
    assert banner.isHidden()


def test_a_captcha_on_a_worker_thread_reaches_the_window(installed, qtbot, monkeypatch):
    alerts = []
    monkeypatch.setattr(QApplication, "alert", lambda *args: alerts.append(args))
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    thread = threading.Thread(
        target=notices.publish,
        args=(Notice(CAPTCHA_WAITING, site="scholar.google.com", seconds=300),),
    )
    thread.start()
    thread.join()
    qtbot.waitUntil(lambda: not window.notice_banner().isHidden(), timeout=2000)
    assert len(alerts) == 1


def test_an_unexpected_error_is_shown_in_the_status_bar(installed, qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    installed.unexpected_error.emit("KeyError: x")
    assert "KeyError: x" in window.statusBar().currentMessage()


# --- start-up ------------------------------------------------------------------------


def test_a_failing_start_is_logged_and_shown(installed, qtbot, monkeypatch, tmp_path):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[2]))

    def explode(_argv=None):
        raise RuntimeError("no display api_key=SECRET123")

    monkeypatch.setattr(gui_app, "_boot", explode)
    assert gui_app.main([]) == 1
    assert "RuntimeError: no display api_key=***" in shown[0]
    assert "thesisagents.log" in shown[0]
    assert "could not start" in installed.text()


def test_a_missing_gui_extra_is_shown_where_there_is_no_console(monkeypatch, capsys):
    shown = []
    monkeypatch.setattr(cli, "show_error", lambda title, text: shown.append(text) or True)
    monkeypatch.setitem(sys.modules, "thesisagents.gui.app", None)
    assert cli.main(["gui"]) == 2
    assert "thesisagents[gui]" in shown[0]
    assert capsys.readouterr().err == ""


def test_the_dialog_is_only_for_programs_without_a_console(monkeypatch):
    # pytest's captured stderr is a stream that leads somewhere.
    assert windows_console.show_error("t", "m") is False
    monkeypatch.setattr(sys, "platform", "linux")
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stderr", None)
        assert windows_console.show_error("t", "m") is False

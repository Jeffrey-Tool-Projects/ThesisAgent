"""Font set-up of the desktop app: Qt's font-probe messages stay out of the log."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from PySide6.QtCore import QLoggingCategory

from thesisagents.gui import app as gui_app


@pytest.fixture
def _restore_filter_rules():
    yield
    QLoggingCategory.setFilterRules("")


def test_font_probe_messages_are_silenced(monkeypatch, _restore_filter_rules):
    # QT_LOGGING_RULES wins over the app's rule by design, so a developer's
    # own setting must not decide this test.
    monkeypatch.delenv("QT_LOGGING_RULES", raising=False)
    category = QLoggingCategory("qt.text.font.db")
    other = QLoggingCategory("qt.text.font")
    assert category.isInfoEnabled()

    gui_app._silence_font_probe_messages()  # noqa: SLF001

    assert not category.isInfoEnabled()
    assert category.isWarningEnabled()
    assert other.isInfoEnabled()


_PROBE = """
import sys
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication
from thesisagents.gui import app as gui_app
if sys.argv[1] == "silenced":
    gui_app._silence_font_probe_messages()
app = QApplication(["probe"])
font = app.font()
# Microsoft JhengHei cannot shape Devanagari, like the system font on a zh-tw Windows.
font.setFamilies(["Microsoft JhengHei UI", "Nirmala UI"])
QFontMetrics(font).horizontalAdvance("\u0939\u093f\u0928\u094d\u0926\u0940")
"""


def _probe(mode: str) -> str:
    env = {k: v for k, v in os.environ.items() if k not in ("QT_LOGGING_RULES", "QT_QPA_PLATFORM")}
    env["QT_FORCE_STDERR_LOGGING"] = "1"
    result = subprocess.run(  # noqa: S603 - this interpreter, constant arguments
        [sys.executable, "-c", _PROBE, mode],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=60, check=True,
    )
    return result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="probes Windows system fonts")
def test_qt_really_stays_quiet_about_a_hindi_label():
    # The rule was first written for the warning level. The category test
    # above, written for the same level, passed while Qt, which logs these
    # lines as info, kept printing them. So ask Qt itself.
    if "OpenType support missing" not in _probe("plain"):
        pytest.skip("this machine's fonts give no probe message to silence")
    assert "OpenType support missing" not in _probe("silenced")


def test_main_silences_the_probe_before_the_application_exists(monkeypatch, qtbot):
    order = []
    monkeypatch.setattr(
        gui_app, "_silence_font_probe_messages", lambda: order.append("silence")
    )
    monkeypatch.setattr(gui_app, "apply_saved_env", lambda: order.append("env"))

    class _StopError(Exception):
        pass

    # main() reuses the test's QApplication, so stop at the first step after it.
    def stop():
        order.append("icon")
        raise _StopError

    monkeypatch.setattr(gui_app, "_load_app_icon", stop)
    with pytest.raises(_StopError):
        gui_app.main([])
    assert order == ["silence", "env", "icon"]

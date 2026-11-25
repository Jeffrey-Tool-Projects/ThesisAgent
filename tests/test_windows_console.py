"""Console borrowing of the windowed executable, and the script that makes it.

Context: ``thesisagents.exe`` opened a console window behind the desktop app.
It is now a windowed program with a console twin, made by
``scripts/split_windows_exe.py``, and ``utils/windows_console.py`` keeps its
command-line output visible in the terminal it was typed into.
"""
from __future__ import annotations

import importlib.util
import io
import struct
import sys
from pathlib import Path

import pytest

from thesisagents import cli
from thesisagents.utils import windows_console

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "split_windows_exe", _ROOT / "scripts" / "split_windows_exe.py"
)
split_windows_exe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(split_windows_exe)

_PE_OFFSET = 0x80
_SUBSYSTEM_AT = _PE_OFFSET + 24 + 68


def _pe(subsystem: int = 3, magic: int = 0x20B) -> bytes:
    """A file with just the PE header fields the script reads."""
    data = bytearray(b"\xAA" * 512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, _PE_OFFSET)
    data[_PE_OFFSET:_PE_OFFSET + 4] = b"PE\0\0"
    struct.pack_into("<H", data, _PE_OFFSET + 24, magic)
    struct.pack_into("<H", data, _SUBSYSTEM_AT, subsystem)
    return bytes(data)


@pytest.mark.parametrize("magic", [0x10B, 0x20B])
def test_split_changes_only_the_subsystem_and_keeps_the_console_build(tmp_path, magic):
    exe = tmp_path / "thesisagents.exe"
    original = _pe(magic=magic)
    exe.write_bytes(original)

    assert split_windows_exe.main([str(exe)]) == 0

    twin = tmp_path / "thesisagents-cli.exe"
    assert twin.read_bytes() == original
    assert split_windows_exe.read_subsystem(twin) == split_windows_exe.SUBSYSTEM_WINDOWS_CONSOLE
    assert split_windows_exe.read_subsystem(exe) == split_windows_exe.SUBSYSTEM_WINDOWS_GUI
    windowed = exe.read_bytes()
    changed = [i for i, (a, b) in enumerate(zip(original, windowed, strict=True)) if a != b]
    assert changed == [_SUBSYSTEM_AT]


def test_split_refuses_to_run_twice(tmp_path, capsys):
    # A second run would replace the console twin with a windowed copy.
    exe = tmp_path / "thesisagents.exe"
    exe.write_bytes(_pe())
    assert split_windows_exe.main([str(exe)]) == 0
    twin = tmp_path / "thesisagents-cli.exe"
    before = twin.read_bytes()

    assert split_windows_exe.main([str(exe)]) == 1
    assert "not a console program" in capsys.readouterr().err
    assert twin.read_bytes() == before


@pytest.mark.parametrize("data", [
    b"",
    b"MZ",
    b"PK" + _pe()[2:],
    _pe().replace(b"PE\0\0", b"XX\0\0"),
    _pe(magic=0x107),
    # The PE pointer leads past the end of the file.
    _pe()[:0x3C] + struct.pack("<I", 0xFFFFFF00) + _pe()[0x40:],
])
def test_split_rejects_what_is_not_an_executable(tmp_path, capsys, data):
    exe = tmp_path / "thesisagents.exe"
    exe.write_bytes(data)
    assert split_windows_exe.main([str(exe)]) == 1
    assert capsys.readouterr().err.startswith("error: ")
    assert exe.read_bytes() == data
    assert not (tmp_path / "thesisagents-cli.exe").exists()


def test_split_reports_a_missing_file(tmp_path, capsys):
    assert split_windows_exe.main([str(tmp_path / "absent.exe")]) == 1
    assert "error: " in capsys.readouterr().err


@pytest.mark.skipif(sys.platform != "win32", reason="needs a Windows interpreter")
def test_read_subsystem_tells_python_from_pythonw():
    base = Path(sys.base_prefix)
    assert split_windows_exe.read_subsystem(base / "python.exe") == 3
    assert split_windows_exe.read_subsystem(base / "pythonw.exe") == 2


class _NulStream(io.StringIO):
    """What Nuitka gives a program that has no console."""

    name = "NUL:"


@pytest.fixture
def console(monkeypatch, tmp_path):
    """Stand-in for CONOUT$: a file, plus a record of the attach calls."""
    attached = []
    target = tmp_path / "conout.txt"
    real_open = open

    def fake_open(name, *args, **kwargs):
        assert name == "CONOUT$"
        return real_open(target, "a", encoding=kwargs["encoding"], buffering=1)

    monkeypatch.setattr(windows_console, "open", fake_open, raising=False)
    monkeypatch.setattr(
        windows_console, "_attach_to_parent", lambda: attached.append(True) or True
    )
    return attached, target


@pytest.mark.parametrize("missing", [None, _NulStream()], ids=["pythonw", "nuitka"])
def test_missing_streams_are_pointed_at_the_parent_console(monkeypatch, console, missing):
    attached, target = console
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", missing)
        patch.setattr(sys, "stderr", missing)
        assert windows_console.borrow_parent_console() is True
        print("論文")
        print("error", file=sys.stderr)
        sys.stdout.close()
        sys.stderr.close()
    assert attached == [True]
    assert target.read_text(encoding="utf-8") == "論文\nerror\n"


def test_a_redirected_stream_is_left_alone(monkeypatch, console):
    redirected = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", redirected)
        patch.setattr(sys, "stderr", None)
        assert windows_console.borrow_parent_console() is True
        assert sys.stdout is redirected
        sys.stderr.close()


def test_a_console_program_never_attaches(monkeypatch, console):
    attached, _target = console
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        assert windows_console.borrow_parent_console() is False
        assert (sys.stdout, sys.stderr) == (out, err)
    assert attached == []


def test_without_a_parent_console_the_streams_stay(monkeypatch):
    monkeypatch.setattr(windows_console, "_attach_to_parent", lambda: False)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", None)
        patch.setattr(sys, "stderr", None)
        assert windows_console.borrow_parent_console() is False
        assert sys.stdout is None


def test_attach_is_windows_only(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert windows_console._attach_to_parent() is False  # noqa: SLF001


def test_cli_borrows_the_console_for_commands_and_not_for_the_gui(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "borrow_parent_console", lambda: calls.append(True))
    monkeypatch.setattr(cli, "_dispatch_gui", lambda _argv: 0)
    assert cli.main([]) == 0
    assert cli.main(["gui"]) == 0
    assert calls == []
    assert cli.main(["--list-sources"]) == 0
    assert calls == [True]
    assert "arxiv" in capsys.readouterr().out

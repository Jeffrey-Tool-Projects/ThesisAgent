"""Console output for the windowed Windows executable.

The release ships ``thesisagents.exe`` as a windowed program, so that opening
the desktop app never shows a console (``scripts/split_windows_exe.py``). Such
a program starts with no standard streams even when it is typed into a
terminal, so ``thesisagents.exe --help`` would print nothing at all. The CLI
therefore borrows the terminal it was started from. ``thesisagents-cli.exe``
is the program to use from a terminal: a shell does not wait for a windowed
one, so its exit code and captured output are lost.
"""

from __future__ import annotations

import sys
from typing import TextIO

#: ``AttachConsole`` argument meaning "the console of the parent process".
_ATTACH_PARENT_PROCESS = -1
#: Nuitka gives a program without streams ones opened on this name, while
#: CPython's ``pythonw`` sets them to None. A ``> NUL`` redirect keeps the
#: name ``<stdout>``, so it is not mistaken for a missing stream.
_NUITKA_NULL_STREAM = "NUL:"


def _is_missing(stream: TextIO | None) -> bool:
    """True when ``stream`` leads nowhere because the process has no console."""
    return stream is None or getattr(stream, "name", None) == _NUITKA_NULL_STREAM


def _attach_to_parent() -> bool:
    """Join the parent's console. False when there is none (opened by a click)."""
    if sys.platform != "win32":
        return False
    import ctypes

    return bool(ctypes.windll.kernel32.AttachConsole(_ATTACH_PARENT_PROCESS))


def borrow_parent_console() -> bool:
    """Point missing stdout / stderr at the terminal this program was run from.

    Streams that exist are left alone, so redirects and pipes keep working and
    a console program (``thesisagents-cli.exe``, ``python -m thesisagents``)
    is unaffected. Returns True when a stream was replaced. Example:
    ``thesisagents.exe --list-sources`` typed into PowerShell prints the list
    there, and the same command from a shortcut prints nowhere, as before.
    """
    missing = [name for name in ("stdout", "stderr") if _is_missing(getattr(sys, name))]
    if not missing or not _attach_to_parent():
        return False
    for name in missing:
        # Stays open for the life of the process, as the stream it replaces.
        console = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)  # noqa: SIM115
        setattr(sys, name, console)
    return True

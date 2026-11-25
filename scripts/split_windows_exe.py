"""Split a console ``.exe`` into a windowed program and its console twin.

Why: one ``thesisagents.exe`` served both the desktop app and the CLI. Built
as a console program it opened a black console window behind the app, and
Nuitka's ``--windows-console-mode`` cannot serve both. ``disable`` silences
the CLI. ``attach`` (tried 2026-11-25, Nuitka 4.3.5) loses the exit code and
the captured output in PowerShell, and without a console it leaves an invalid
standard input handle that makes ``subprocess.run(capture_output=True)``
raise OSError, which is how Selenium Manager is run, so Chrome could not
start.

Windows reads one 16-bit field of the PE header, the subsystem, to decide
whether a program gets a console. ``python.exe`` and ``pythonw.exe`` differ in
the same way. Copying the file and changing that field costs no second
compile (about an hour, since the mode is a compiler define and misses every
cached object). Run by the release workflow after the Nuitka build:

    python scripts/split_windows_exe.py thesisagents.dist/thesisagents.exe

leaves ``thesisagents.exe`` windowed and adds ``thesisagents-cli.exe``.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import sys
from pathlib import Path

SUBSYSTEM_WINDOWS_GUI = 2
SUBSYSTEM_WINDOWS_CONSOLE = 3

_PE_POINTER_OFFSET = 0x3C
_PE_SIGNATURE = b"PE\0\0"
#: Signature (4 bytes) and COFF header (20 bytes) precede the optional header,
#: whose subsystem field is at offset 68 in both its 32 and 64-bit layouts.
_OPTIONAL_HEADER_OFFSET = 24
_SUBSYSTEM_OFFSET = 68
_OPTIONAL_HEADER_MAGICS = (0x10B, 0x20B)


def _subsystem_field(data: bytes | bytearray) -> int:
    """Offset of the subsystem field. ValueError when ``data`` is not a PE file."""
    try:
        (pe_offset,) = struct.unpack_from("<I", data, _PE_POINTER_OFFSET)
        optional_header = pe_offset + _OPTIONAL_HEADER_OFFSET
        (magic,) = struct.unpack_from("<H", data, optional_header)
        struct.unpack_from("<H", data, optional_header + _SUBSYSTEM_OFFSET)
    except struct.error as err:
        raise ValueError("not a Windows executable (too short)") from err
    if data[:2] != b"MZ" or data[pe_offset:pe_offset + 4] != _PE_SIGNATURE:
        raise ValueError("not a Windows executable (no MZ / PE signature)")
    if magic not in _OPTIONAL_HEADER_MAGICS:
        raise ValueError(f"unknown PE optional header magic {magic:#x}")
    return optional_header + _SUBSYSTEM_OFFSET


def read_subsystem(path: Path) -> int:
    """The PE subsystem of ``path``: 2 is windowed, 3 is console."""
    data = path.read_bytes()
    return struct.unpack_from("<H", data, _subsystem_field(data))[0]


def split(exe: Path) -> Path:
    """Make ``exe`` windowed, keep the console build beside it, return that path.

    Refuses an ``exe`` that is not a console program: running twice would
    otherwise overwrite the console twin with a windowed copy.
    """
    data = bytearray(exe.read_bytes())
    field = _subsystem_field(data)
    (subsystem,) = struct.unpack_from("<H", data, field)
    if subsystem != SUBSYSTEM_WINDOWS_CONSOLE:
        raise ValueError(f"{exe.name} is not a console program (subsystem {subsystem})")
    console_twin = exe.with_name(f"{exe.stem}-cli{exe.suffix}")
    shutil.copy2(exe, console_twin)
    struct.pack_into("<H", data, field, SUBSYSTEM_WINDOWS_GUI)
    exe.write_bytes(data)
    return console_twin


def main(argv: list[str] | None = None) -> int:
    """Command-line entry: split one executable, report both files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("exe", type=Path, help="console executable to split")
    args = parser.parse_args(argv)
    try:
        console_twin = split(args.exe)
    except (OSError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    for path in (args.exe, console_twin):
        print(f"{path}: subsystem {read_subsystem(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

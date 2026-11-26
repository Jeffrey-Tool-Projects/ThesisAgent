"""Summaries written by an AI program on the command line, such as ``claude -p``.

A user who is signed in to Claude Code, the Gemini CLI or Codex can summarise
with that subscription and needs no API key. The program is run once per
paper: the instructions and the paper go in on standard input, the answer
comes back on standard output.

What this module guards:

* **The command line.** It is split into arguments and run without a shell,
  so nothing in it or in a paper is ever read as shell syntax. The paper
  travels on standard input only, never as an argument.
* **The user's files.** Agent programs can read and write files. Each run
  happens in a new empty folder that is removed afterwards, so the program
  sees no project and writes nowhere that matters.
* **The window.** On Windows the program gets no console of its own, which
  would flash up over the app for every paper.

Example::

    run_command("claude -p --output-format text", "Summarise ...", timeout=600)
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess  # nosec B404 - runs the program the user chose, without a shell
import tempfile
from collections.abc import Sequence
from typing import Final

from thesisagents.core.exceptions import ConfigError, ParseError, SourceUnavailableError

#: How long one paper may take, in seconds. Agent programs think for a while.
TIMEOUT_ENV: Final[str] = "THESISAGENTS_LLM_CLI_TIMEOUT"
DEFAULT_TIMEOUT: Final[float] = 600.0
_SOURCE: Final[str] = "llm"
#: Colour and cursor codes some programs print even into a pipe.
_ANSI: Final[re.Pattern[str]] = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_STDERR_SHOWN: Final[int] = 400


def split_command(command: str) -> list[str]:
    """``command`` as the list of arguments it names.

    Quotes group an argument with spaces. On Windows a backslash is a path
    separator, not an escape.

    >>> split_command('ollama run "qwen3:8b"')
    ['ollama', 'run', 'qwen3:8b']
    """
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError as err:
        raise ConfigError(f"the command {command!r} cannot be read: {err}") from err
    # Windows keeps the quotes in non-POSIX mode.
    parts = [part[1:-1] if len(part) > 1 and part[0] == part[-1] == '"' else part for part in parts]
    if not parts:
        raise ConfigError("no command is set for the command-line model")
    return parts


def find_program(command: str) -> str | None:
    """The full path of the program ``command`` starts, ``None`` when there is none.

    ``shutil.which`` also finds ``claude.cmd``, the form npm installs on
    Windows, which a plain ``claude`` would not start.
    """
    return shutil.which(split_command(command)[0])


def run_command(
    command: str | Sequence[str], prompt: str, *, timeout: float | None = None,
    label: str = "",
) -> str:
    """Run ``command`` with ``prompt`` on standard input and return what it printed.

    ``command`` is a command line or its arguments. Raises ``ConfigError``
    when the program is not installed, ``SourceUnavailableError`` when it
    fails or takes too long, and ``ParseError`` when it prints nothing.
    """
    arguments = split_command(command) if isinstance(command, str) else list(command)
    if not arguments:
        raise ConfigError("no command is set for the command-line model")
    program = shutil.which(arguments[0])
    name = label or arguments[0]
    if program is None:
        raise ConfigError(
            f"{arguments[0]} is not installed or not on PATH. Install it and sign in "
            "first, or choose another model"
        )
    seconds = timeout if timeout is not None else _timeout()
    with tempfile.TemporaryDirectory(prefix="thesisagents-llm-") as workdir:
        try:
            done = subprocess.run(  # noqa: S603  # nosec B603 - no shell, the user's own program
                [program, *arguments[1:]],
                input=prompt.encode("utf-8"),
                capture_output=True,
                cwd=workdir,
                timeout=seconds,
                check=False,
                creationflags=_NO_WINDOW,
                env=_environment(),
            )
        except subprocess.TimeoutExpired as err:
            raise SourceUnavailableError(
                _SOURCE, f"{name} did not finish within {seconds:g} s. Raise {TIMEOUT_ENV}"
            ) from err
        except OSError as err:
            raise SourceUnavailableError(_SOURCE, f"{name} could not be started: {err}") from err
    output = _clean(done.stdout)
    if done.returncode != 0:
        detail = _clean(done.stderr)[-_STDERR_SHOWN:] or output[-_STDERR_SHOWN:]
        raise SourceUnavailableError(
            _SOURCE,
            f"{name} ended with code {done.returncode}: {detail or 'no message'}. "
            "Is it signed in?",
        )
    if not output.strip():
        raise ParseError("intelligence", f"{name} printed nothing")
    return output


def list_ollama_models(command: str) -> list[str]:
    """The models of the local Ollama, from ``ollama list``.

    Example: ``["qwen3:8b", "llama3.2:latest"]``.
    """
    program = find_program(command) or shutil.which("ollama")
    if program is None:
        raise ConfigError("ollama is not installed or not on PATH")
    try:
        done = subprocess.run(  # noqa: S603  # nosec B603 - no shell, a fixed argument
            [program, "list"], capture_output=True, timeout=30, check=False,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        raise SourceUnavailableError(_SOURCE, f"ollama list failed: {err}") from err
    lines = _clean(done.stdout).splitlines()[1:]  # the first line is the header
    return [line.split()[0] for line in lines if line.strip()]


def with_model(command: Sequence[str], flag: str, model: str) -> list[str]:
    """``command`` with the model added, by its flag or as the last argument.

    A last ``-`` (read the prompt from standard input) stays last.

    >>> with_model(["claude", "-p"], "--model", "opus")
    ['claude', '-p', '--model', 'opus']
    >>> with_model(["ollama", "run"], "", "qwen3")
    ['ollama', 'run', 'qwen3']
    >>> with_model(["codex", "exec", "-"], "--model", "o4")
    ['codex', 'exec', '--model', 'o4', '-']
    """
    if not model:
        return list(command)
    head, tail = (list(command[:-1]), ["-"]) if command and command[-1] == "-" else (
        list(command), [],
    )
    return [*head, *([flag, model] if flag else [model]), *tail]


def _timeout() -> float:
    stated = os.environ.get(TIMEOUT_ENV, "").strip()
    try:
        value = float(stated)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def _environment() -> dict[str, str]:
    """This process's environment, asking for plain output in UTF-8.

    ``NO_COLOR`` is the common way to turn colour codes off, and the CLIs of
    the agent programs honour it. ``PYTHONUTF8`` makes a program written in
    Python read the paper as UTF-8: on a Chinese Windows it would read it in
    the code page and garble every accent.
    """
    return {**os.environ, "NO_COLOR": "1", "PYTHONUTF8": "1"}


def _clean(raw: bytes) -> str:
    return _ANSI.sub("", raw.decode("utf-8", errors="replace")).replace("\r\n", "\n")


#: ``CREATE_NO_WINDOW`` on Windows, nothing elsewhere.
_NO_WINDOW: Final[int] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

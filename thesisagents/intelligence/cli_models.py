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
  starts in a new empty folder that is removed afterwards, so a program that
  looks around finds nothing, and the presets turn tools off (Claude Code)
  or allow reading only (Codex). A program allowed to read can still open
  other files by their full path.
* **The window.** On Windows the program gets no console of its own, which
  would flash up over the app for every paper.
* **The keys.** The API keys this app holds are taken out of the program's
  environment, so a program signed in to an account uses that account and
  not a key it happens to find (Claude Code bills a set
  ``ANTHROPIC_API_KEY`` instead of the subscription), and no program reads
  the keys of other services.
* **The time.** On a timeout the whole process tree is ended. An npm shim
  (``gemini.cmd``) starts the real program as a child that kept the pipes
  open, so the timeout waited for it.

Example::

    run_command("claude -p --output-format text", "Summarise ...", timeout=600)
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess  # nosec B404 - runs the program the user chose, without a shell
import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

from thesisagents.core.exceptions import ConfigError, ParseError, SourceUnavailableError

#: How long one paper may take, in seconds. Agent programs think for a while.
TIMEOUT_ENV: Final[str] = "THESISAGENTS_LLM_CLI_TIMEOUT"
DEFAULT_TIMEOUT: Final[float] = 600.0
_SOURCE: Final[str] = "llm"
#: Colour and cursor codes some programs print even into a pipe.
_ANSI: Final[re.Pattern[str]] = re.compile(
    r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
)
_STDERR_SHOWN: Final[int] = 400
_LOGIN_REQUIRED: Final[re.Pattern[str]] = re.compile(
    r"\b(?:not (?:logged|signed) in|(?:please|must) (?:log|sign) in|"
    r"please run /login|(?:authentication|login|sign[- ]in) (?:is )?required|"
    r"unauthenticated|not authenticated|(?:sign|log) in again|please set an auth method|"
    r"(?:access|refresh) token (?:has )?expired)\b",
    re.IGNORECASE,
)


def split_command(command: str) -> list[str]:
    """``command`` as the list of arguments it names.

    Single or double quotes group an argument with spaces, also inside one
    (``--flag="a b"``). On Windows a backslash is a path separator, not an
    escape, so a Windows path stays as written.

    >>> split_command('ollama run "qwen3:8b"')
    ['ollama', 'run', 'qwen3:8b']
    >>> split_command("ai --flag='a b'")
    ['ai', '--flag=a b']
    """
    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    if os.name == "nt":
        lexer.escape = ""
    try:
        parts = list(lexer)
    except ValueError as err:
        raise ConfigError(f"the command {command!r} cannot be read: {err}") from err
    if not parts:
        raise ConfigError("no command is set for the command-line model")
    return parts


def find_program(command: str) -> str | None:
    """The full path of the program ``command`` starts, ``None`` when there is none.

    ``shutil.which`` also finds ``claude.cmd``, the form npm installs on
    Windows, which a plain ``claude`` would not start.
    """
    found = shutil.which(split_command(command)[0])
    # Absolute: the program runs in another folder, where a relative path
    # such as ./summarise.sh names nothing.
    return os.path.abspath(found) if found else None


def run_command(
    command: str | Sequence[str], prompt: str, *, timeout: float | None = None,
    label: str = "", hidden: Iterable[str] = (), login_hint: str = "",
) -> str:
    """Run ``command`` with ``prompt`` on standard input and return what it printed.

    ``command`` is a command line or its arguments, ``hidden`` the names of
    environment variables the program must not get. Raises ``ConfigError``
    when the program is not installed, ``SourceUnavailableError`` when it
    fails or takes too long, and ``ParseError`` when it prints nothing.
    """
    arguments = split_command(command) if isinstance(command, str) else list(command)
    code, output, diagnostic = _invoke(arguments, prompt, timeout, label, hidden)
    name = label or arguments[0]
    if code != 0:
        if login_hint and _LOGIN_REQUIRED.search(diagnostic + "\n" + output):
            raise ConfigError(login_hint)
        detail = diagnostic[-_STDERR_SHOWN:] or output[-_STDERR_SHOWN:]
        raise SourceUnavailableError(
            _SOURCE, f"{name} ended with code {code}: {detail or 'no message'}",
        )
    if not output.strip():
        raise ParseError("intelligence", f"{name} printed nothing")
    return output


def _invoke(
    arguments: Sequence[str], prompt: str, timeout: float | None, label: str,
    hidden: Iterable[str],
) -> tuple[int, str, str]:
    if not arguments:
        raise ConfigError("no command is set for the command-line model")
    found = shutil.which(arguments[0])
    program = os.path.abspath(found) if found else None
    name = label or arguments[0]
    if program is None:
        raise ConfigError(
            f"{arguments[0]} is not installed or not on PATH. Install it and sign in "
            "first, or choose another model"
        )
    seconds = timeout if timeout is not None else _timeout()
    # A program still running after the kill holds the folder, which is left
    # to the system's temp cleanup rather than turned into a second error.
    with tempfile.TemporaryDirectory(
        prefix="thesisagents-llm-", ignore_cleanup_errors=True
    ) as workdir:
        try:
            process = subprocess.Popen(  # noqa: S603  # nosec B603 - no shell, the user's own program
                [program, *arguments[1:]],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=workdir,
                creationflags=_NO_WINDOW | _NEW_GROUP,
                start_new_session=os.name != "nt",
                env=_environment(hidden),
            )
        except OSError as err:
            raise SourceUnavailableError(_SOURCE, f"{name} could not be started: {err}") from err
        try:
            stdout, stderr = process.communicate(prompt.encode("utf-8"), timeout=seconds)
        except subprocess.TimeoutExpired as err:
            _end_tree(process)
            hint = f". Raise {TIMEOUT_ENV}" if timeout is None else ""
            raise SourceUnavailableError(
                _SOURCE, f"{name} did not finish within {seconds:g} s{hint}"
            ) from err
    return process.returncode, _clean(stdout), _clean(stderr)


def login_required(program: str, provider: str, hidden: Iterable[str]) -> bool:
    """Check the noninteractive account status for a supported preset."""
    if provider == "claude-cli":
        _, output, _ = _invoke([program, "auth", "status", "--json"], "", 10, program, hidden)
        try:
            status = json.loads(output)
        except (ValueError, RecursionError):
            # Older releases without this subcommand report errors on the actual run.
            return False
        return isinstance(status, dict) and status.get("loggedIn") is False
    if provider == "codex-cli":
        code, output, error = _invoke([program, "login", "status"], "", 10, program, hidden)
        return code != 0 and bool(_LOGIN_REQUIRED.search(error + "\n" + output))
    return False


def run_agy(
    command: Sequence[str], prompt: str, *, label: str, hidden: Iterable[str], login_hint: str = "",
) -> str:
    """Send one user event on stdin and return the final response from the event stream."""
    event = {"event": "user", "message": {"content": prompt}}
    output = run_command(
        command, json.dumps(event) + "\n", label=label, hidden=hidden, login_hint=login_hint,
    )
    try:
        last = json.loads(output.rstrip().rsplit("\n", 1)[-1])
    except (ValueError, RecursionError) as err:
        raise ParseError("intelligence", f"{label} returned an invalid result event") from err
    if not isinstance(last, dict) or last.get("event") != "result":
        raise ParseError("intelligence", f"{label} returned no final result event")
    result = last.get("result")
    if not isinstance(result, dict):
        raise ParseError("intelligence", f"{label} returned a malformed result")
    if result.get("status") != "SUCCESS":
        detail = str(result.get("error") or result.get("status") or "unknown status")
        if login_hint and _LOGIN_REQUIRED.search(detail):
            raise ConfigError(login_hint)
        raise SourceUnavailableError(_SOURCE, f"{label}: {detail[:_STDERR_SHOWN]}")
    response = result.get("response")
    if not isinstance(response, str) or not response.strip():
        raise ParseError("intelligence", f"{label} returned an empty response")
    return response


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
    if not model or (flag and flag in command):
        # A command that names its model already keeps it.
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


def _end_tree(process: subprocess.Popen[bytes]) -> None:
    """End ``process`` and every process it started, then collect it.

    Ending the shim alone leaves the real program running with the pipes,
    and ``communicate`` would wait for it after all.
    """
    if os.name == "nt":
        taskkill = Path(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "taskkill.exe")
        subprocess.run(  # noqa: S603  # nosec B603 - the system's own tool, fixed arguments
            [str(taskkill), "/T", "/F", "/PID", str(process.pid)],
            capture_output=True, check=False, creationflags=_NO_WINDOW,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
    process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=5)


def _environment(hidden: Iterable[str] = ()) -> dict[str, str]:
    """This process's environment without ``hidden``, asking for plain output in UTF-8.

    ``NO_COLOR`` is the common way to turn colour codes off, and the CLIs of
    the agent programs honour it. ``PYTHONUTF8`` makes a program written in
    Python read the paper as UTF-8: on a Chinese Windows it would read it in
    the code page and garble every accent.
    """
    leave_out = set(hidden)
    kept = {name: value for name, value in os.environ.items() if name not in leave_out}
    return {**kept, "NO_COLOR": "1", "PYTHONUTF8": "1"}


def _clean(raw: bytes) -> str:
    return _ANSI.sub("", raw.decode("utf-8", errors="replace")).replace("\r\n", "\n")


#: ``CREATE_NO_WINDOW`` on Windows, nothing elsewhere.
_NO_WINDOW: Final[int] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
#: Its own process group on Windows, so the whole tree can be ended.
_NEW_GROUP: Final[int] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

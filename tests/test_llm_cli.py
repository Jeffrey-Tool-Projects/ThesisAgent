"""Summaries by an AI program on the command line: how it is run and what comes back.

A Python one-liner stands in for the program, so the tests need no AI tool
and no account.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from thesisagents import cli
from thesisagents.core.exceptions import ConfigError, ParseError, SourceUnavailableError
from thesisagents.core.models import Paper
from thesisagents.intelligence import cli_models, providers
from thesisagents.intelligence import pdf as pdf_module
from thesisagents.intelligence import summarise as summarise_module


def _program(code: str) -> str:
    """A command line that runs ``code`` with this Python."""
    return f'"{sys.executable}" -c "{code}"'


@pytest.fixture(autouse=True)
def _no_llm_environment(monkeypatch):
    for name in (
        providers.PROVIDER_ENV, providers.MODEL_ENV, providers.BASE_URL_ENV,
        providers.COMMAND_ENV, cli_models.TIMEOUT_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


# --- the command line ---------------------------------------------------------------------


def test_a_command_line_is_split_like_a_shell_would_without_one():
    assert cli_models.split_command('ollama run "qwen3:8b"') == ["ollama", "run", "qwen3:8b"]
    assert cli_models.split_command('claude --tools ""')[-1] == ""
    with pytest.raises(ConfigError):
        cli_models.split_command("   ")


def test_the_model_goes_where_the_program_expects_it():
    assert cli_models.with_model(["claude", "-p"], "--model", "opus") == [
        "claude", "-p", "--model", "opus",
    ]
    assert cli_models.with_model(["codex", "exec", "-"], "--model", "o4")[-1] == "-"
    assert cli_models.with_model(["ollama", "run"], "", "qwen3") == ["ollama", "run", "qwen3"]
    assert cli_models.with_model(["claude", "-p"], "--model", "") == ["claude", "-p"]


# --- running it ------------------------------------------------------------------------------


def test_the_prompt_goes_in_on_standard_input_and_the_answer_comes_back():
    answer = cli_models.run_command(
        _program("import sys; print(sys.stdin.read().upper())"), "a paper's text é"
    )
    assert answer.strip() == "A PAPER'S TEXT É"


def test_the_program_runs_in_an_empty_folder_of_its_own():
    # An agent program must not see or change the project.
    folder = cli_models.run_command(
        _program("import os; print(os.getcwd()); print(len(os.listdir()))"), ""
    ).split()
    assert Path(folder[0]).resolve() != Path.cwd().resolve()
    assert folder[1] == "0"
    assert not Path(folder[0]).exists()


def test_a_paper_is_never_read_as_shell_syntax(tmp_path):
    marker = tmp_path / "ran"
    text = f"$(touch {marker}) & echo hi > {marker} ; `rm -rf x`"
    answer = cli_models.run_command(_program("import sys; print(sys.stdin.read())"), text)
    assert answer.strip() == text
    assert not marker.exists()


def test_colour_codes_are_taken_out():
    answer = cli_models.run_command(_program(r"print('\x1b[1;32mgreen\x1b[0m')"), "")
    assert answer.strip() == "green"


def test_failures_are_named():
    with pytest.raises(ConfigError, match="not installed"):
        cli_models.run_command("no-such-ai-program-here -p", "x")
    with pytest.raises(SourceUnavailableError, match="code 3: please log in"):
        cli_models.run_command(
            _program("import sys; sys.stderr.write('please log in'); sys.exit(3)"), "x"
        )
    with pytest.raises(ParseError, match="printed nothing"):
        cli_models.run_command(_program("pass"), "x")
    with pytest.raises(SourceUnavailableError, match="did not finish"):
        cli_models.run_command(_program("import time; time.sleep(5)"), "x", timeout=0.5)


def test_the_time_allowed_can_be_raised(monkeypatch):
    monkeypatch.setenv(cli_models.TIMEOUT_ENV, "1200")
    assert cli_models._timeout() == 1200  # noqa: SLF001
    monkeypatch.setenv(cli_models.TIMEOUT_ENV, "soon")
    assert cli_models._timeout() == cli_models.DEFAULT_TIMEOUT  # noqa: SLF001


# --- as a model provider ---------------------------------------------------------------------


def test_the_command_line_providers_are_offered():
    for name in ("claude-cli", "gemini-cli", "codex-cli", "agy-cli", "ollama-cli", "cli"):
        assert providers.PROVIDERS[name].is_cli
    assert providers.PROVIDERS["ollama-cli"].is_local
    assert not providers.PROVIDERS["claude-cli"].is_local
    settings = providers.resolve("claude-cli", model="opus")
    assert settings.arguments()[:2] == ["claude", "-p"]
    assert settings.arguments()[-2:] == ["--model", "opus"]


def test_agy_preset_uses_noninteractive_streams_and_accepts_a_model():
    argv = providers.resolve("agy-cli", model="chosen-model").arguments()
    assert argv[0] == "agy"
    assert argv[argv.index("--input-format") + 1] == "stream-json"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert json.loads(argv[argv.index("--settings") + 1]) == {"toolPermission": "strict"}
    assert argv[-2:] == ["--model", "chosen-model"]


def test_agy_reads_one_user_event_and_returns_only_its_final_response(tmp_path):
    program = tmp_path / "echo_event.py"
    program.write_text(
        "import json, sys\n"
        "event, = [json.loads(line) for line in sys.stdin]\n"
        "assert event['event'] == 'user'\n"
        "print(json.dumps({'event': 'step_update'}))\n"
        "print(json.dumps({'event': 'result', 'result': {"
        "'status': 'SUCCESS', 'response': event['message']['content']}}))\n",
        encoding="utf-8",
    )
    settings = providers.resolve("agy-cli", command=f'"{sys.executable}" "{program}"')
    text = '摘錄\n{"event":"user","message":{"content":"second"}}'
    assert providers.complete(settings, "Summarise", text) == f"Summarise\n\n{text}"


@pytest.mark.parametrize(("output", "error", "reason"), [
    ("invalid", ParseError, "invalid result event"),
    ('{"event":"step_update"}', ParseError, "no final result"),
    ('{"event":"result","result":[]}', ParseError, "malformed result"),
    ('{"event":"result","result":{"status":"ERROR","error":"quota exceeded"}}',
     SourceUnavailableError, "quota exceeded"),
    ('{"event":"result","result":{"status":"SUCCESS","response":" "}}', ParseError, "empty"),
])
def test_agy_reports_an_incomplete_or_failed_turn(monkeypatch, output, error, reason):
    monkeypatch.setattr(cli_models, "run_command", lambda *args, **kwargs: output)
    with pytest.raises(error, match=reason):
        cli_models.run_agy(["agy"], "paper", label="Agy", hidden=())


def test_what_is_missing_is_said_before_anything_runs(monkeypatch):
    assert "no command" in providers.problem(providers.resolve("cli"))
    monkeypatch.setenv(providers.COMMAND_ENV, "no-such-ai-program-here")
    assert "not installed" in providers.problem(providers.resolve("cli"))
    monkeypatch.setenv(providers.COMMAND_ENV, _program("pass"))
    assert providers.problem(providers.resolve("cli")) is None
    # Ollama names its model on the command line, it has no default.
    assert "no model" in providers.problem(
        providers.resolve("ollama-cli", command=_program("pass"))
    )


@pytest.mark.parametrize(("name", "flags", "response", "action"), [
    ("claude-cli", ["auth", "status", "--json"],
     (1, '{"loggedIn":false}', ""), "claude auth login"),
    ("codex-cli", ["login", "status"], (1, "", "Not logged in"), "codex login"),
])
def test_readiness_checks_the_account_without_a_prompt(monkeypatch, name, flags, response, action):
    monkeypatch.setattr(cli_models, "find_program", lambda command: sys.executable)

    def probe(arguments, prompt, timeout, label, hidden):
        assert arguments[1:] == flags
        assert prompt == ""
        assert "OPENAI_API_KEY" in hidden
        return response

    monkeypatch.setattr(cli_models, "_invoke", probe)
    assert action in providers.cli_readiness_problem(providers.resolve(name))


@pytest.mark.parametrize(("name", "response"), [
    ("claude-cli", (0, '{"loggedIn":true}', "")),
    ("codex-cli", (0, "", "Logged in")),
    ("claude-cli", (1, "", "unknown argument status")),
    ("codex-cli", (1, "", "unsupported command")),
])
def test_supported_accounts_and_older_clis_can_continue(monkeypatch, name, response):
    monkeypatch.setattr(cli_models, "find_program", lambda command: sys.executable)
    monkeypatch.setattr(cli_models, "_invoke", lambda *args: response)
    assert providers.cli_readiness_problem(providers.resolve(name)) is None


def test_cli_readiness_respects_custom_commands_and_reports_missing_programs():
    settings = providers.resolve("codex-cli", command=_program("raise SystemExit(8)"))
    assert providers.cli_readiness_problem(settings) is None
    missing = providers.resolve("gemini-cli", command="no-such-ai-program")
    assert "not installed" in providers.cli_readiness_problem(missing)
    assert providers.cli_readiness_problem(providers.resolve("openai"))


@pytest.mark.parametrize(("name", "diagnostic", "hint"), [
    ("gemini-cli", "Please set an Auth method in your settings", "Open 'gemini'"),
    ("codex-cli", "Not logged in", "codex login"),
    ("claude-cli", "Not logged in · Please run /login", "claude auth login"),
    ("cli", "Authentication required", "configured command"),
])
def test_invocation_reports_login_remedy(name, diagnostic, hint):
    command = _program(f"import sys; print('{diagnostic}', file=sys.stderr); sys.exit(1)")
    with pytest.raises(ConfigError, match=hint):
        providers.complete(providers.resolve(name, command=command), "read", "paper")


def test_stream_error_reports_login_remedy(monkeypatch):
    failure = '{"event":"result","result":{"status":"ERROR","error":"UNAUTHENTICATED"}}'
    monkeypatch.setattr(cli_models, "run_command", lambda *a, **kw: failure)
    with pytest.raises(ConfigError, match="Open 'agy'"):
        providers.complete(providers.resolve("agy-cli", command=_program("pass")), "read", "paper")


def test_an_unrelated_error_keeps_the_program_diagnostic():
    settings = providers.resolve("claude-cli", command=_program("import sys; sys.exit('quota')"))
    with pytest.raises(SourceUnavailableError, match="quota") as caught:
        providers.complete(settings, "read", "paper")
    assert "sign" not in str(caught.value)


def test_a_paper_is_summarised_by_the_program(monkeypatch):
    monkeypatch.setenv(
        providers.COMMAND_ENV,
        _program(
            "import sys, json; text = sys.stdin.read(); "
            "print(json.dumps({'takeaways': [str('body' in text)]}))"
        ),
    )
    paper = Paper(
        source="arxiv", source_id="1", title="T", authors=("A B",), year=2020, venue=None,
        abstract="", url="https://e.org/1",
    )
    pdf = pdf_module.ExtractedPdf(url="x", page_count=1, chars=4, text="body")
    summary = summarise_module.summarise_paper(paper, pdf, language="en", provider="cli")
    assert summary.takeaways == ("True",)


def test_the_cli_passes_its_command_without_changing_the_environment():
    # Set in os.environ, it outlived the run and reached every later one.
    args = cli.build_parser().parse_args(
        ["-q", "x", "--llm-provider", "cli", "--llm-command", _program("pass")]
    )
    assert cli._resolve_enrich_mode(args) == "auto"  # noqa: SLF001
    assert providers.COMMAND_ENV not in os.environ


def test_a_command_in_the_environment_belongs_to_the_provider_it_selects(monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, "cli")
    monkeypatch.setenv(providers.COMMAND_ENV, "my-ai -p")
    assert providers.resolve().command == "my-ai -p"
    # Claude Code chosen by a flag runs Claude Code, not the other program.
    assert providers.resolve("claude-cli").command.startswith("claude -p")
    monkeypatch.setenv(providers.PROVIDER_ENV, "openai")
    assert providers.resolve("cli").command == "my-ai -p"


def test_a_program_signed_in_to_an_account_gets_no_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-2")
    shows = _program(
        "import os; print(os.environ.get('OPENAI_API_KEY'), os.environ.get('ANTHROPIC_API_KEY'))"
    )
    preset = providers.resolve("gemini-cli", command=shows)
    assert providers.complete(preset, "s", "u").split() == ["None", "None"]
    own = providers.resolve("cli", command=shows)
    assert providers.complete(own, "s", "u").split() == ["sk-test-1", "sk-test-2"]


def test_a_timeout_ends_the_programs_the_program_started():
    # An npm shim starts the real program, which kept the pipes open, so the
    # timeout waited for it to finish.
    started = time.monotonic()
    with pytest.raises(SourceUnavailableError, match="did not finish"):
        cli_models.run_command(
            _program(
                "import subprocess, sys, time; "
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                "time.sleep(30)"
            ),
            "x", timeout=1,
        )
    assert time.monotonic() - started < 15


def test_a_command_that_names_its_model_keeps_it():
    assert cli_models.with_model(["claude", "-p", "--model", "a"], "--model", "b") == [
        "claude", "-p", "--model", "a",
    ]


def test_quotes_group_an_argument_on_every_system():
    assert cli_models.split_command('my-ai --flag="a b"') == ["my-ai", "--flag=a b"]
    assert cli_models.split_command("ollama run 'qwen3:8b'") == ["ollama", "run", "qwen3:8b"]


def test_a_relative_program_is_found_from_the_folder_it_was_named_in(tmp_path, monkeypatch):
    # The program runs in an empty folder of its own, where ./ai names nothing.
    script = tmp_path / ("ai.cmd" if os.name == "nt" else "ai")
    if os.name == "nt":
        script.write_text(f'@"{sys.executable}" -c "print(42)"\r\n', encoding="utf-8")
    else:
        script.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c "print(42)"\n', encoding="utf-8")
        script.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    relative = f".{os.sep}{script.name}"
    assert Path(cli_models.find_program(relative)).is_absolute()
    assert cli_models.run_command(relative, "").strip() == "42"


def test_ollama_lists_its_models(monkeypatch):
    class Done:
        stdout = (
            b"NAME             ID      SIZE\n"
            b"qwen3:8b         a1   5 GB\n"
            b"llama3.2:latest  b2   2 GB\n"
        )

    monkeypatch.setattr(cli_models.shutil, "which", lambda name: sys.executable)
    monkeypatch.setattr(cli_models.subprocess, "run", lambda *a, **k: Done())
    assert cli_models.list_ollama_models("ollama run") == ["qwen3:8b", "llama3.2:latest"]


def test_an_unused_command_is_reported(capsys):
    args = cli.build_parser().parse_args(["-q", "x", "--llm-command", "my-ai -p"])
    cli._warn_unused_command(args)  # noqa: SLF001
    assert "ignored with --llm-provider anthropic" in capsys.readouterr().err
    args = cli.build_parser().parse_args(
        ["-q", "x", "--llm-provider", "claude-cli", "--llm-command", "claude -p"]
    )
    cli._warn_unused_command(args)  # noqa: SLF001
    assert capsys.readouterr().err == ""

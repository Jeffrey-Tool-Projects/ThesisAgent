"""Summaries by an AI program on the command line: how it is run and what comes back.

A Python one-liner stands in for the program, so the tests need no AI tool
and no account.
"""
from __future__ import annotations

import os
import sys
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
    for name in ("claude-cli", "gemini-cli", "codex-cli", "ollama-cli", "cli"):
        assert providers.PROVIDERS[name].is_cli
    assert providers.PROVIDERS["ollama-cli"].is_local
    assert not providers.PROVIDERS["claude-cli"].is_local
    settings = providers.resolve("claude-cli", model="opus")
    assert settings.arguments()[:2] == ["claude", "-p"]
    assert settings.arguments()[-2:] == ["--model", "opus"]


def test_what_is_missing_is_said_before_anything_runs(monkeypatch):
    assert "no command" in providers.problem(providers.resolve("cli"))
    monkeypatch.setenv(providers.COMMAND_ENV, "no-such-ai-program-here")
    assert "not installed" in providers.problem(providers.resolve("cli"))
    monkeypatch.setenv(providers.COMMAND_ENV, _program("pass"))
    assert providers.problem(providers.resolve("cli")) is None
    # Ollama names its model on the command line, it has no default.
    monkeypatch.setenv(providers.COMMAND_ENV, _program("pass"))
    assert "no model" in providers.problem(providers.resolve("ollama-cli"))


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


def test_the_cli_takes_the_command_on_the_command_line(monkeypatch):
    seen = {}

    async def fake_run(args):
        seen["command"] = os.environ.get(providers.COMMAND_ENV)
        return 0

    monkeypatch.setattr(cli, "_run", fake_run)
    assert cli.main(["-q", "x", "--llm-provider", "cli", "--llm-command", "my-ai -p"]) == 0
    assert seen["command"] == "my-ai -p"

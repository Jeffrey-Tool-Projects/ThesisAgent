"""Choosing a language model and talking to OpenAI-compatible servers."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from thesisagents import cli
from thesisagents.core.exceptions import (
    ConfigError,
    ParseError,
    RateLimitError,
    SourceUnavailableError,
)
from thesisagents.core.models import Paper
from thesisagents.fetchers import http as http_module
from thesisagents.intelligence import providers, summarise
from thesisagents.intelligence.pdf import ExtractedPdf

_KEYS = sorted({p.key_env for p in providers.PROVIDERS.values() if p.key_env})


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        *_KEYS, providers.PROVIDER_ENV, providers.MODEL_ENV, providers.BASE_URL_ENV,
        providers.MAX_CHARS_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


# --- choosing ------------------------------------------------------------------------


def test_without_a_choice_it_is_anthropic():
    settings = providers.resolve()
    assert (settings.provider.name, settings.model) == (
        "anthropic", providers.DEFAULT_ANTHROPIC_MODEL
    )
    assert "ANTHROPIC_API_KEY" in providers.problem(settings)


def test_a_key_lying_around_selects_nothing(monkeypatch):
    # The text of a paper goes only where the user said.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("GEMINI_API_KEY", "g-x")
    assert providers.resolve().provider.name == "anthropic"
    assert providers.problem(providers.resolve()) is not None


def test_the_environment_chooses_and_arguments_win(monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, " Ollama ")
    monkeypatch.setenv(providers.MODEL_ENV, "qwen3")
    monkeypatch.setenv(providers.BASE_URL_ENV, "http://localhost:9/v1/")
    settings = providers.resolve()
    assert (settings.provider.name, settings.model, settings.base_url) == (
        "ollama", "qwen3", "http://localhost:9/v1"
    )
    assert providers.problem(settings) is None
    assert providers.resolve(model="phi").model == "phi"
    # A model and an address of one service mean nothing to another.
    other = providers.resolve("openai")
    assert (other.model, other.base_url) == ("", "https://api.openai.com/v1")


@pytest.mark.parametrize(("provider", "kwargs", "expected"), [
    ("openai", {"model": "m"}, "OPENAI_API_KEY is not set"),
    ("openai", {"api_key": "k"}, "no model is chosen for OpenAI"),
    ("ollama", {}, "no model is chosen"),
    ("custom", {"model": "m"}, "THESISAGENTS_LLM_BASE_URL is not set"),
])
def test_what_is_missing_is_named(provider, kwargs, expected):
    assert expected in providers.problem(providers.resolve(provider, **kwargs))


def test_a_custom_server_needs_no_key():
    settings = providers.resolve("custom", model="m", base_url="http://10.0.0.2:8000/v1")
    assert providers.problem(settings) is None


def test_an_unknown_provider_is_refused():
    with pytest.raises(ConfigError, match="unknown model provider 'gpt'"):
        providers.resolve("gpt")


def test_the_key_is_not_in_the_representation():
    assert "sk-secret" not in repr(providers.resolve("openai", model="m", api_key="sk-secret"))


def test_every_provider_is_https_or_on_this_computer():
    for provider in providers.PROVIDERS.values():
        if provider.base_url:
            assert provider.is_local or provider.base_url.startswith("https://")
            assert not provider.base_url.endswith("/")
    assert set(providers.provider_names(local=True)) == {"ollama", "lmstudio", "llamacpp", "vllm"}


@pytest.mark.parametrize(("provider", "base_url", "stated", "expected"), [
    ("openai", None, None, 80_000),
    ("ollama", None, None, 24_000),
    ("custom", "http://192.168.1.9/v1", None, 24_000),
    ("custom", "https://llm.example/v1", None, 80_000),
    ("ollama", None, "50000", 50_000),
    ("ollama", None, "lots", 24_000),
])
def test_how_much_of_a_paper_is_sent(monkeypatch, provider, base_url, stated, expected):
    if stated:
        monkeypatch.setenv(providers.MAX_CHARS_ENV, stated)
    assert providers.max_paper_chars(providers.resolve(provider, base_url=base_url)) == expected


# --- talking to a server -----------------------------------------------------------------


_SUMMARY = {"motivation": ["M"], "contributions": ["C"], "method": [], "results": ["R"],
            "limitations": [], "takeaways": ["T"]}


class _Server:
    """A model server on this computer, answering from a list."""

    def __init__(self) -> None:
        self.answers: list[tuple[int, object]] = []
        self.requests: list[tuple[str, dict, dict]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, body):
                outer.requests.append((self.path, dict(self.headers), body))
                status, payload = outer.answers.pop(0)
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                if status in (301, 302):
                    self.send_header("Location", "https://evil.example/")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802 - name fixed by the base class
                self._answer({})

            def do_POST(self):  # noqa: N802 - name fixed by the base class
                length = int(self.headers.get("Content-Length") or 0)
                self._answer(json.loads(self.rfile.read(length) or b"{}"))

            def log_message(self, *_args):
                pass

        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_port}/v1"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()


@pytest.fixture
def server(monkeypatch):
    # tests/conftest.py refuses live HTTP. This server is the test's own.
    monkeypatch.undo()
    server = _Server()
    yield server
    server.http.shutdown()
    server.http.server_close()


def _settings(server, **kwargs):
    return providers.resolve(
        "custom", model="qwen3", base_url=server.url, **{"api_key": "sk-secret", **kwargs}
    )


def _message(text):
    return {"choices": [{"message": {"content": text}}]}


def test_a_paper_is_summarised_by_a_local_server(server):
    server.answers = [(200, _message(
        "<think>{not json}</think>\n```json\n" + json.dumps(_SUMMARY) + "\n```"
    ))]
    paper = Paper(
        source="arxiv", source_id="1", title="T", authors=("A",), year=2020, venue=None,
        abstract="", url="https://example.org",
    )
    summary = summarise.summarise_paper(
        paper, ExtractedPdf("u", 1, 100_000, "x" * 100_000), language="es",
        provider="custom", model="qwen3", base_url=server.url,
    )
    assert (summary.motivation, summary.model, summary.language) == (("M",), "qwen3", "es")
    path, headers, body = server.requests[0]
    assert path == "/v1/chat/completions"
    assert "Authorization" not in headers
    assert body["response_format"] == {"type": "json_object"}
    sent = body["messages"][1]["content"]
    assert "Spanish" in sent
    assert sent.count("x" * 1000) <= 25


def test_an_option_the_server_refuses_is_left_out(server):
    server.answers = [
        (400, {"error": {"message": "max_tokens is not supported"}}), (200, _message("{}")),
    ]
    assert providers.complete(_settings(server), "s", "u") == "{}"
    assert "max_tokens" in server.requests[0][2]
    assert set(server.requests[1][2]) == {"model", "messages", "stream"}
    assert server.requests[1][1]["Authorization"] == "Bearer sk-secret"


@pytest.mark.parametrize(("answers", "error", "match"), [
    ([(401, {"error": {"message": "bad key sk-secret"}})], ConfigError, r"refused.*bad key \*\*\*"),
    ([(404, {"error": "model not found"})], ConfigError, "knows no model 'qwen3'"),
    ([(429, b"slow down")], RateLimitError, "slow down"),
    ([(500, b"oops")], SourceUnavailableError, "answered 500"),
    ([(302, b"")], SourceUnavailableError, "answered 302"),
    ([(400, {"error": "a"}), (400, {"error": "b"})], ConfigError, "refused the request: b"),
    ([(200, b"<html>")], ParseError, "did not answer with JSON"),
    ([(200, {"choices": []})], ParseError, "without a message"),
    ([(200, _message("  "))], ParseError, "answered with nothing"),
])
def test_failures_say_what_went_wrong(server, answers, error, match):
    server.answers = answers
    with pytest.raises(error, match=match) as caught:
        providers.complete(_settings(server), "s", "u")
    assert "sk-secret" not in str(caught.value)


def test_content_in_parts_is_joined(server):
    server.answers = [(200, _message([{"type": "text", "text": "a"}, {"text": "b"}]))]
    assert providers.complete(_settings(server), "s", "u") == "ab"


@pytest.mark.parametrize("payload", [
    {"data": [{"id": "b"}, {"id": "models/a"}, {"x": 1}]},
    [{"name": "b"}, {"id": "a"}],
])
def test_models_are_listed(server, payload):
    server.answers = [(200, payload)]
    assert providers.list_models(_settings(server)) == ["a", "b"]


def test_nobody_listening_is_explained(server):
    server.http.shutdown()
    server.http.server_close()
    settings = providers.resolve("ollama", model="m", base_url=server.url)
    with pytest.raises(SourceUnavailableError, match="Is it running"):
        providers.complete(settings, "s", "u")


def test_nothing_is_sent_while_something_is_missing():
    with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
        providers.complete(providers.resolve("openai", model="m"), "s", "u")


# --- the transport --------------------------------------------------------------------------


class _Inner(httpx.BaseTransport):
    def handle_request(self, request):
        return httpx.Response(200, json={}, request=request)


@pytest.mark.parametrize(("configured", "url", "allowed"), [
    ("http://localhost:11434/v1", "http://localhost:11434/v1/models", True),
    ("http://192.168.1.5/v1", "http://192.168.1.5/v1/models", True),
    ("https://api.openai.com/v1", "https://api.openai.com/v1/models", True),
    ("http://api.openai.com/v1", "http://api.openai.com/v1/models", False),
    ("http://localhost/v1", "https://evil.example/", False),
    ("https://api.openai.com/v1", "http://localhost/", False),
])
def test_the_transport_reaches_one_host_and_public_ones_by_https(configured, url, allowed):
    transport = http_module._LlmTransport(  # noqa: SLF001
        _Inner(), httpx.URL(configured).host
    )
    with httpx.Client(transport=transport) as client:
        if allowed:
            assert client.get(url).status_code == 200
        else:
            with pytest.raises(httpx.RequestError, match="refusing"):
                client.get(url)


def test_local_models_are_not_asked_through_a_proxy():
    with http_module.llm_client("http://localhost:1/v1") as client:
        assert client._trust_env is False  # noqa: SLF001
        assert client.follow_redirects is False


# --- command line ----------------------------------------------------------------------------


def _mode(*argv: str) -> str:
    args = cli.build_parser().parse_args(["-q", "x", *argv])
    return cli._resolve_enrich_mode(args)  # noqa: SLF001


def test_the_cli_enriches_with_a_usable_choice_only(monkeypatch):
    assert _mode() == "skip-no-key"
    assert _mode("--llm-provider", "ollama") == "skip-no-key"
    assert _mode("--llm-provider", "ollama", "--llm-model", "qwen3") == "auto"
    monkeypatch.setenv(providers.PROVIDER_ENV, "openai")
    monkeypatch.setenv(providers.MODEL_ENV, "m")
    assert _mode() == "skip-no-key"
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert _mode() == "auto"
    assert _mode("--lightweight") == "skip-lightweight"

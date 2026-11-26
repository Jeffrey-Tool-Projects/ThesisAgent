"""Which language model writes the summaries, and how it is asked.

Anthropic is called through its SDK. Most others speak the same HTTP
dialect, OpenAI's ``/chat/completions``, so one small client covers the
hosted services, programs on this computer (Ollama, LM Studio, llama.cpp,
vLLM) and any other server with a compatible endpoint (``custom``). The
``*-cli`` providers and ``cli`` run an AI program on the command line
instead (``claude -p``, ``gemini``, ``codex exec``, ``ollama run``, or any
command), see ``cli_models.py``.

The choice comes from ``THESISAGENTS_LLM_PROVIDER`` (``anthropic`` when
unset), ``THESISAGENTS_LLM_MODEL`` and ``THESISAGENTS_LLM_BASE_URL``, or from
the CLI flags and the GUI settings, which win. A key for some service lying
in the environment never selects that service: the paper's text is only sent
where the user said.

No model names are built in for the services other than Anthropic, because
they change every few months. :func:`list_models` asks the service.

Example::

    settings = resolve("ollama", model="qwen3")
    problem(settings)                       # None, or why it cannot be used
    complete(settings, "You are…", "Summarise…")
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final

import httpx

from thesisagents.core.exceptions import (
    ConfigError,
    ParseError,
    RateLimitError,
    SourceUnavailableError,
)
from thesisagents.fetchers.http import is_local_host, llm_client
from thesisagents.intelligence import cli_models
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

ANTHROPIC: Final[str] = "anthropic"
CUSTOM: Final[str] = "custom"
#: Runs the command line the user gives, the paper on standard input.
CLI: Final[str] = "cli"
DEFAULT_ANTHROPIC_MODEL: Final[str] = "claude-opus-5-5"
#: Models that always think, take ``effort`` and accept the server-side
#: fallback on a refusal. Another model named with ``--llm-model`` is sent the
#: plain request, which every Claude model accepts.
_CURRENT_ANTHROPIC_MODELS: Final[frozenset[str]] = frozenset({
    "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1",
    "claude-fable-5-2",
})
#: Room for the thinking as well as the answer: thinking counts against
#: ``max_tokens``, and 4000 cut summaries off. Below the size that needs
#: streaming.
_ANTHROPIC_MAX_TOKENS: Final[int] = 16_000
#: A summary is extraction more than reasoning, and ``medium`` is the default
#: of Claude Opus 5.5. Named, so that a newer default does not change the cost.
_ANTHROPIC_EFFORT: Final[str] = "medium"
_FALLBACK_BETA: Final[str] = "server-side-fallback-2026-07-01"

PROVIDER_ENV: Final[str] = "THESISAGENTS_LLM_PROVIDER"
MODEL_ENV: Final[str] = "THESISAGENTS_LLM_MODEL"
BASE_URL_ENV: Final[str] = "THESISAGENTS_LLM_BASE_URL"
CUSTOM_KEY_ENV: Final[str] = "THESISAGENTS_LLM_API_KEY"
MAX_CHARS_ENV: Final[str] = "THESISAGENTS_LLM_MAX_CHARS"
#: The command line of a command-line provider, in place of its own.
COMMAND_ENV: Final[str] = "THESISAGENTS_LLM_COMMAND"

#: How much of a paper is sent. A program on this computer usually runs with
#: a small context window and silently drops what does not fit, the end of
#: the paper first, so it gets less unless the user says otherwise.
_HOSTED_MAX_CHARS: Final[int] = 80_000
_LOCAL_MAX_CHARS: Final[int] = 24_000
_MAX_OUTPUT_TOKENS: Final[int] = 4_000
_LOCAL_SOURCE: Final[str] = "llm"


@dataclass(frozen=True, slots=True)
class Provider:
    """One service. ``key_env`` is empty for those that need no key.

    A command-line provider has a ``command`` instead of an address, and
    ``model_flag`` says how a model is named on it (empty: as the last
    argument). ``local`` marks one whose model runs on this computer.
    """

    name: str
    label: str
    base_url: str = ""
    key_env: str = ""
    command: str = ""
    model_flag: str = ""
    local: bool = False
    needs_model: bool = False

    @property
    def is_cli(self) -> bool:
        """Whether it is a program run on the command line."""
        return bool(self.command) or self.name == CLI

    @property
    def is_local(self) -> bool:
        """Whether it runs on this computer, so no text leaves it."""
        return self.local or self.base_url.startswith("http://localhost")


#: In the order the settings list them: hosted services, then local programs.
PROVIDERS: Final[dict[str, Provider]] = {
    provider.name: provider
    for provider in (
        Provider(ANTHROPIC, "Anthropic", key_env="ANTHROPIC_API_KEY"),
        Provider("openai", "OpenAI", "https://api.openai.com/v1", "OPENAI_API_KEY"),
        Provider(
            "gemini", "Google Gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY",
        ),
        Provider("mistral", "Mistral", "https://api.mistral.ai/v1", "MISTRAL_API_KEY"),
        Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY"),
        Provider("xai", "xAI", "https://api.x.ai/v1", "XAI_API_KEY"),
        Provider("groq", "Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY"),
        Provider("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
        Provider("together", "Together AI", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
        Provider(
            "fireworks", "Fireworks AI",
            "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY",
        ),
        Provider(
            "dashscope", "Alibaba Qwen",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY",
        ),
        Provider("moonshot", "Moonshot AI", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY"),
        Provider("ollama", "Ollama", "http://localhost:11434/v1"),
        Provider("lmstudio", "LM Studio", "http://localhost:1234/v1"),
        Provider("llamacpp", "llama.cpp", "http://localhost:8080/v1"),
        Provider("vllm", "vLLM", "http://localhost:8000/v1"),
        Provider(CUSTOM, "Custom", key_env=CUSTOM_KEY_ENV),
        # Programs on the command line, each with the account it is signed in to.
        # No tools and nothing remembered: the program only reads and answers.
        Provider(
            "claude-cli", "Claude Code",
            command='claude -p --output-format text --tools "" --no-session-persistence '
            "--permission-prompts none",
            model_flag="--model",
        ),
        Provider("gemini-cli", "Gemini CLI", command="gemini", model_flag="--model"),
        Provider(
            "codex-cli", "Codex CLI",
            command="codex exec --skip-git-repo-check --sandbox read-only --ephemeral "
            "--color never -",
            model_flag="--model",
        ),
        Provider(
            "ollama-cli", "Ollama", command="ollama run", local=True,
            needs_model=True,
        ),
        Provider(CLI, "Command line", needs_model=False),
    )
}


@dataclass(frozen=True, slots=True)
class LlmSettings:
    """A resolved choice. ``api_key`` is not shown by ``repr``, so no log has it."""

    provider: Provider
    model: str
    base_url: str
    api_key: str = ""
    #: The command line of a command-line provider, before the model is added.
    command: str = ""

    def __repr__(self) -> str:
        return (
            f"LlmSettings({self.provider.name!r}, model={self.model!r}, "
            f"base_url={self.base_url!r}, command={self.command!r}, "
            f"api_key={'***' if self.api_key else ''!r})"
        )

    def arguments(self) -> list[str]:
        """The program and its arguments, the model included."""
        parts = cli_models.split_command(self.command)
        return cli_models.with_model(parts, self.provider.model_flag, self.model)

    @property
    def describes(self) -> str:
        """For a message to the user: ``"Ollama (qwen3)"``."""
        return f"{self.provider.label} ({self.model})" if self.model else self.provider.label


def selected_provider() -> str:
    """The provider named in the environment, ``anthropic`` when none is."""
    return os.environ.get(PROVIDER_ENV, "").strip().lower() or ANTHROPIC


def resolve(
    provider: str | None = None,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    command: str | None = None,
) -> LlmSettings:
    """Fill what was not given from the environment and the provider's defaults.

    ``THESISAGENTS_LLM_MODEL`` and ``…_BASE_URL`` belong to the provider the
    environment selects. When another one is asked for, they are not used: a
    model of one service means nothing to the next. ``…_COMMAND`` is a whole
    command line and applies to whichever command-line provider is chosen.
    """
    name = (provider or "").strip().lower() or selected_provider()
    if name not in PROVIDERS:
        raise ConfigError(
            f"unknown model provider {name!r}. Available: {', '.join(PROVIDERS)}"
        )
    chosen = PROVIDERS[name]
    own_environment = name == selected_provider()
    if not model and own_environment:
        model = os.environ.get(MODEL_ENV, "")
    if not base_url and own_environment:
        base_url = os.environ.get(BASE_URL_ENV, "")
    if not model and name == ANTHROPIC:
        model = DEFAULT_ANTHROPIC_MODEL
    if api_key is None:
        api_key = os.environ.get(chosen.key_env, "") if chosen.key_env else ""
    # Like the model: the command in the environment belongs to the provider it
    # selects (one of Claude Code means nothing to Codex), and to ``cli``,
    # which has no command of its own.
    if chosen.is_cli and not command and (own_environment or name == CLI):
        command = os.environ.get(COMMAND_ENV, "")
    return LlmSettings(
        provider=chosen,
        model=(model or "").strip(),
        base_url=(base_url or "").strip().rstrip("/") or chosen.base_url,
        api_key=api_key.strip(),
        command=(command or "").strip() or chosen.command if chosen.is_cli else "",
    )


def problem(settings: LlmSettings) -> str | None:
    """Why ``settings`` cannot be used, or None. Asks nobody.

    Whether a key is valid or a program runs shows only when it is used.
    """
    provider = settings.provider
    if provider.is_cli:
        return _cli_problem(settings)
    if provider.name == CUSTOM and not settings.base_url:
        return f"{BASE_URL_ENV} is not set, which the custom provider needs"
    if provider.key_env and provider.name != CUSTOM and not settings.api_key:
        return f"{provider.key_env} is not set"
    if not settings.model:
        return (
            f"no model is chosen for {provider.label}. Set {MODEL_ENV}, pass --llm-model, "
            "or choose one in the settings"
        )
    return None


def _cli_problem(settings: LlmSettings) -> str | None:
    if not settings.command:
        return f"no command is set. Set {COMMAND_ENV} or pass --llm-command"
    try:
        program = cli_models.find_program(settings.command)
    except ConfigError as err:
        return str(err)
    if program is None:
        name = cli_models.split_command(settings.command)[0]
        return f"{name} is not installed or not on PATH"
    if settings.provider.needs_model and not settings.model:
        return (
            f"no model is chosen for {settings.provider.label}. Set {MODEL_ENV}, "
            "pass --llm-model, or choose one in the settings"
        )
    return None


def max_paper_chars(settings: LlmSettings) -> int:
    """How many characters of a paper to send."""
    stated = os.environ.get(MAX_CHARS_ENV, "").strip()
    if stated.isdigit() and int(stated) > 0:
        return int(stated)
    if settings.provider.is_cli:
        return _LOCAL_MAX_CHARS if settings.provider.is_local else _HOSTED_MAX_CHARS
    try:
        host = httpx.URL(settings.base_url).host if settings.base_url else ""
    except httpx.InvalidURL:
        host = ""  # the request reports the address
    return _LOCAL_MAX_CHARS if host and is_local_host(host) else _HOSTED_MAX_CHARS


def complete(settings: LlmSettings, system: str, user: str) -> str:
    """Ask the model and return its text. Blocking.

    Raises ``ConfigError`` when the key, the model or the address is refused,
    ``RateLimitError``, ``SourceUnavailableError`` when nobody answers, and
    ``ParseError`` when the answer is not one.
    """
    reason = problem(settings)
    if reason:
        raise ConfigError(reason)
    if settings.provider.name == ANTHROPIC:
        return _complete_anthropic(settings, system, user)
    if settings.provider.is_cli:
        # One text: not every program takes a system prompt, and none the same way.
        return cli_models.run_command(
            settings.arguments(), f"{system}\n\n{user}", label=settings.provider.label,
            hidden=() if settings.provider.name == CLI else _app_keys(),
        )
    return _complete_compatible(settings, system, user)


def _app_keys() -> set[str]:
    """The API key variables of every provider, which the app may have set.

    A program signed in to an account must use that account. Your own
    command (``cli``) keeps them: it may be a tool that needs one.
    """
    return {p.key_env for p in PROVIDERS.values() if p.key_env} | {CUSTOM_KEY_ENV}


def list_models(settings: LlmSettings) -> list[str]:
    """The models the service offers, for a menu. Blocking.

    Raises like :func:`complete`.
    """
    if settings.provider.name == ANTHROPIC:
        client = _anthropic_client(settings)
        return [entry.id for entry in client.models.list(limit=100).data]
    if settings.provider.name == "ollama-cli":
        return cli_models.list_ollama_models(settings.command)
    if settings.provider.is_cli:
        raise ConfigError(
            f"{settings.provider.label} does not list its models here. Type the name "
            "the program knows, or leave it empty for its own default"
        )
    payload = _request(settings, "GET", "/models", None)
    entries = payload.get("data") if isinstance(payload, dict) else payload
    names = [
        str(entry.get("id") or entry.get("name"))
        for entry in entries or ()
        if isinstance(entry, dict) and (entry.get("id") or entry.get("name"))
    ]
    # Gemini answers with "models/gemini-…" and takes the short form.
    return sorted(name.removeprefix("models/") for name in names)


# --- Anthropic ------------------------------------------------------------------


def _anthropic_client(settings: LlmSettings) -> Any:
    try:
        import anthropic  # imported lazily so the extra is truly optional
    except ImportError as err:
        raise ConfigError(
            "anthropic is not installed; run `pip install thesisagents[intelligence]`"
        ) from err
    if not settings.api_key:
        raise ConfigError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=settings.api_key)


def _complete_anthropic(settings: LlmSettings, system: str, user: str) -> str:
    """One summary from Claude, the text of its answer.

    The boundary this guards: what comes back besides the answer. The
    current models think first, in blocks without text, and may decline a
    paper (``stop_reason`` ``refusal``) or run out of room (``max_tokens``).
    Each of those is reported as such instead of a JSON error further on.
    On a current model a refusal is first retried by the API on a fallback
    model it picks by the refusal's category (``fallbacks="default"``).
    """
    client = _anthropic_client(settings)
    request: dict[str, Any] = {
        "model": settings.model,
        # Marked for the prompt cache, so twenty papers in one session pay for
        # the instructions once.
        "system": [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ],
        "messages": [{"role": "user", "content": user}],
    }
    if settings.model in _CURRENT_ANTHROPIC_MODELS:
        response = client.beta.messages.create(
            **request,
            max_tokens=_ANTHROPIC_MAX_TOKENS,
            output_config={"effort": _ANTHROPIC_EFFORT},
            betas=[_FALLBACK_BETA],
            fallbacks="default",
        )
    else:
        response = client.messages.create(**request, max_tokens=_MAX_OUTPUT_TOKENS)
    stop = getattr(response, "stop_reason", None)
    if stop == "refusal":
        details = getattr(response, "stop_details", None)
        category = getattr(details, "category", None) or "unspecified"
        raise ParseError("intelligence", f"the model declined this paper ({category})")
    texts = [
        block.text for block in response.content
        if getattr(block, "type", None) == "text" and block.text
    ]
    if stop == "max_tokens":
        raise ParseError("intelligence", "the answer was cut off at the output limit")
    if texts:
        return "".join(texts)
    raise ParseError("intelligence", "Anthropic response had no text block")


# --- OpenAI-compatible -------------------------------------------------------------


def _complete_compatible(settings: LlmSettings, system: str, user: str) -> str:
    body: dict[str, Any] = {
        "model": settings.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    extras = {
        "response_format": {"type": "json_object"},
        "max_tokens": _MAX_OUTPUT_TOKENS,
    }
    try:
        payload = _request(settings, "POST", "/chat/completions", {**body, **extras})
    except _BadRequestError as err:
        # Not every server knows both options (newer OpenAI models refuse
        # max_tokens, some local servers refuse response_format). The prompt
        # asks for JSON anyway.
        _LOG.info("%s refused an option, asking again without: %s", settings.provider.label, err)
        try:
            payload = _request(settings, "POST", "/chat/completions", body)
        except _BadRequestError as again:
            raise ConfigError(f"{settings.describes} refused the request: {again}") from again
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as err:
        raise ParseError(
            "intelligence", f"{settings.describes} answered without a message"
        ) from err
    if isinstance(text, list):
        # Some servers send the content in parts.
        text = "".join(str(part.get("text", "")) for part in text if isinstance(part, dict))
    if not isinstance(text, str) or not text.strip():
        raise ParseError("intelligence", f"{settings.describes} answered with nothing")
    return text


class _BadRequestError(Exception):
    """The server understood us and refused an option (HTTP 400 / 422)."""


def _request(settings: LlmSettings, method: str, path: str, body: Any) -> Any:
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    try:
        with llm_client(settings.base_url) as client:
            response = client.request(
                method, settings.base_url + path, json=body, headers=headers
            )
    except httpx.InvalidURL as err:
        raise ConfigError(f"{settings.base_url} is not a usable address: {err}") from err
    except httpx.TimeoutException as err:
        raise SourceUnavailableError(
            _LOCAL_SOURCE, f"{settings.describes} did not answer in time"
        ) from err
    except httpx.HTTPError as err:
        hint = " Is it running?" if settings.provider.is_local else ""
        raise SourceUnavailableError(
            _LOCAL_SOURCE, f"{settings.provider.label} at {settings.base_url} cannot be "
            f"reached: {_hide(str(err), settings.api_key)}.{hint}",
        ) from err
    _raise_for_status(settings, response)
    try:
        return response.json()
    except ValueError as err:
        raise ParseError(
            "intelligence", f"{settings.provider.label} did not answer with JSON"
        ) from err


def _raise_for_status(settings: LlmSettings, response: httpx.Response) -> None:
    status = response.status_code
    if status < 300:
        return
    detail = _hide(_error_text(response), settings.api_key)
    if status in (400, 422):
        raise _BadRequestError(detail)
    if status in (401, 403):
        raise ConfigError(f"{settings.provider.label} refused the API key: {detail}")
    if status == 404:
        raise ConfigError(
            f"{settings.provider.label} knows no model {settings.model!r} at "
            f"{settings.base_url}: {detail}"
        )
    if status == 429:
        raise RateLimitError(_LOCAL_SOURCE, f"{settings.provider.label}: {detail}")
    raise SourceUnavailableError(
        _LOCAL_SOURCE, f"{settings.provider.label} answered {status}: {detail}"
    )


def _error_text(response: httpx.Response) -> str:
    """The server's own words, shortened."""
    try:
        payload = response.json()
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        text = error.get("message", error) if isinstance(error, dict) else error
    except ValueError:
        text = response.text
    return " ".join(str(text).split())[:300]


def _hide(text: str, secret: str) -> str:
    """Some services quote the key they refuse."""
    return text.replace(secret, "***") if secret else text


def provider_names(local: bool | None = None) -> Iterable[str]:
    """Names of all providers, or only the local / hosted ones."""
    return [
        name for name, provider in PROVIDERS.items()
        if local is None or provider.is_local is local
    ]

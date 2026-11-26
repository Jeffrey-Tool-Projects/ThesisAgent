"""Choosing the language model in Settings."""

from __future__ import annotations

import os

import pytest

from thesisagents.core.exceptions import ConfigError
from thesisagents.gui.credentials import SERVICE
from thesisagents.gui.main_window import MainWindow
from thesisagents.gui.pages.settings import SettingsPage, apply_saved_env, settings_store
from thesisagents.gui.widgets.model_card import ModelCard, apply_saved_model
from thesisagents.intelligence import providers


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    names = {p.key_env for p in providers.PROVIDERS.values() if p.key_env}
    for name in (
        *names, providers.PROVIDER_ENV, providers.MODEL_ENV, providers.BASE_URL_ENV,
        providers.COMMAND_ENV,
    ):
        monkeypatch.setenv(name, "x")
        monkeypatch.delenv(name)


def _page(qtbot) -> SettingsPage:
    page = SettingsPage(ui_language="en")
    qtbot.addWidget(page)
    return page


def _choose(card: ModelCard, name: str) -> None:
    card.provider_combo().setCurrentIndex(card.provider_combo().findData(name))


def test_a_choice_is_saved_and_mirrored(qtbot, credential_store):
    page = _page(qtbot)
    card = page.model_card()
    assert card.provider() == "anthropic"
    _choose(card, "openai")
    card.model_combo().setCurrentText("some-model")
    card.key_input().setText("sk-1")
    page.trigger_save()
    assert os.environ[providers.PROVIDER_ENV] == "openai"
    assert os.environ[providers.MODEL_ENV] == "some-model"
    assert os.environ["OPENAI_API_KEY"] == "sk-1"
    assert credential_store.saved[SERVICE, "api/llm_openai"] == "sk-1"
    assert "sk-1" not in str(settings_store().allKeys())
    assert not settings_store().contains("api/llm_openai")
    assert providers.problem(providers.resolve()) is None
    reopened = _page(qtbot)
    again = reopened.model_card()
    assert again.provider() == "openai"
    assert (again.model_combo().currentText(), again.key_input().text()) == ("some-model", "sk-1")


def test_every_provider_keeps_its_own_fields(qtbot):
    page = _page(qtbot)
    card = page.model_card()
    _choose(card, "openai")
    card.model_combo().setCurrentText("a")
    _choose(card, "ollama")
    assert card.model_combo().currentText() == ""
    card.model_combo().setCurrentText("qwen3")
    card.base_url_input().setText("http://localhost:9/v1")
    _choose(card, "openai")
    assert card.model_combo().currentText() == "a"
    _choose(card, "ollama")
    page.trigger_save()
    settings = providers.resolve()
    assert (settings.model, settings.base_url) == ("qwen3", "http://localhost:9/v1")
    _choose(card, "openai")
    page.trigger_save()
    # The other provider's address must not stay in the environment.
    assert providers.BASE_URL_ENV not in os.environ
    assert os.environ[providers.MODEL_ENV] == "a"


@pytest.mark.parametrize(("name", "url_shown", "key_shown", "note"), [
    ("anthropic", False, False, "under API keys"),
    ("openai", True, True, "sent to this service"),
    ("ollama", True, False, "no text leaves it"),
    ("custom", True, True, "sent to this service"),
    ("claude-cli", True, False, "signed in"),
    ("ollama-cli", True, False, "no text leaves it"),
])
def test_only_the_fields_a_provider_needs_are_shown(qtbot, name, url_shown, key_shown, note):
    card = ModelCard("en")
    qtbot.addWidget(card)
    _choose(card, name)
    assert card.base_url_input().isHidden() is not url_shown
    assert card.key_input().isHidden() is not key_shown
    assert note in card.note()


def test_nothing_saved_leaves_the_environment_alone(monkeypatch):
    monkeypatch.setenv(providers.PROVIDER_ENV, "ollama")
    monkeypatch.setenv(providers.MODEL_ENV, "mine")
    apply_saved_env()
    assert providers.resolve().model == "mine"
    settings_store().setValue("llm/provider", "gone")
    apply_saved_model(settings_store())
    assert providers.resolve().model == "mine"


def test_models_are_listed_on_demand(qtbot, monkeypatch):
    asked = []

    def fake(settings):
        asked.append(settings)
        return ["m1", "m2"]

    monkeypatch.setattr(providers, "list_models", fake)
    card = ModelCard("en")
    qtbot.addWidget(card)
    _choose(card, "ollama")
    card.list_button().click()
    qtbot.waitUntil(lambda: card.list_button().isEnabled(), timeout=3000)
    assert [card.model_combo().itemText(i) for i in range(2)] == ["m1", "m2"]
    assert card.model_combo().currentText() == "m1"
    assert "2 models" in card.note()
    assert asked[0].base_url == "http://localhost:11434/v1"


def test_a_failed_listing_is_explained(qtbot, monkeypatch):
    def fake(_settings):
        raise ConfigError("the key was refused")

    monkeypatch.setattr(providers, "list_models", fake)
    card = ModelCard("en")
    qtbot.addWidget(card)
    _choose(card, "openai")
    card.list_button().click()
    qtbot.waitUntil(lambda: card.list_button().isEnabled(), timeout=3000)
    assert "the key was refused" in card.note()


def test_an_answer_for_another_provider_is_dropped(qtbot):
    card = ModelCard("en")
    qtbot.addWidget(card)
    _choose(card, "ollama")
    card._on_listed(("openai", ["x"]))  # noqa: SLF001
    assert card.model_combo().count() == 0


def test_the_enrich_page_names_the_chosen_model(qtbot):
    window = MainWindow(ui_language="en")
    qtbot.addWidget(window)
    card = window.settings_page().model_card()
    _choose(card, "ollama")
    card.model_combo().setCurrentText("qwen3")
    window.settings_page().trigger_save()
    shown = window.enrich_page()._model_input.placeholderText()  # noqa: SLF001
    assert shown == "Ollama (qwen3)"



def test_a_command_line_program_is_chosen_with_its_command(qtbot):
    page = _page(qtbot)
    card = page.model_card()
    _choose(card, "claude-cli")
    assert "(command line)" in card.provider_combo().currentText()
    label = card._form.labelForField(card.base_url_input())  # noqa: SLF001
    assert label.text() == "Command"
    assert card.base_url_input().placeholderText().startswith("claude -p")
    card.base_url_input().setText("claude -p --model opus")
    page.trigger_save()
    assert os.environ[providers.PROVIDER_ENV] == "claude-cli"
    assert os.environ[providers.COMMAND_ENV] == "claude -p --model opus"
    assert providers.BASE_URL_ENV not in os.environ
    assert providers.resolve().command == "claude -p --model opus"
    _choose(card, "ollama")
    assert card._form.labelForField(card.base_url_input()).text() == "Server address"  # noqa: SLF001
    page.trigger_save()
    assert providers.COMMAND_ENV not in os.environ

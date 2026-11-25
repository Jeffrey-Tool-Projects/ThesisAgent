"""The Settings card that chooses the language model for summaries.

Every provider keeps its own model, address and key, so switching back and
forth loses nothing. Keys go to the credential store like the other API keys.
What is saved is mirrored into the environment variables that
``intelligence/providers.py`` reads, so the CLI code paths see the same.

Example::

    card = ModelCard("en")
    card.load(settings_store())
    card.save(settings_store())
"""

from __future__ import annotations

import os
from typing import Final

from PySide6.QtCore import QSettings, QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from thesisagents.gui import credentials
from thesisagents.gui.i18n import t
from thesisagents.gui.widgets.responsive import adapt_form_rows, make_card
from thesisagents.gui.workers import BlockingWorker
from thesisagents.intelligence import providers

_PROVIDER_KEY: Final[str] = "llm/provider"


def _secret_key(provider: str) -> str:
    """Where a provider's API key is kept. Anthropic's has its own field in Settings."""
    return "api/anthropic" if provider == providers.ANTHROPIC else f"api/llm_{provider}"


def _mirror(name: str, value: str) -> None:
    if value:
        os.environ[name] = value
    else:
        os.environ.pop(name, None)


def apply_saved_model(store: QSettings) -> None:
    """Push the saved choice into the environment of this process.

    Nothing saved leaves the environment alone, so variables set outside the
    app keep working.
    """
    name = store.value(_PROVIDER_KEY, "", type=str)
    if name not in providers.PROVIDERS:
        return
    provider = providers.PROVIDERS[name]
    os.environ[providers.PROVIDER_ENV] = name
    _mirror(providers.MODEL_ENV, store.value(f"llm/model/{name}", "", type=str))
    _mirror(providers.BASE_URL_ENV, store.value(f"llm/base_url/{name}", "", type=str))
    if provider.key_env and name != providers.ANTHROPIC:
        _mirror(provider.key_env, credentials.read(store, _secret_key(name)))


class ModelCard(QWidget):
    """Provider, model, address and key."""

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._language = language
        self._shown = ""
        self._drafts: dict[str, tuple[str, str, str]] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card, layout = make_card(t("model.card", language), self)
        outer.addWidget(card)
        self._form = QFormLayout()
        layout.addLayout(self._form)
        self._provider = QComboBox(card)
        for name, provider in providers.PROVIDERS.items():
            label = provider.label
            if provider.is_local:
                label = t("model.local", language, name=label)
            elif name == providers.CUSTOM:
                label = t("model.custom", language)
            self._provider.addItem(label, name)
        self._provider.currentIndexChanged.connect(self._on_provider_changed)
        self._form.addRow(t("model.provider", language), self._provider)

        row = QWidget(card)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        self._model = QComboBox(card)
        self._model.setEditable(True)
        self._model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._model.setAccessibleName(t("enrich.model_label", language))
        self._list_button = QPushButton(t("model.list", language), card)
        self._list_button.clicked.connect(self._on_list)
        row_layout.addWidget(self._model, stretch=1)
        row_layout.addWidget(self._list_button)
        self._form.addRow(t("enrich.model_label", language), row)

        self._base_url = QLineEdit(card)
        self._form.addRow(t("model.base_url", language), self._base_url)
        self._key = QLineEdit(card)
        self._key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self._form.addRow(t("model.key", language), self._key)
        adapt_form_rows(card, self._form)
        self._note = QLabel("", card)
        self._note.setObjectName("Muted")
        self._note.setWordWrap(True)
        layout.addWidget(self._note)
        self._on_provider_changed()

    # --- state ------------------------------------------------------------

    def load(self, store: QSettings) -> None:
        """Show what is saved, else what the environment selects."""
        self._drafts = {
            name: (
                store.value(f"llm/model/{name}", "", type=str),
                store.value(f"llm/base_url/{name}", "", type=str),
                credentials.read(store, _secret_key(name))
                if provider.key_env and name != providers.ANTHROPIC else "",
            )
            for name, provider in providers.PROVIDERS.items()
        }
        chosen = store.value(_PROVIDER_KEY, "", type=str)
        if chosen not in providers.PROVIDERS:
            chosen = providers.selected_provider()
        self._shown = ""
        index = max(0, self._provider.findData(chosen))
        self._provider.setCurrentIndex(index)
        self._on_provider_changed()

    def save(self, store: QSettings) -> None:
        """Store every provider's fields and the choice, and mirror the choice."""
        self._keep_draft()
        for name, (model, base_url, key) in self._drafts.items():
            store.setValue(f"llm/model/{name}", model)
            store.setValue(f"llm/base_url/{name}", base_url)
            if providers.PROVIDERS[name].key_env and name != providers.ANTHROPIC:
                credentials.write(store, _secret_key(name), key)
        store.setValue(_PROVIDER_KEY, self.provider())
        apply_saved_model(store)

    def provider(self) -> str:
        return str(self._provider.currentData())

    def settings(self) -> providers.LlmSettings:
        """The choice as the fields show it now, saved or not."""
        provider = providers.PROVIDERS[self.provider()]
        own_key = provider.key_env and provider.name != providers.ANTHROPIC
        return providers.resolve(
            provider.name,
            model=self._model.currentText().strip(),
            base_url=self._base_url.text().strip(),
            api_key=self._key.text().strip() if own_key else None,
        )

    def _keep_draft(self) -> None:
        if self._shown:
            self._drafts[self._shown] = (
                self._model.currentText().strip(),
                self._base_url.text().strip(),
                self._key.text().strip(),
            )

    def _on_provider_changed(self, _index: int = 0) -> None:
        self._keep_draft()
        name = self.provider()
        provider = providers.PROVIDERS[name]
        self._shown = name
        model, base_url, key = self._drafts.get(name, ("", "", ""))
        self._model.clear()
        self._model.setCurrentText(model)
        default = providers.DEFAULT_ANTHROPIC_MODEL if name == providers.ANTHROPIC else ""
        self._model.lineEdit().setPlaceholderText(default)
        self._base_url.setText(base_url)
        self._base_url.setPlaceholderText(provider.base_url or "https://…/v1")
        self._key.setText(key)
        self._form.setRowVisible(self._base_url, name != providers.ANTHROPIC)
        self._form.setRowVisible(
            self._key, bool(provider.key_env) and name != providers.ANTHROPIC
        )
        key_of_note = (
            "model.note_local" if provider.is_local
            else "model.note_anthropic" if name == providers.ANTHROPIC
            else "model.note_hosted"
        )
        self._note.setText(t(key_of_note, self._language))

    # --- listing -------------------------------------------------------------

    def _on_list(self) -> None:
        settings = self.settings()
        self._list_button.setEnabled(False)
        self._note.setText(t("status.busy", self._language))
        worker = BlockingWorker(lambda: (settings.provider.name, providers.list_models(settings)))
        worker.signals.finished.connect(self._on_listed)
        worker.signals.failed.connect(self._on_list_failed)
        QThreadPool.globalInstance().start(worker)

    def _on_listed(self, result: object) -> None:
        self._list_button.setEnabled(True)
        name, models = result  # type: ignore[misc]
        if name != self.provider():
            return
        chosen = self._model.currentText()
        self._model.clear()
        self._model.addItems(models)
        self._model.setCurrentText(chosen or (models[0] if models else ""))
        self._note.setText(t("model.listed", self._language, count=len(models)))

    def _on_list_failed(self, error: object) -> None:
        self._list_button.setEnabled(True)
        self._note.setText(t("model.list_failed", self._language, error=str(error)))

    # --- accessors used by tests ---------------------------------------------

    def provider_combo(self) -> QComboBox:
        return self._provider

    def model_combo(self) -> QComboBox:
        return self._model

    def base_url_input(self) -> QLineEdit:
        return self._base_url

    def key_input(self) -> QLineEdit:
        return self._key

    def list_button(self) -> QPushButton:
        return self._list_button

    def note(self) -> str:
        return self._note.text()

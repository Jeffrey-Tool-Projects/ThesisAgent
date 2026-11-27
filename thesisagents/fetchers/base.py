"""Fetcher base class and source registry. Each source plugin subclasses Fetcher."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from dataclasses import dataclass

from thesisagents.core.exceptions import ConfigError
from thesisagents.core.models import Paper, Query
from thesisagents.fetchers.rate_limit import RateLimit, TokenBucket, shared_bucket
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FetcherConfig:
    """Static configuration block declared by every source plugin."""

    name: str
    rate_limit: RateLimit
    requires_api_key: bool = False
    enabled_by_default: bool = True
    # Env var the plugin checks to enable itself (e.g. Springer needs an
    # API key; without it the plugin raises ConfigError at construction).
    opt_in_env_var: str | None = None
    # Env var the plugin checks to disable itself when it is otherwise
    # default-ON. Used by IEEE / Scholar — both scrape paths are
    # default-on but the user can flip them off via this env var.
    opt_out_env_var: str | None = None
    # The upstream service whose request quota this source draws on, when
    # it is not the source's own name. ACM searches through the Crossref
    # API, so it sets "crossref" and both plugins share one bucket
    # instead of together sending twice Crossref's rate.
    rate_limit_group: str | None = None


class Fetcher(ABC):
    """Strategy interface every source plugin implements."""

    config: FetcherConfig

    def __init__(self) -> None:
        # The process-wide bucket of this source, not a new one: every
        # search loads a new fetcher, and a fresh full bucket per search
        # let concurrent searches each send the whole burst.
        group = self.config.rate_limit_group or self.config.name
        self._bucket = shared_bucket(group, self.config.rate_limit)

    @property
    def bucket(self) -> TokenBucket:
        return self._bucket

    @abstractmethod
    async def search(self, query: Query) -> list[Paper]:
        """Run the query against this source and return up to `query.max_results`."""

    async def fetch_by_id(self, identifier: str) -> Paper:
        """Fetch a single paper by source-native identifier.

        Subclasses that support direct-by-ID lookup MUST override this. The
        default raises so callers can detect unsupported sources cleanly.
        """
        raise NotImplementedError(
            f"source '{self.config.name}' does not support fetch_by_id"
        )



def load_fetcher(name: str) -> Fetcher:
    """Load and instantiate the fetcher plugin for the given source name."""
    try:
        module = importlib.import_module(f"thesisagents.sources.{name}")
    except ImportError as err:
        raise ConfigError(f"unknown or unavailable source plugin: {name}") from err
    fetcher_class = getattr(module, "fetcher_class", None)
    if fetcher_class is None:
        raise ConfigError(
            f"source plugin '{name}' does not expose `fetcher_class`"
        )
    instance = fetcher_class()
    if not isinstance(instance, Fetcher):
        raise ConfigError(
            f"source plugin '{name}' fetcher_class did not produce a Fetcher"
        )
    _LOG.debug("Loaded fetcher plugin %s", name)
    return instance

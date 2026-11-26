"""How far a citation snowball goes: the bounds, and the form that sets them.

Example::

    form = SnowballBoundsForm("en")
    form.set_bounds(SnowballBounds(seeds=10))
    form.bounds()
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QSpinBox, QWidget

from thesisagents.cli_snowball import DEFAULT_SNOWBALL_MAX_TOTAL, DEFAULT_SNOWBALL_SEEDS
from thesisagents.core.constants import (
    MAX_RESULTS_PER_SOURCE,
    SNOWBALL_DEFAULT_DEPTH,
    SNOWBALL_DEFAULT_MAX_PER_SEED,
    SNOWBALL_MAX_DEPTH,
    SNOWBALL_MAX_PER_SEED,
    SNOWBALL_MAX_TOTAL,
)
from thesisagents.gui.i18n import t
from thesisagents.gui.widgets.responsive import adapt_form_rows


@dataclass(frozen=True)
class SnowballBounds:
    """The snowball bounds the Search page passes to ``snowball()``.

    The defaults are the CLI's (``--snowball-seeds`` 5, depth 1, 20 per seed,
    20 new papers in all, no relevance floor), so a user who never opens the
    *Advanced* section gets the same expansion as before. ``min_relevance``
    of ``None`` keeps every paper found.

    Example: ``SnowballBounds(seeds=10, max_total=50)``.
    """

    seeds: int = DEFAULT_SNOWBALL_SEEDS
    depth: int = SNOWBALL_DEFAULT_DEPTH
    max_per_seed: int = SNOWBALL_DEFAULT_MAX_PER_SEED
    max_total: int = DEFAULT_SNOWBALL_MAX_TOTAL
    min_relevance: float | None = None


class SnowballBoundsForm(QWidget):
    """The bounds as spin boxes. The defaults are the CLI's."""

    def __init__(self, language: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        defaults = SnowballBounds()
        self._seeds = self._bounded_spin(MAX_RESULTS_PER_SOURCE, defaults.seeds)
        self._depth = self._bounded_spin(SNOWBALL_MAX_DEPTH, defaults.depth)
        self._per_seed = self._bounded_spin(SNOWBALL_MAX_PER_SEED, defaults.max_per_seed)
        self._total = self._bounded_spin(SNOWBALL_MAX_TOTAL, defaults.max_total)
        self._floor = QDoubleSpinBox(self)
        self._floor.setRange(0.0, 1.0)
        self._floor.setSingleStep(0.05)
        self._floor.setDecimals(2)
        # 0 shows as a dash and means "no floor", the CLI's omitted flag.
        self._floor.setSpecialValueText("—")
        form.addRow(t("search.snowball_seeds", language), self._seeds)
        form.addRow(t("search.snowball_depth", language), self._depth)
        form.addRow(t("search.snowball_max_per_seed", language), self._per_seed)
        form.addRow(t("search.snowball_max_total", language), self._total)
        form.addRow(t("search.snowball_min_relevance", language), self._floor)
        adapt_form_rows(self, form)

    def _bounded_spin(self, upper: int, value: int) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(1, upper)
        spin.setValue(value)
        return spin

    def bounds(self) -> SnowballBounds:
        floor = self._floor.value()
        return SnowballBounds(
            seeds=self._seeds.value(),
            depth=self._depth.value(),
            max_per_seed=self._per_seed.value(),
            max_total=self._total.value(),
            min_relevance=floor if floor > 0 else None,
        )

    def set_bounds(self, bounds: SnowballBounds) -> None:
        self._seeds.setValue(bounds.seeds)
        self._depth.setValue(bounds.depth)
        self._per_seed.setValue(bounds.max_per_seed)
        self._total.setValue(bounds.max_total)
        self._floor.setValue(bounds.min_relevance or 0.0)

"""Published clinical calculators (deterministic formulas, no training).

Each calculator module (models/renal/egfr.py, models/hepatic/fib4.py)
defines a Calculator whose formula, coefficients, units and cutoffs are taken
ONLY from the cited original publication, and whose interpretation uses only
thresholds from that publication or from this project's cited corpus.

models/tool.py runs calculators through the same interface as the cardiac
risk model: missing inputs -> "needs_values", invalid inputs -> "invalid",
never a guessed value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

CALC_DISCLAIMER = ("Calculated with a published equation; an estimate that supports, "
                   "and does not replace, clinical judgment. Not a diagnosis.")


@dataclass(frozen=True)
class CalcInput:
    key: str
    label: str
    kind: str                       # "numeric" | "categorical"
    unit: str | None = None
    choices: tuple[str, ...] = ()
    minimum: float | None = None    # lower bound for numeric inputs
    min_exclusive: bool = True      # True: value must be > minimum; False: >= minimum
    min_reason: str = ""            # shown when the bound is violated


@dataclass(frozen=True)
class Interpretation:
    band: str                       # short label, e.g. "below 60"
    text: str                       # sentence quoting the cited threshold
    source: str                     # where the threshold comes from


@dataclass(frozen=True)
class Calculator:
    organ: str
    title: str
    measure: str                    # what the number is, e.g. "eGFR (CKD-EPI 2021, creatinine)"
    unit: str
    decimals: int                   # value is rounded to this; bands use the rounded value
    inputs: tuple[CalcInput, ...]
    formula: str                    # human-readable formula, as published
    citation: str
    doi: str
    compute: Callable[[dict], float]                # validated inputs -> unrounded value
    interpret: Callable[[float], Interpretation]    # rounded value -> band
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def keys(self) -> list[str]:
        return [i.key for i in self.inputs]

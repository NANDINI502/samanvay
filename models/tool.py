"""Risk tools used by specialist agents: one trained model and two published
calculators, behind one interface.

    estimate("cardiac", {...}) -> RiskResult   # UCI Cleveland model (kind "model")
    estimate("renal",   {...}) -> RiskResult   # eGFR, CKD-EPI 2021 (kind "calculator")
    estimate("hepatic", {...}) -> RiskResult   # FIB-4, Sterling 2006 (kind "calculator")

Rules enforced here, in code, for every tool:
  - Every input must be provided. Missing inputs -> status "needs_values"
    with the list of what to ask for; no result.
  - Values must be valid. Model: numeric within the range seen in training
    (no extrapolation), categories from the documented choices. Calculator:
    numeric above the published/physical lower bound, categories from the
    choices. Otherwise -> status "invalid"; no result.
  - Every result carries a disclaimer and the source citation.

Model explanation: for each input, the estimate is recomputed with that input
set to the training-set median (numeric) or most common value (categorical).
The change in estimated risk is that input's contribution; the three largest
are reported. Calculators are explained by their published formula instead.

The renal (UCI CKD) and hepatic (ILPD) trained models were retired to
experiments/negative_results/ — see the README there.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

from models.calculator import CALC_DISCLAIMER, Calculator
from models.common import DISCLAIMER, SHARED_KEYS
from models.hepatic.fib4 import CALCULATOR as FIB4
from models.renal.egfr import CALCULATOR as EGFR

MODELS_DIR = Path(__file__).resolve().parent
TRAINED_MODELS = ["cardiac"]
CALCULATORS: dict[str, Calculator] = {"renal": EGFR, "hepatic": FIB4}
RISK_ORGANS = TRAINED_MODELS + list(CALCULATORS)


@dataclass
class RiskResult:
    organ: str
    status: str                      # "ok" | "needs_values" | "invalid"
    title: str
    kind: str = "model"              # "model" | "calculator"
    disclaimer: str = DISCLAIMER
    missing: list[dict] = field(default_factory=list)   # [{key, label, unit}]
    problems: list[str] = field(default_factory=list)
    citation: str = ""
    # kind == "model"
    probability: float | None = None
    target: str = ""
    population: str = ""
    model_name: str = ""
    top_factors: list[dict] = field(default_factory=list)
    validation: dict = field(default_factory=dict)
    # kind == "calculator"
    value: float | None = None
    unit: str = ""
    decimals: int = 0
    measure: str = ""
    band: str = ""
    interpretation: str = ""
    interpretation_source: str = ""
    formula: str = ""
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """One plain-text block, safe to show as-is or pass to the agent model."""
        name = f"{self.title} {'calculator' if self.kind == 'calculator' else 'risk model'}"
        if self.status == "needs_values":
            asks = ", ".join(f"{m['label']}" + (f" ({m['unit']})" if m.get("unit") else "") for m in self.missing)
            return f"{name}: no result yet. Please provide: {asks}."
        if self.status == "invalid":
            return f"{name}: no result. " + " ".join(self.problems)
        if self.kind == "calculator":
            unit = f" {self.unit}" if self.unit else ""
            return (
                f"{name}: {self.measure} = {self.value:.{self.decimals}f}{unit}. {self.interpretation} "
                f"(Threshold source: {self.interpretation_source}.) {' '.join(self.caveats)} "
                f"Source: {self.citation} {self.disclaimer}"
            )
        factors = "; ".join(
            f"{f['label']} = {f['value']} ({'+' if f['effect'] >= 0 else '-'}{abs(f['effect']) * 100:.0f} pts)"
            for f in self.top_factors)
        v = self.validation
        return (
            f"{name}: estimated probability of {self.target}: {self.probability * 100:.0f}%. "
            f"Largest contributions vs a typical patient in the dataset: {factors}. "
            f"Validation (cross-validated, {v.get('n_samples')} patients): AUC {v.get('cv_auc_mean', 0):.2f}, "
            f"sensitivity {v.get('sensitivity', 0):.2f}, specificity {v.get('specificity', 0):.2f} at 50%. "
            f"Population: {self.population}. {self.disclaimer}"
        )


@lru_cache(maxsize=None)
def load_bundle(organ: str) -> dict:
    if organ not in TRAINED_MODELS:
        raise ValueError(f"'{organ}' has no trained model (calculators: {list(CALCULATORS)})")
    path = MODELS_DIR / organ / "model.joblib"
    if not path.exists():
        raise FileNotFoundError(f"No trained risk model for '{organ}'. Run: python -m models.{organ}.train")
    return joblib.load(path)


def has_risk_model(organ: str) -> bool:
    if organ in CALCULATORS:
        return True
    return organ in TRAINED_MODELS and (MODELS_DIR / organ / "model.joblib").exists()


def tool_info(organ: str) -> dict:
    """Description of the tool for the UI/API: what it is and where it comes from."""
    if organ in CALCULATORS:
        c = CALCULATORS[organ]
        return {"kind": "calculator", "title": c.title, "formula": c.formula,
                "citation": f"{c.citation} {c.doi}", "caveats": list(c.caveats), "disclaimer": CALC_DISCLAIMER}
    spec = load_bundle(organ)["spec"]
    return {"kind": "model", "title": spec["title"], "population": spec["population"], "dataset": spec["dataset"],
            "citation": f"{spec['citation']} {spec['doi']} ({spec['license']})", "disclaimer": DISCLAIMER}


def required_inputs(organ: str) -> list[dict]:
    """Input schema for the UI/CLI: key, label, kind, unit, and choices
    (categorical), or range (model: training range) / min (calculator)."""
    out = []
    if organ in CALCULATORS:
        for i in CALCULATORS[organ].inputs:
            item = {"key": i.key, "label": i.label, "kind": i.kind, "unit": i.unit}
            if i.kind == "categorical":
                item["choices"] = list(i.choices)
            else:
                item["min"] = i.minimum
                item["min_exclusive"] = i.min_exclusive
                item["max"] = i.maximum
            out.append(item)
        return out
    b = load_bundle(organ)
    for f in b["spec"]["features"]:
        item = {"key": f["key"], "label": f["label"], "kind": f["kind"], "unit": f["unit"]}
        if f["kind"] == "categorical":
            item["choices"] = list(f["choices"])
        else:
            item["range"] = b["ranges"][f["key"]]
        out.append(item)
    return out


def _input_keys(organ: str) -> set[str]:
    if organ in CALCULATORS:
        return set(CALCULATORS[organ].keys)
    return {f["key"] for f in load_bundle(organ)["spec"]["features"]}


def is_requested(organ: str, values: dict | None) -> bool:
    """The user asked for this tool if they gave at least one of its
    tool-specific inputs (age/sex alone are shared and don't count)."""
    if not values:
        return False
    return any(_present(values.get(k)) for k in _input_keys(organ) - SHARED_KEYS)


def _present(v) -> bool:
    return v is not None and not (isinstance(v, str) and v.strip() == "")


def _parse(f: dict, raw, ranges: dict) -> tuple[object, str | None]:
    if f["kind"] == "categorical":
        key = str(raw).strip().lower()
        if key not in f["choices"]:
            return None, f"{f['label']}: '{raw}' is not one of {', '.join(f['choices'])}."
        return f["choices"][key], None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None, f"{f['label']}: '{raw}' is not a number."
    if f.get("cap") is not None and x > f["cap"]:
        x = f["cap"]
    lo, hi = ranges[f["key"]]
    if not lo <= x <= hi:
        return None, (f"{f['label']}: {raw} is outside the range seen in the training data "
                      f"({lo:g}-{hi:g}); the model won't extrapolate.")
    return x, None


def _parse_calc_input(i, raw) -> tuple[object, str | None]:
    if i.kind == "categorical":
        key = str(raw).strip().lower()
        if key not in i.choices:
            return None, f"{i.label}: '{raw}' is not one of {', '.join(i.choices)}."
        return key, None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None, f"{i.label}: '{raw}' is not a number."
    if x != x or x in (float("inf"), float("-inf")):
        return None, f"{i.label}: '{raw}' is not a finite number."
    if i.minimum is not None and (x <= i.minimum if i.min_exclusive else x < i.minimum):
        op = ">" if i.min_exclusive else ">="
        return None, f"{i.label}: {raw} is not valid; must be {op} {i.minimum:g} ({i.min_reason})."
    if i.maximum is not None and x > i.maximum:
        if i.max_message:
            return None, f"{i.label}: {raw}. {i.max_message}"
        return None, f"{i.label}: {raw} is not valid; must be <= {i.maximum:g} ({i.max_reason})."
    return x, None


def _calculate(organ: str, values: dict) -> RiskResult:
    c = CALCULATORS[organ]
    base = dict(organ=organ, kind="calculator", title=c.title, disclaimer=CALC_DISCLAIMER,
                citation=f"{c.citation} {c.doi}", unit=c.unit, decimals=c.decimals, measure=c.measure, formula=c.formula,
                caveats=list(c.caveats))
    missing = [{"key": i.key, "label": i.label, "unit": i.unit} for i in c.inputs if not _present(values.get(i.key))]
    if missing:
        return RiskResult(status="needs_values", missing=missing, **base)
    parsed, problems = {}, []
    for i in c.inputs:
        v, err = _parse_calc_input(i, values[i.key])
        if err:
            problems.append(err)
        parsed[i.key] = v
    if problems:
        return RiskResult(status="invalid", problems=problems, **base)
    value = round(c.compute(parsed), c.decimals)
    band = c.interpret(value)
    return RiskResult(status="ok", value=value, band=band.band, interpretation=band.text,
                      interpretation_source=band.source, **base)


def estimate(organ: str, values: dict) -> RiskResult:
    if organ in CALCULATORS:
        return _calculate(organ, values)
    b = load_bundle(organ)
    spec = b["spec"]
    base = dict(organ=organ, title=spec["title"], target=spec["target"], population=spec["population"],
                model_name=b["model_name"], validation=b["metrics"],
                citation=f"{spec['citation']} {spec['doi']} ({spec['license']})")

    missing = [{"key": f["key"], "label": f["label"], "unit": f["unit"]}
               for f in spec["features"] if not _present(values.get(f["key"]))]
    if missing:
        return RiskResult(status="needs_values", missing=missing, **base)

    row, problems = {}, []
    for f in spec["features"]:
        parsed, err = _parse(f, values[f["key"]], b["ranges"])
        if err:
            problems.append(err)
        row[f["key"]] = parsed
    if problems:
        return RiskResult(status="invalid", problems=problems, **base)

    pipe = b["pipeline"]
    X = pd.DataFrame([row], columns=[f["key"] for f in spec["features"]])
    p = float(pipe.predict_proba(X)[0, 1])

    factors = []
    for f in spec["features"]:
        ref = b["reference"][f["key"]]
        if row[f["key"]] == ref:
            continue
        X_ref = X.copy()
        X_ref[f["key"]] = ref
        effect = p - float(pipe.predict_proba(X_ref)[0, 1])
        factors.append({"key": f["key"], "label": f["label"], "value": values[f["key"]], "effect": round(effect, 4)})
    factors.sort(key=lambda d: abs(d["effect"]), reverse=True)

    return RiskResult(status="ok", probability=round(p, 4), top_factors=factors[:3], **base)

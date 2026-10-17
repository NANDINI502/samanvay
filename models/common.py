"""Shared training, evaluation and persistence for the trained risk models.

The shipped model is models/cardiac/train.py. The renal (UCI CKD) and hepatic
(ILPD) models are kept as negative results in experiments/negative_results/
and use the same code. Each train.py defines a RiskModelSpec and a loader for
its UCI dataset, then calls train_and_save(). Everything here is deterministic for a
given seed, so retraining reproduces the saved model exactly.

Model selection: two simple, explainable candidates (logistic regression and
a shallow gradient-boosted tree) with fixed, untuned hyperparameters — the
datasets are too small to tune and validate honestly on the same data.
Whichever has the higher mean AUC over 5x5 repeated stratified CV is kept
(ties go to logistic regression).

Missing values: imputed inside the CV pipeline (median for numeric, most
frequent for categorical), fitted on training folds only, so no information
leaks from validation folds. Imputation is only used for TRAINING rows. At
prediction time the tool (models/tool.py) refuses to estimate unless every
input is provided — it never fills in a patient's values.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# The only shipped trained model is cardiac (UCI Cleveland: donated to UCI July 1988, collected 1981-84).
DISCLAIMER = "Model estimate from a small 1988 research dataset (Cleveland Clinic, collected 1981-84), not a diagnosis."
SHARED_KEYS = {"age", "sex"}  # inputs several risk models use; never count as a request for one model


@dataclass
class FeatureSpec:
    key: str                 # input name used by the tool, CLI and UI
    label: str
    kind: str                # "numeric" | "categorical"
    unit: str | None = None
    choices: dict[str, object] | None = None  # user value -> value as coded in the dataset
    cap: float | None = None  # values above this are recorded as `cap` in the dataset (e.g. ILPD age 89+ -> 90)


@dataclass
class RiskModelSpec:
    organ: str
    title: str
    target: str              # what a positive label means in this dataset
    population: str         # who the data came from — the model only describes this population
    dataset: str
    citation: str
    doi: str
    license: str
    features: list[FeatureSpec] = field(default_factory=list)

    @property
    def keys(self) -> list[str]:
        return [f.key for f in self.features]


def _candidates(seed: int) -> dict[str, object]:
    return {
        "logistic_regression": LogisticRegression(max_iter=5000, C=1.0),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=2, learning_rate=0.05, random_state=seed),
    }


def _pipeline(spec: RiskModelSpec, estimator) -> Pipeline:
    numeric = [f.key for f in spec.features if f.kind == "numeric"]
    categorical = [f.key for f in spec.features if f.kind == "categorical"]
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")),
                          ("scale", StandardScaler())]), numeric),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    return Pipeline([("pre", pre), ("model", estimator)])


def _threshold_metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    pred = p >= threshold
    tp = int(np.sum(pred & (y == 1))); fn = int(np.sum(~pred & (y == 1)))
    tn = int(np.sum(~pred & (y == 0))); fp = int(np.sum(pred & (y == 0)))
    return {
        "threshold": threshold,
        "sensitivity": tp / (tp + fn) if tp + fn else None,
        "specificity": tn / (tn + fp) if tn + fp else None,
        "ppv": tp / (tp + fp) if tp + fp else None,
        "npv": tn / (tn + fn) if tn + fn else None,
        "confusion": {"tp": tp, "fn": fn, "tn": tn, "fp": fp},
    }


def _calibration(y: np.ndarray, p: np.ndarray, bins: int = 5) -> dict:
    """Calibration of out-of-fold predictions: slope/intercept of a logistic
    recalibration (ideal 1 / 0), calibration-in-the-large, and quantile bins."""
    eps = 1e-6
    logit = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps))).reshape(-1, 1)
    recal = LogisticRegression(C=np.inf, max_iter=5000).fit(logit, y)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, len(edges) - 2)
    table = []
    for b in range(len(edges) - 1):
        m = idx == b
        if m.any():
            table.append({"mean_predicted": float(p[m].mean()), "observed_rate": float(y[m].mean()), "n": int(m.sum())})
    return {
        "slope": float(recal.coef_[0][0]),
        "intercept": float(recal.intercept_[0]),
        "mean_predicted_minus_observed": float(p.mean() - y.mean()),
        "brier": float(brier_score_loss(y, p)),
        "bins": table,
    }


def evaluate(spec: RiskModelSpec, X: pd.DataFrame, y: np.ndarray, seed: int = 0) -> dict:
    repeated = RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=seed)
    single = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    out = {}
    for name, est in _candidates(seed).items():
        pipe = _pipeline(spec, est)
        aucs = cross_val_score(pipe, X, y, cv=repeated, scoring="roc_auc")
        oof = cross_val_predict(pipe, X, y, cv=single, method="predict_proba")[:, 1]
        out[name] = {
            "cv_auc_mean": float(aucs.mean()),
            "cv_auc_sd": float(aucs.std()),
            "oof_auc": float(roc_auc_score(y, oof)),
            **_threshold_metrics(y, oof),
            "calibration": _calibration(y, oof),
        }
    return out


def train(spec: RiskModelSpec, X: pd.DataFrame, y: np.ndarray, seed: int = 0) -> tuple[dict, dict]:
    """Returns (bundle, metrics). The bundle is self-contained: the tool needs
    nothing but it to validate inputs, predict and explain."""
    X = X[spec.keys]
    candidates = evaluate(spec, X, y, seed)
    chosen = max(candidates, key=lambda n: (candidates[n]["cv_auc_mean"], n == "logistic_regression"))
    pipe = clone(_pipeline(spec, _candidates(seed)[chosen])).fit(X, y)

    numeric = [f.key for f in spec.features if f.kind == "numeric"]
    ranges = {k: [float(X[k].min()), float(X[k].max())] for k in numeric}
    reference = {k: float(X[k].median()) for k in numeric}
    reference.update({f.key: X[f.key].mode().iloc[0] for f in spec.features if f.kind == "categorical"})

    metrics = {
        "organ": spec.organ,
        "dataset": spec.dataset,
        "n_samples": int(len(y)),
        "n_positive": int(y.sum()),
        "prevalence": float(y.mean()),
        "missing_values_per_feature": {k: int(X[k].isna().sum()) for k in spec.keys if X[k].isna().any()},
        "validation": "5x5 repeated stratified CV for AUC; one seeded 5-fold stratified split for out-of-fold sensitivity/specificity/calibration",
        "seed": seed,
        "chosen_model": chosen,
        "selection_rule": "highest mean CV AUC; ties go to logistic regression",
        "candidates": candidates,
        "sklearn_version": sklearn.__version__,
    }
    bundle = {
        "spec": asdict(spec),
        "pipeline": pipe,
        "model_name": chosen,
        "ranges": ranges,
        "reference": reference,
        "metrics": {"cv_auc_mean": candidates[chosen]["cv_auc_mean"],
                    "sensitivity": candidates[chosen]["sensitivity"],
                    "specificity": candidates[chosen]["specificity"],
                    "n_samples": int(len(y)), "prevalence": float(y.mean())},
        "sklearn_version": sklearn.__version__,
    }
    return bundle, metrics


def train_and_save(spec: RiskModelSpec, X: pd.DataFrame, y: np.ndarray, out_dir: Path, seed: int = 0,
                   save_model: bool = True) -> dict:
    bundle, metrics = train(spec, X, y, seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    if save_model:
        joblib.dump(bundle, out_dir / "model.joblib")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str) + "\n", encoding="utf-8")
    c = metrics["candidates"][metrics["chosen_model"]]
    print(f"[{spec.organ}] n={metrics['n_samples']} prevalence={metrics['prevalence']:.2f} chosen={metrics['chosen_model']}")
    for name, m in metrics["candidates"].items():
        print(f"    {name:20s} CV AUC {m['cv_auc_mean']:.3f} +/- {m['cv_auc_sd']:.3f} | "
              f"sens {m['sensitivity']:.2f} spec {m['specificity']:.2f} | "
              f"calib slope {m['calibration']['slope']:.2f} brier {m['calibration']['brier']:.3f}")
    return metrics


def row_to_values(spec: RiskModelSpec, row: pd.Series) -> dict:
    """Convert one dataset row back into tool inputs (used by tests, which run
    on real dataset rows only — never on invented patients)."""
    values = {}
    for f in spec.features:
        v = row[f.key]
        if f.kind == "categorical":
            values[f.key] = next(k for k, code in f.choices.items() if code == v)
        else:
            values[f.key] = float(v)
    return values

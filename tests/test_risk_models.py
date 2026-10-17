"""Trained risk model (cardiac, UCI Cleveland): training reproducibility and
the tool interface. Calculators are tested in test_calculators.py; the
retired renal/hepatic models in test_negative_results.py.

All patient inputs here are real rows from the UCI dataset (via the
train.py loader) — no invented patients."""
import json
from importlib import import_module

import joblib
import numpy as np
import pytest

from agents.specialist import SpecialistAgent
from models.common import DISCLAIMER, row_to_values, train
from models.tool import MODELS_DIR, TRAINED_MODELS, estimate, required_inputs
from orchestrator.router import handle_query


def _module(organ):
    return import_module(f"models.{organ}.train")


def _real_values(organ, i=0):
    m = _module(organ)
    X, y = m.load()
    complete = X.dropna()
    return row_to_values(m.SPEC, complete.iloc[i])


@pytest.mark.parametrize("organ", TRAINED_MODELS)
def test_training_reproduces_saved_model_and_metrics(organ):
    m = _module(organ)
    X, y = m.load()
    bundle, metrics = train(m.SPEC, X, y)
    saved = joblib.load(MODELS_DIR / organ / "model.joblib")
    saved_metrics = json.loads((MODELS_DIR / organ / "metrics.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(metrics, default=str)) == saved_metrics
    Xc = X[m.SPEC.keys]
    np.testing.assert_allclose(bundle["pipeline"].predict_proba(Xc), saved["pipeline"].predict_proba(Xc), rtol=0, atol=1e-12)


@pytest.mark.parametrize("organ", TRAINED_MODELS)
def test_metrics_report_required_fields(organ):
    metrics = json.loads((MODELS_DIR / organ / "metrics.json").read_text(encoding="utf-8"))
    chosen = metrics["candidates"][metrics["chosen_model"]]
    assert set(metrics["candidates"]) == {"logistic_regression", "gradient_boosting"}
    for key in ("cv_auc_mean", "sensitivity", "specificity"):
        assert 0 <= chosen[key] <= 1
    assert {"slope", "intercept", "brier", "bins"} <= set(chosen["calibration"])
    assert chosen["cv_auc_mean"] == max(c["cv_auc_mean"] for c in metrics["candidates"].values())


@pytest.mark.parametrize("organ", TRAINED_MODELS)
def test_complete_real_row_gives_estimate_with_disclaimer(organ):
    r = estimate(organ, _real_values(organ))
    assert r.status == "ok"
    assert 0 <= r.probability <= 1
    assert 1 <= len(r.top_factors) <= 3
    assert r.disclaimer == DISCLAIMER
    assert "small 1988 research dataset" in DISCLAIMER and "not a diagnosis" in DISCLAIMER
    assert DISCLAIMER in r.summary()
    assert "doi.org" in r.citation


@pytest.mark.parametrize("organ", TRAINED_MODELS)
def test_missing_values_ask_instead_of_guessing(organ):
    values = _real_values(organ)
    dropped = [k for k in values if k not in {"age", "sex"}][:2]
    for k in dropped:
        del values[k]
    r = estimate(organ, values)
    assert r.status == "needs_values" and r.probability is None
    assert [m["key"] for m in r.missing] == dropped
    assert "Please provide" in r.summary()


def test_out_of_range_value_is_refused_not_extrapolated():
    values = _real_values("cardiac")
    hi = next(f for f in required_inputs("cardiac") if f["key"] == "cholesterol")["range"][1]
    r = estimate("cardiac", dict(values, cholesterol=hi * 2))
    assert r.status == "invalid" and r.probability is None
    assert "won't extrapolate" in r.problems[0]


def test_unknown_category_is_refused():
    r = estimate("cardiac", dict(_real_values("cardiac"), sex="unknown"))
    assert r.status == "invalid" and r.probability is None


def test_agent_runs_tool_after_guardrails():
    a = SpecialistAgent("cardiac").run("What is this patient's cardiovascular risk?",
                                       patient_values=_real_values("cardiac"))
    assert not a.deferred and a.risk["status"] == "ok"
    assert a.answer.startswith("[MOCK")  # the model reply is a stub; the estimate is real and separate


def test_agent_without_values_does_not_run_tool():
    a = SpecialistAgent("cardiac").run("What is this patient's cardiovascular risk?")
    assert a.risk is None


def test_red_flag_blocks_risk_tool():
    r = handle_query("Chest pain now, what is the heart risk?", patient_values=_real_values("cardiac"))
    assert r.routing_method == "red_flag" and r.agent_answers == {}


def test_final_answer_carries_estimate_and_disclaimer():
    r = handle_query("What is this patient's cardiovascular risk?", patient_values=_real_values("cardiac"))
    assert r.agent_answers["cardiac"].risk["status"] == "ok"
    assert DISCLAIMER in r.final_answer


def test_final_answer_asks_for_missing_values():
    values = _real_values("cardiac")
    del values["cholesterol"]
    r = handle_query("What is this patient's cardiovascular risk?", patient_values=values)
    assert r.agent_answers["cardiac"].risk["status"] == "needs_values"
    assert "Please provide: Serum cholesterol" in r.final_answer


def test_values_for_unrouted_organ_are_ignored():
    r = handle_query("What GFR value suggests kidney disease?", patient_values=_real_values("cardiac"))
    assert r.agents_consulted == ["renal"]
    assert r.agent_answers["renal"].risk is None

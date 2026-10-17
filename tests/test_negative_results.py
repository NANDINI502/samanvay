"""Retired risk models kept as documented negative results
(experiments/negative_results/). Re-running each training script must
reproduce the saved metrics exactly, so the numbers quoted in the READMEs
stay verifiable. No model file is shipped for either."""
import json
from importlib import import_module
from pathlib import Path

import pytest

from models.common import train
from models.tool import RISK_ORGANS, TRAINED_MODELS

NEG = Path(__file__).resolve().parents[1] / "experiments" / "negative_results"
CASES = ["renal_uci_ckd", "hepatic_ilpd"]


@pytest.mark.parametrize("name", CASES)
def test_negative_result_metrics_reproduce(name):
    m = import_module(f"experiments.negative_results.{name}.train")
    X, y = m.load()
    _, metrics = train(m.SPEC, X, y)
    saved = json.loads((NEG / name / "metrics.json").read_text(encoding="utf-8"))
    assert json.loads(json.dumps(metrics, default=str)) == saved
    assert not (NEG / name / "model.joblib").exists()


def test_quoted_failure_numbers():
    ckd = json.loads((NEG / "renal_uci_ckd" / "metrics.json").read_text(encoding="utf-8"))
    assert ckd["candidates"][ckd["chosen_model"]]["cv_auc_mean"] == 1.0
    ilpd = json.loads((NEG / "hepatic_ilpd" / "metrics.json").read_text(encoding="utf-8"))
    chosen = ilpd["candidates"][ilpd["chosen_model"]]
    assert round(chosen["specificity"], 2) == 0.22 and round(ilpd["prevalence"], 2) == 0.71


def test_retired_models_are_not_served():
    assert TRAINED_MODELS == ["cardiac"]
    assert set(RISK_ORGANS) == {"cardiac", "renal", "hepatic"}  # renal/hepatic are calculators now
    assert not (Path(__file__).resolve().parents[1] / "models" / "renal" / "model.joblib").exists()
    assert not (Path(__file__).resolve().parents[1] / "models" / "hepatic" / "model.joblib").exists()

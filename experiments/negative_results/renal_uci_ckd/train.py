"""Renal risk model: UCI Chronic Kidney Disease (Rubini et al., 2015).

    python -m experiments.negative_results.renal_uci_ckd.train   (writes metrics.json only)

Target: the dataset's own `class` label (ckd vs notckd).

Parsing (the ARFF file has known formatting faults, fixed here, nothing else):
  - stray whitespace/tabs around values ("\\tno", "ckd\\t") are stripped
  - 3 of 400 rows have 26 fields: two end in a trailing comma, one has an
    empty field between `htn` and `dm`. Empty fields are dropped, which
    restores 25 fields that match the header in all three rows.
  - '?' means missing.

Feature selection rule (fixed in advance, not tuned on outcome): keep every
attribute with <= 15% missing values. That excludes red/pus cell microscopy,
sodium, potassium, packed cell volume and blood cell counts (22-38% missing),
so the tool asks for 17 routinely recorded values instead of 24.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from models.common import FeatureSpec, RiskModelSpec, train_and_save

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "uci" / "chronic_kidney_disease" / "chronic_kidney_disease_full.arff"
OUT = Path(__file__).resolve().parent

ARFF_COLUMNS = ["age", "bp", "sg", "al", "su", "rbc", "pc", "pcc", "ba", "bgr", "bu", "sc", "sod", "pot",
                "hemo", "pcv", "wbcc", "rbcc", "htn", "dm", "cad", "appet", "pe", "ane", "class"]
MAX_MISSING_FRACTION = 0.15

YES_NO = {"yes": "yes", "no": "no"}

ALL_FEATURES = {
    "age": FeatureSpec("age", "Age", "numeric", "years"),
    "bp": FeatureSpec("blood_pressure", "Blood pressure (as recorded in the dataset)", "numeric", "mm Hg"),
    "sg": FeatureSpec("urine_specific_gravity", "Urine specific gravity (1.005-1.025)", "numeric"),
    "al": FeatureSpec("urine_albumin", "Urine albumin (dipstick scale 0-5)", "numeric", "0-5"),
    "su": FeatureSpec("urine_sugar", "Urine sugar (dipstick scale 0-5)", "numeric", "0-5"),
    "pcc": FeatureSpec("pus_cell_clumps", "Pus cell clumps (urine)", "categorical",
                       choices={"present": "present", "notpresent": "notpresent"}),
    "ba": FeatureSpec("bacteria", "Bacteria (urine)", "categorical",
                      choices={"present": "present", "notpresent": "notpresent"}),
    "bgr": FeatureSpec("blood_glucose_random", "Random blood glucose", "numeric", "mg/dl"),
    "bu": FeatureSpec("blood_urea", "Blood urea", "numeric", "mg/dl"),
    "sc": FeatureSpec("serum_creatinine", "Serum creatinine", "numeric", "mg/dl"),
    "sod": FeatureSpec("sodium", "Sodium", "numeric", "mEq/L"),
    "pot": FeatureSpec("potassium", "Potassium", "numeric", "mEq/L"),
    "hemo": FeatureSpec("hemoglobin", "Hemoglobin", "numeric", "g/dl"),
    "pcv": FeatureSpec("packed_cell_volume", "Packed cell volume", "numeric"),
    "wbcc": FeatureSpec("white_cell_count", "White blood cell count", "numeric", "cells/cumm"),
    "rbcc": FeatureSpec("red_cell_count", "Red blood cell count", "numeric", "millions/cmm"),
    "rbc": FeatureSpec("urine_red_cells", "Red blood cells (urine)", "categorical",
                       choices={"normal": "normal", "abnormal": "abnormal"}),
    "pc": FeatureSpec("pus_cells", "Pus cells (urine)", "categorical",
                      choices={"normal": "normal", "abnormal": "abnormal"}),
    "htn": FeatureSpec("hypertension", "Hypertension", "categorical", choices=YES_NO),
    "dm": FeatureSpec("diabetes", "Diabetes mellitus", "categorical", choices=YES_NO),
    "cad": FeatureSpec("coronary_artery_disease", "Coronary artery disease", "categorical", choices=YES_NO),
    "appet": FeatureSpec("appetite", "Appetite", "categorical", choices={"good": "good", "poor": "poor"}),
    "pe": FeatureSpec("pedal_edema", "Pedal edema", "categorical", choices=YES_NO),
    "ane": FeatureSpec("anemia", "Anemia", "categorical", choices=YES_NO),
}


def _parse_arff() -> pd.DataFrame:
    rows = []
    in_data = False
    for line in DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("%"):
            continue
        if line.lower() == "@data":
            in_data = True
            continue
        if not in_data:
            continue
        fields = [f.strip() for f in line.split(",")]
        if len(fields) != len(ARFF_COLUMNS):
            fields = [f for f in fields if f != ""]
        if len(fields) != len(ARFF_COLUMNS):
            raise ValueError(f"Unparseable CKD row: {line!r}")
        rows.append([None if f == "?" else f for f in fields])
    df = pd.DataFrame(rows, columns=ARFF_COLUMNS)
    for col, f in ALL_FEATURES.items():
        if f.kind == "numeric":
            df[col] = pd.to_numeric(df[col])
    return df


def _select_features(df: pd.DataFrame) -> list[str]:
    return [c for c in ARFF_COLUMNS[:-1] if df[c].isna().mean() <= MAX_MISSING_FRACTION]


_RAW = _parse_arff()
SELECTED = _select_features(_RAW)

SPEC = RiskModelSpec(
    organ="renal",
    title="Chronic kidney disease (dataset label)",
    target="chronic kidney disease as labelled in the UCI dataset ('ckd' vs 'notckd')",
    population="400 patients from Apollo Hospitals, Karaikudi, Tamil Nadu, India (2015); 250 labelled CKD",
    dataset="UCI Chronic Kidney Disease",
    citation="Rubini, L., Soundarapandian, P., & Eswaran, P. (2015). Chronic Kidney Disease [Dataset]. UCI Machine Learning Repository.",
    doi="https://doi.org/10.24432/C5G020",
    license="CC BY 4.0",
    features=[ALL_FEATURES[c] for c in SELECTED],
)


def load() -> tuple[pd.DataFrame, np.ndarray]:
    df = _RAW.copy()
    y = (df["class"] == "ckd").astype(int).to_numpy()
    X = df[SELECTED].rename(columns={c: ALL_FEATURES[c].key for c in SELECTED})
    for f in SPEC.features:
        if f.kind == "categorical":
            X[f.key] = X[f.key].astype(object).where(X[f.key].notna(), np.nan)
    return X, y


def main() -> None:
    X, y = load()
    train_and_save(SPEC, X, y, OUT, save_model=False)  # negative result: no model shipped


if __name__ == "__main__":
    main()

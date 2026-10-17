"""Hepatic risk model: UCI ILPD (Indian Liver Patient Dataset).

    python -m experiments.negative_results.hepatic_ilpd.train   (writes metrics.json only)

Target: the `Selector` column. UCI does not state its encoding; the file has
416 rows with 1 and 167 with 2, matching UCI's "416 patients diagnosed with
liver disease and 167 patients without", so 1 = liver patient.

Missing: UCI lists the dataset as having no missing values, but 4 rows have
an empty A/G ratio — imputed for training only (see models/common.py).
Age: UCI records any age over 89 as 90; the tool applies the same cap.
Units are not stated by UCI; inputs must use the units of the original data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from models.common import FeatureSpec, RiskModelSpec, train_and_save

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "uci" / "ilpd" / "ilpd.csv"
OUT = Path(__file__).resolve().parent

SPEC = RiskModelSpec(
    organ="hepatic",
    title="Liver patient (dataset label)",
    target="'liver patient' as labelled in ILPD (Selector = 1)",
    population="583 patients from north-east Andhra Pradesh, India; 416 labelled liver patients, 441 male",
    dataset="UCI ILPD (Indian Liver Patient Dataset)",
    citation="Ramana, B. & Venkateswarlu, N. (2022). ILPD (Indian Liver Patient Dataset) [Dataset]. UCI Machine Learning Repository.",
    doi="https://doi.org/10.24432/C5D02C",
    license="CC BY 4.0",
    features=[
        FeatureSpec("age", "Age", "numeric", "years", cap=90.0),
        FeatureSpec("sex", "Sex", "categorical", choices={"male": "Male", "female": "Female"}),
        FeatureSpec("total_bilirubin", "Total bilirubin", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("direct_bilirubin", "Direct bilirubin", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("alkaline_phosphatase", "Alkaline phosphatase", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("alt", "ALT (SGPT)", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("ast", "AST (SGOT)", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("total_protein", "Total protein", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("serum_albumin", "Serum albumin", "numeric", "units as in ILPD (not stated by UCI)"),
        FeatureSpec("ag_ratio", "Albumin/globulin ratio", "numeric"),
    ],
)

COLUMNS = ["age", "sex", "total_bilirubin", "direct_bilirubin", "alkaline_phosphatase", "alt", "ast",
           "total_protein", "serum_albumin", "ag_ratio", "selector"]


def load() -> tuple[pd.DataFrame, np.ndarray]:
    df = pd.read_csv(DATA, header=None, names=COLUMNS)
    y = (df.pop("selector") == 1).astype(int).to_numpy()
    df["sex"] = df["sex"].astype(object)
    return df, y


def main() -> None:
    X, y = load()
    train_and_save(SPEC, X, y, OUT, save_model=False)  # negative result: no model shipped


if __name__ == "__main__":
    main()

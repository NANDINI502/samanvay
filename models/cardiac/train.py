"""Cardiac risk model: UCI Heart Disease, Cleveland subset (processed, 14 attributes).

    python -m models.cardiac.train

Target: angiographic coronary artery disease — UCI attribute `num` > 0
(> 50% diameter narrowing in any major vessel). Codes and missing-value
marker ('?') are as documented in data/uci/heart_disease/heart-disease.names.
Missing: 4 rows lack `ca`, 2 lack `thal` — imputed for training only (see
models/common.py).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from models.common import FeatureSpec, RiskModelSpec, train_and_save

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "uci" / "heart_disease" / "processed.cleveland.data"
OUT = Path(__file__).resolve().parent

YES_NO = {"yes": 1.0, "no": 0.0}

SPEC = RiskModelSpec(
    organ="cardiac",
    title="Coronary artery disease on angiography",
    target="angiographic coronary artery disease (>50% diameter narrowing in any major vessel; UCI 'num' > 0)",
    population="303 patients referred for coronary angiography at the Cleveland Clinic Foundation (data collected 1981-1984)",
    dataset="UCI Heart Disease (Cleveland subset)",
    citation="Janosi, A., Steinbrunn, W., Pfisterer, M., & Detrano, R. (1989). Heart Disease [Dataset]. UCI Machine Learning Repository.",
    doi="https://doi.org/10.24432/C52P4X",
    license="CC BY 4.0",
    features=[
        FeatureSpec("age", "Age", "numeric", "years"),
        FeatureSpec("sex", "Sex", "categorical", choices={"male": 1.0, "female": 0.0}),
        FeatureSpec("chest_pain_type", "Chest pain type", "categorical", choices={
            "typical_angina": 1.0, "atypical_angina": 2.0, "non_anginal_pain": 3.0, "asymptomatic": 4.0}),
        FeatureSpec("resting_bp", "Resting blood pressure (on admission)", "numeric", "mm Hg"),
        FeatureSpec("cholesterol", "Serum cholesterol", "numeric", "mg/dl"),
        FeatureSpec("fasting_blood_sugar_over_120", "Fasting blood sugar > 120 mg/dl", "categorical", choices=YES_NO),
        FeatureSpec("resting_ecg", "Resting ECG", "categorical", choices={
            "normal": 0.0, "st_t_abnormality": 1.0, "lv_hypertrophy": 2.0}),
        FeatureSpec("max_heart_rate", "Maximum heart rate achieved (exercise test)", "numeric", "bpm"),
        FeatureSpec("exercise_angina", "Exercise-induced angina", "categorical", choices=YES_NO),
        FeatureSpec("st_depression", "ST depression induced by exercise relative to rest", "numeric", "mm"),
        FeatureSpec("st_slope", "Slope of peak exercise ST segment", "categorical", choices={
            "upsloping": 1.0, "flat": 2.0, "downsloping": 3.0}),
        FeatureSpec("major_vessels", "Major vessels coloured by fluoroscopy (0-3)", "numeric", "count"),
        FeatureSpec("thal", "Thallium scan", "categorical", choices={
            "normal": 3.0, "fixed_defect": 6.0, "reversible_defect": 7.0}),
    ],
)

COLUMNS = ["age", "sex", "chest_pain_type", "resting_bp", "cholesterol", "fasting_blood_sugar_over_120",
           "resting_ecg", "max_heart_rate", "exercise_angina", "st_depression", "st_slope",
           "major_vessels", "thal", "num"]


def load() -> tuple[pd.DataFrame, np.ndarray]:
    df = pd.read_csv(DATA, header=None, names=COLUMNS, na_values="?")
    y = (df.pop("num") > 0).astype(int).to_numpy()
    return df, y


def main() -> None:
    X, y = load()
    train_and_save(SPEC, X, y, OUT)


if __name__ == "__main__":
    main()

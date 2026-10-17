# Datasets

Risk tools in this project:

| Agent | Tool | Basis |
| --- | --- | --- |
| Cardiac | Trained model (`models/cardiac/`) | UCI Heart Disease (Cleveland) — below |
| Renal | eGFR calculator (`models/renal/egfr.py`) | Published equation: Inker LA, et al. N Engl J Med 2021;385:1737-1749, Table 2 — https://doi.org/10.1056/NEJMoa2102953. No dataset. |
| Hepatic | FIB-4 calculator (`models/hepatic/fib4.py`) | Published formula: Sterling RK, et al. Hepatology 2006;43(6):1317-1325 — https://doi.org/10.1002/hep.21178. No dataset. |

The UCI CKD and ILPD datasets below were used for renal and hepatic models
that were **retired as negative results** (see
`experiments/negative_results/README.md`); the app does not use them.

All three UCI datasets are public, from the UCI Machine Learning Repository. Each was downloaded from
its official UCI page on 2026-10-13; licence and citation were checked on
that page before use. No patient data in this project is generated or
invented — tests use real rows from these files.

Raw files are kept unmodified in `data/uci/`. Any cleaning happens in code
(`models/cardiac/train.py` and `experiments/negative_results/*/train.py`) and is described below.

## UCI Heart Disease (Cleveland subset) — Cardiac agent

| | |
| --- | --- |
| Page | https://archive.ics.uci.edu/dataset/45/heart+disease |
| Download | https://archive.ics.uci.edu/static/public/45/heart+disease.zip (SHA-256 `b17cd273da9ce1caa4710fce80227ea454d4dbf9fcbc8e6a9121672751563adc`) |
| Licence | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Citation | Janosi, A., Steinbrunn, W., Pfisterer, M., & Detrano, R. (1989). Heart Disease [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C52P4X |
| Files used | `processed.cleveland.data` (SHA-256 `a74b7efa…427c8`), `heart-disease.names` (attribute codes) |

The dataset's `heart-disease.names` asks that publications name the principal
investigators: Andras Janosi, M.D. (Hungarian Institute of Cardiology,
Budapest); William Steinbrunn, M.D. (University Hospital, Zurich); Matthias
Pfisterer, M.D. (University Hospital, Basel); Robert Detrano, M.D., Ph.D.
(V.A. Medical Center, Long Beach and Cleveland Clinic Foundation).

- **Which file:** UCI's `WARNING` file says the raw `cleveland.data` is
  corrupted and `processed.cleveland.data` is the usable one (14 attributes).
- **Population:** 303 patients referred for coronary angiography at the
  Cleveland Clinic. Not a general or primary-care population.
- **Target:** `num` > 0, i.e. > 50% diameter narrowing in any major vessel
  on angiography (`num` is 0–4 in the file). 139 of 303 positive.
- **Missing values:** `?` in the file: 4 rows lack `ca` (major vessels), 2
  lack `thal`. Imputed for training only (median / most frequent, inside
  each CV fold).
- **Known quirk:** in this referral population, *asymptomatic* chest-pain
  type is the strongest positive predictor and *typical angina* lowers the
  estimate. That is a property of who was referred for angiography, not a
  clinical rule — the tool reports it as-is.

## UCI Chronic Kidney Disease — retired renal model (negative result)

| | |
| --- | --- |
| Page | https://archive.ics.uci.edu/dataset/336/chronic+kidney+disease |
| Download | https://archive.ics.uci.edu/static/public/336/chronic+kidney+disease.zip (SHA-256 `3f0d0e5bab0f453165acfa2c77eae695393089c5b338cb4cd98339c96a26a585`) |
| Licence | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Citation | Rubini, L., Soundarapandian, P., & Eswaran, P. (2015). Chronic Kidney Disease [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5G020 |
| Files used | `chronic_kidney_disease_full.arff` (SHA-256 `a5ea9636…5797`), `chronic_kidney_disease.info.txt`, extracted from the `.rar` inside the zip |

- **Population:** 400 patients, Apollo Hospitals, Karaikudi, Tamil Nadu,
  India (2015); 250 labelled CKD, 150 not.
- **Target:** the dataset's `class` label (`ckd` / `notckd`). How the label
  was assigned is not documented.
- **Parsing fixes (format only):** stray tabs/spaces around values stripped
  (e.g. `ckd\t`, `\tno`); 3 rows have 26 fields — two end in a trailing
  comma, one has an empty field between `htn` and `dm`. Dropping the empty
  field restores 25 fields matching the header in all three.
- **Feature selection rule (fixed before training):** keep attributes with
  ≤ 15% missing values → 17 of 24. Dropped: urine red cells and pus cells,
  sodium, potassium, packed cell volume, white and red cell counts (22–38%
  missing).
- **Missing values:** in 9–52 rows per kept feature (see
  `experiments/negative_results/renal_uci_ckd/metrics.json`); imputed for
  training only.
- **Units:** as listed by UCI. `bp` is "blood pressure (mm/Hg)" — UCI does
  not say systolic or diastolic.
- **Warning:** the dataset is almost perfectly separable (CV AUC 1.00). That
  most likely reflects how the label relates to the inputs (creatinine,
  urea, haemoglobin, urine albumin), not real-world accuracy. Do not read
  the validation numbers as how the model would perform elsewhere.

## UCI ILPD (Indian Liver Patient Dataset) — retired hepatic model (negative result)

| | |
| --- | --- |
| Page | https://archive.ics.uci.edu/dataset/225/ilpd+indian+liver+patient+dataset |
| Download | https://archive.ics.uci.edu/static/public/225/ilpd+indian+liver+patient+dataset.zip (SHA-256 `60e18fbfe7f84daf58c178ea280ba5fe8db7e2507aabce01b57425b3b822cf0b`) |
| Licence | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| Citation | Ramana, B. & Venkateswarlu, N. (2022). ILPD (Indian Liver Patient Dataset) [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5D02C |
| File used | `Indian Liver Patient Dataset (ILPD).csv`, stored as `data/uci/ilpd/ilpd.csv` (SHA-256 `84feac16…3425`) |

- **Population:** 583 patients from north-east Andhra Pradesh, India; 441
  male, 142 female.
- **Target:** `Selector`. UCI does not state its encoding; the file has 416
  rows with `1` and 167 with `2`, matching UCI's "416 patients diagnosed with
  liver disease and 167 patients without", so `1` = liver patient.
- **Missing values:** UCI lists none, but 4 rows have an empty A/G ratio.
  Imputed for training only.
- **Age:** UCI records ages over 89 as 90; the tool applies the same cap.
- **Units:** not stated by UCI for any lab value. Inputs must be in the
  units of the original data.
- **Warning:** 71% of the dataset is positive, so the model rarely predicts
  low risk: specificity at a 50% threshold is only 0.22.

## Attribution in the app

Every cardiac model result carries the dataset citation and DOI, and the text
"Model estimate from a small 1988 research dataset (Cleveland Clinic,
collected 1981-84), not a diagnosis." (The data was collected 1981-84 and
donated to UCI in July 1988, per `heart-disease.names`.)

Every calculator result carries its publication citation and DOI, the
source of its interpretation thresholds, the population caveat from the
publication, and "Calculated with a published equation; an estimate that
supports, and does not replace, clinical judgment. Not a diagnosis."

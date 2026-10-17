# Negative results: retired risk models

Two trained risk models were built for the Renal and Hepatic agents and then
**retired** because their validation results showed they should not be used.
They are kept here, with their training code and metrics, so the results can
be checked and reproduced. No model file is shipped for either, and the app
does not load them.

They were replaced by published, deterministic calculators:

| Agent | Retired model | Replacement |
| --- | --- | --- |
| Renal | UCI Chronic Kidney Disease classifier | eGFR, 2021 CKD-EPI creatinine equation without race (Inker et al., NEJM 2021) — `models/renal/egfr.py` |
| Hepatic | UCI ILPD classifier | FIB-4 (Sterling et al., Hepatology 2006) — `models/hepatic/fib4.py` |

Reproduce (writes `metrics.json` only; `tests/test_negative_results.py`
checks that the saved metrics are reproduced exactly):

    python -m experiments.negative_results.renal_uci_ckd.train
    python -m experiments.negative_results.hepatic_ilpd.train

Both use the shared pipeline in `models/common.py`: logistic regression vs a
shallow gradient-boosted tree, fixed hyperparameters, 5x5 repeated
stratified CV for AUC, and one seeded 5-fold split for out-of-fold
sensitivity, specificity and calibration. Dataset details are in
`DATASETS.md`.

## Renal — UCI Chronic Kidney Disease: AUC 1.00 (suspected label leakage)

Source: Rubini, Soundarapandian & Eswaran (2015), UCI, https://doi.org/10.24432/C5G020 (CC BY 4.0).
400 patients, 250 labelled CKD (62.5%). 17 features kept (≤ 15% missing).

| Candidate | CV AUC (mean ± SD) | Sensitivity | Specificity | Calibration slope |
| --- | --- | --- | --- | --- |
| Logistic regression (chosen) | 1.000 ± 0.000 | 0.988 | 1.000 | 16.39 |
| Gradient boosting | 0.9998 ± 0.0006 | 0.992 | 1.000 | 2.52 |

**Why retired.** A cross-validated AUC of 1.00 on 400 routine-care patients
is not a credible measure of real-world performance. UCI does not document
how the `ckd` / `notckd` label was assigned. The inputs include the values
that kidney disease is usually defined from: serum creatinine, blood urea,
haemoglobin and urine albumin. So the label is most likely derived from the
model's own inputs (label leakage), and the model learns that definition
back rather than predicting anything. The calibration slope of 16.4 (ideal
1.0) shows the out-of-fold probabilities are pushed to almost exactly 0 or 1.
The validation numbers do not say how the model would perform on new
patients, so we can't honestly present its output as a risk estimate.

## Hepatic — UCI ILPD: specificity 0.22 at a 71% base rate

Source: Ramana & Venkateswarlu (2022), UCI, https://doi.org/10.24432/C5D02C (CC BY 4.0).
583 patients, 416 labelled liver patients (71.4%). 10 features.

| Candidate | CV AUC (mean ± SD) | Sensitivity | Specificity | PPV | NPV |
| --- | --- | --- | --- | --- | --- |
| Logistic regression (chosen) | 0.745 ± 0.043 | 0.923 | 0.222 | 0.747 | 0.536 |
| Gradient boosting | 0.726 ± 0.040 | 0.901 | 0.240 | 0.747 | 0.494 |

Out-of-fold confusion matrix for the chosen model at a 50% threshold:
TP 384, FN 32, TN 37, FP 130.

**Why retired.** 71% of the dataset is positive, so the model almost always
predicts "liver patient". It correctly identified only 37 of the 167
non-patients (specificity 0.22). Its PPV of 0.75 is barely above the 0.71
base rate, so a positive result adds little. UCI states no units for any lab
value, so users can't reliably enter comparable inputs. The labels come from
a selected hospital population and say nothing about which liver condition
is present.

## What this changed

- Renal and Hepatic now use published equations with cited coefficients,
  interpreted only with cited thresholds. No trained model sits behind them.
- The cardiac model (UCI Cleveland, CV AUC 0.91) is the only trained model
  still shipped. It is labelled "Model estimate from a small 1988 research
  dataset (Cleveland Clinic, collected 1981-84), not a diagnosis."

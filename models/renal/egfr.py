"""eGFR calculator: 2021 CKD-EPI creatinine equation, without race.

Source (equation and every coefficient): Inker LA, Eneanya ND, Coresh J, et
al. New Creatinine- and Cystatin C-Based Equations to Estimate GFR without
Race. N Engl J Med 2021;385:1737-1749. https://doi.org/10.1056/NEJMoa2102953
Table 2 (p. 1741), row "2021 CKD-EPI creatinine ... eGFRcr(AS), new":

    eGFR = 142 x min(Scr/k, 1)^a1 x max(Scr/k, 1)^-1.200 x 0.9938^Age x 1.012 [if female]
    k  = 0.7 (female), 0.9 (male)
    a1 = -0.241 (female), -0.302 (male)
    Scr in mg/dL; eGFR in mL/min/1.73 m^2. No race coefficient.

Interpretation uses ONLY the GFR thresholds in rag/corpus/renal_sources.md
(NIDDK): >= 60 normal range; < 60 may mean kidney disease; <= 15 is called
kidney failure. No CKD staging — the corpus does not cover it.

Input sanity checks (not clinical thresholds; the paper gives no ranges,
only means +- SD). Out-of-bounds values are refused, never converted:
  - Age 18-120. 18: "All the participants were 18 years of age or older"
    (Inker 2021, Methods). 120: no source; an upper limit on a plausible age.
  - Serum creatinine above 20 mg/dL is refused as probably µmol/L. Why 20:
    creatinine in the paper's data sets was 1.66 +- 1.16, 1.57 +- 0.93 and
    1.16 +- 0.70 mg/dL (Table 1), so 20 mg/dL is over 15 SD above every
    mean, while a µmol/L value read as mg/dL is 88.4 times too high (Table 1
    footnote: "To convert the values for serum creatinine to micromoles per
    liter, multiply by 88.4."). A true value above 20 mg/dL would be in the
    eGFR <= 15 band anyway: by this equation any creatinine above 5.4 mg/dL
    gives eGFR <= 15 at every adult age and either sex (crossover at age 18:
    4.19 female, 5.34 male). Not caught: a µmol/L value of 20 or less
    (under 0.23 mg/dL).
"""
from __future__ import annotations

from models.calculator import CalcInput, Calculator, Interpretation

# Table 2, Inker et al. 2021
MU = 142
KAPPA = {"female": 0.7, "male": 0.9}
A1 = {"female": -0.241, "male": -0.302}
A2 = -1.200
AGE_COEF = 0.9938
FEMALE_COEF = 1.012

# Input sanity checks, see the module docstring
MAX_AGE = 120
MAX_CREATININE_MG_DL = 20
UMOL_PER_MG_DL = 88.4  # Inker et al. 2021, Table 1 footnote
UMOL_MESSAGE = f"This looks like µmol/L. Enter mg/dL (µmol/L ÷ {UMOL_PER_MG_DL:g})."

NIDDK = "NIDDK, Chronic Kidney Disease Tests & Diagnosis (rag/corpus/renal_sources.md)"


def egfr_cr_2021(scr_mg_dl: float, age: float, sex: str) -> float:
    ratio = scr_mg_dl / KAPPA[sex]
    value = MU * min(ratio, 1) ** A1[sex] * max(ratio, 1) ** A2 * AGE_COEF ** age
    return value * FEMALE_COEF if sex == "female" else value


def interpret(egfr: float) -> Interpretation:
    if egfr <= 15:
        return Interpretation("15 or less", "A GFR of 15 or less is called kidney failure.", NIDDK)
    if egfr < 60:
        return Interpretation("below 60", "A GFR of less than 60 may mean kidney disease.", NIDDK)
    return Interpretation("60 or more", "A GFR of 60 or more is in the normal range.", NIDDK)


CALCULATOR = Calculator(
    organ="renal",
    title="eGFR (CKD-EPI 2021, creatinine, race-free)",
    measure="estimated GFR",
    unit="mL/min/1.73 m²",
    decimals=1,
    inputs=(
        CalcInput("age", "Age", "numeric", "years", minimum=18, min_exclusive=False,
                  min_reason="the equation was developed in adults",
                  maximum=MAX_AGE, max_reason="input sanity check: not a plausible age"),
        CalcInput("sex", "Sex", "categorical", choices=("female", "male")),
        CalcInput("serum_creatinine", "Serum creatinine", "numeric", "mg/dL", minimum=0,
                  min_reason="creatinine must be a positive value",
                  maximum=MAX_CREATININE_MG_DL, max_message=UMOL_MESSAGE),
    ),
    formula=("eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^−1.200 × 0.9938^Age × 1.012 [if female]; "
             "κ = 0.7 (F) / 0.9 (M); α = −0.241 (F) / −0.302 (M); Scr in mg/dL"),
    citation=("Inker LA, et al. New Creatinine- and Cystatin C-Based Equations to Estimate GFR "
              "without Race. N Engl J Med 2021;385:1737-1749 (Table 2)."),
    doi="https://doi.org/10.1056/NEJMoa2102953",
    compute=lambda v: egfr_cr_2021(v["serum_creatinine"], v["age"], v["sex"]),
    interpret=interpret,
    caveats=(
        "The equation was developed in ambulatory adult populations without serious coexisting "
        "conditions and may not apply to patients in acute care settings (Inker et al. 2021).",
    ),
)

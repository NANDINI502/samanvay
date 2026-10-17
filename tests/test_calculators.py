"""Published calculators: eGFR (CKD-EPI 2021 creatinine, race-free) and FIB-4.

Neither source publication contains worked numeric examples (Inker et al.
2021 has none; the Sterling et al. 2006 abstract has none, and the full text
was not available). So each expected value below is COMPUTED BY HAND FROM
THE PUBLISHED FORMULA: the branch (Scr <= k or Scr > k) and the sex-specific
coefficients are resolved by hand from Inker Table 2 and written out as a
literal expression, independently of models/renal/egfr.py. FIB-4 cases are
chosen so the published formula gives an exact number.

The input values are arithmetic test inputs, not patient records.
"""
import math
from pathlib import Path

import pytest

from models.calculator import CALC_DISCLAIMER
from models.hepatic import fib4
from models.renal import egfr
from models.tool import estimate, is_requested, required_inputs
from orchestrator.router import handle_query

# ---------- eGFR: Inker et al. NEJM 2021, Table 2 ----------

EGFR_CASES = [
    # (sex, age, Scr mg/dL, hand-resolved Table 2 expression)           # ≈ value
    ("male", 50, 0.9, 142 * 1 ** -0.302 * 1 ** -1.200 * 0.9938 ** 50),            # 104.05 (Scr = k)
    ("female", 50, 0.7, 142 * 1 ** -0.241 * 1 ** -1.200 * 0.9938 ** 50 * 1.012),  # 105.30 (Scr = k)
    ("male", 60, 1.8, 142 * (1.8 / 0.9) ** -1.200 * 0.9938 ** 60),                # 42.56 (Scr > k)
    ("female", 40, 0.5, 142 * (0.5 / 0.7) ** -0.241 * 0.9938 ** 40 * 1.012),      # 121.52 (Scr < k)
    ("male", 30, 0.6, 142 * (0.6 / 0.9) ** -0.302 * 0.9938 ** 30),                # 133.18 (Scr < k)
    ("female", 70, 2.1, 142 * (2.1 / 0.7) ** -1.200 * 0.9938 ** 70 * 1.012),      # 24.88 (Scr > k)
]


@pytest.mark.parametrize("sex,age,scr,expected", EGFR_CASES)
def test_egfr_matches_hand_computed_table2_value(sex, age, scr, expected):
    assert egfr.egfr_cr_2021(scr, age, sex) == pytest.approx(expected, rel=1e-12)


def test_egfr_hand_values_rounded():
    # Rounded results of the cases above, for a reader checking by calculator.
    got = [round(egfr.egfr_cr_2021(scr, age, sex), 1) for sex, age, scr, _ in EGFR_CASES]
    assert got == [104.0, 105.3, 42.6, 121.5, 133.2, 24.9]


def test_egfr_coefficients_are_table2_values():
    assert (egfr.MU, egfr.A2, egfr.AGE_COEF, egfr.FEMALE_COEF) == (142, -1.200, 0.9938, 1.012)
    assert egfr.KAPPA == {"female": 0.7, "male": 0.9}
    assert egfr.A1 == {"female": -0.241, "male": -0.302}


@pytest.mark.parametrize("sex", ["female", "male"])
def test_egfr_continuous_at_kappa(sex):
    k = egfr.KAPPA[sex]
    assert egfr.egfr_cr_2021(k - 1e-9, 55, sex) == pytest.approx(egfr.egfr_cr_2021(k + 1e-9, 55, sex), rel=1e-6)


def test_egfr_falls_as_creatinine_rises():
    values = [egfr.egfr_cr_2021(s, 60, "female") for s in (0.4, 0.7, 1.0, 2.0, 5.0)]
    assert values == sorted(values, reverse=True)


@pytest.mark.parametrize("value,band", [
    (104.0, "60 or more"), (60.0, "60 or more"), (59.9, "below 60"),
    (15.1, "below 60"), (15.0, "15 or less"), (5.0, "15 or less"),
])
def test_egfr_bands_use_only_niddk_corpus_thresholds(value, band):
    assert egfr.interpret(value).band == band


def test_egfr_interpretation_text_is_in_renal_corpus():
    corpus = (Path(__file__).resolve().parents[1] / "rag" / "corpus" / "renal_sources.md").read_text(encoding="utf-8")
    assert "GFR of 60 or more is in the normal range" in corpus
    assert "GFR of less than 60 may mean kidney disease" in corpus
    assert "GFR of 15 or less is called kidney failure" in corpus


def test_egfr_tool_result():
    r = estimate("renal", {"age": 60, "sex": "male", "serum_creatinine": 1.8})
    assert r.status == "ok" and r.kind == "calculator"
    assert r.value == 42.6 and r.band == "below 60"
    assert r.disclaimer == CALC_DISCLAIMER and "not a diagnosis" in r.disclaimer.lower()
    s = r.summary()
    assert "42.6 mL/min/1.73 m²" in s and "10.1056/NEJMoa2102953" in s and "acute care" in s


def test_egfr_accepts_numeric_strings_and_case():
    r = estimate("renal", {"age": "50", "sex": "Male", "serum_creatinine": "0.9"})
    assert r.status == "ok" and r.value == 104.0


@pytest.mark.parametrize("values,fragment", [
    ({"age": 17, "sex": "male", "serum_creatinine": 0.9}, "developed in adults"),
    ({"age": 50, "sex": "male", "serum_creatinine": 0}, "positive"),
    ({"age": 50, "sex": "male", "serum_creatinine": -1}, "positive"),
    ({"age": 50, "sex": "unknown", "serum_creatinine": 0.9}, "not one of"),
    ({"age": 50, "sex": "male", "serum_creatinine": "abc"}, "not a number"),
    ({"age": 50, "sex": "male", "serum_creatinine": "nan"}, "not a finite number"),
])
def test_egfr_invalid_inputs_refused(values, fragment):
    r = estimate("renal", values)
    assert r.status == "invalid" and r.value is None
    assert any(fragment in p for p in r.problems)


def test_egfr_missing_inputs_asked_for():
    r = estimate("renal", {"serum_creatinine": 1.1})
    assert r.status == "needs_values" and r.value is None
    assert [m["key"] for m in r.missing] == ["age", "sex"]
    assert "Please provide: Age (years), Sex" in r.summary()


# ---------- FIB-4: Sterling et al. Hepatology 2006 ----------

FIB4_CASES = [
    # (age, AST, ALT, PLT, expected) — (age x AST) / (PLT x sqrt(ALT)), exact by hand
    (50, 40, 25, 200, 2.0),     # 2000 / (200 x 5)
    (60, 100, 16, 100, 15.0),   # 6000 / (100 x 4)
    (30, 20, 36, 250, 0.4),     # 600 / (250 x 6)
    (29, 25, 25, 100, 1.45),    # 725 / (100 x 5)  — exactly the low cutoff
    (65, 25, 25, 100, 3.25),    # 1625 / (100 x 5) — exactly the high cutoff
]


@pytest.mark.parametrize("age,ast,alt,plt,expected", FIB4_CASES)
def test_fib4_matches_hand_computed_value(age, ast, alt, plt, expected):
    assert fib4.fib4(age, ast, alt, plt) == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("score,band", [
    (0.4, "below 1.45"), (1.44, "below 1.45"), (1.45, "1.45-3.25"),
    (2.0, "1.45-3.25"), (3.25, "1.45-3.25"), (3.26, "above 3.25"), (15.0, "above 3.25"),
])
def test_fib4_bands_follow_sterling_cutoffs(score, band):
    # Sterling: "<1.45" and ">3.25"; values from 1.45 to 3.25 inclusive are between the cutoffs.
    assert fib4.interpret(score).band == band


def test_fib4_band_texts_quote_sterling_figures():
    assert "90% negative predictive value" in fib4.interpret(1.0).text and "70% sensitivity" in fib4.interpret(1.0).text
    assert "65% positive predictive value" in fib4.interpret(4.0).text and "97% specificity" in fib4.interpret(4.0).text


@pytest.mark.parametrize("age,ast,alt,plt,expected", FIB4_CASES)
def test_fib4_tool_bands_exact_cutoffs(age, ast, alt, plt, expected):
    r = estimate("hepatic", {"age": age, "ast": ast, "alt": alt, "platelets": plt})
    assert r.status == "ok" and r.value == expected
    assert r.band == fib4.interpret(expected).band


def test_fib4_tool_result_has_source_and_population_caveat():
    r = estimate("hepatic", {"age": 50, "ast": 40, "alt": 25, "platelets": 200})
    s = r.summary()
    assert "FIB-4 index = 2.00" in s and "10.1002/hep.21178" in s and "HIV/HCV" in s
    assert r.disclaimer == CALC_DISCLAIMER


@pytest.mark.parametrize("key", ["age", "ast", "alt", "platelets"])
def test_fib4_zero_inputs_refused(key):
    values = dict({"age": 50, "ast": 40, "alt": 25, "platelets": 200}, **{key: 0})
    r = estimate("hepatic", values)
    assert r.status == "invalid" and r.value is None


# ---------- through the agents and orchestrator ----------

def test_calculator_requested_only_by_its_specific_inputs():
    assert not is_requested("renal", {"age": 50, "sex": "male"})
    assert is_requested("renal", {"serum_creatinine": 1.0})
    assert not is_requested("hepatic", {"age": 50})
    assert is_requested("hepatic", {"ast": 40})


def test_schema_fields_for_calculators():
    assert [f["key"] for f in required_inputs("renal")] == ["age", "sex", "serum_creatinine"]
    assert [f["key"] for f in required_inputs("hepatic")] == ["age", "ast", "alt", "platelets"]


def test_egfr_reaches_final_answer():
    r = handle_query("What does this patient's eGFR mean?",
                     patient_values={"age": 60, "sex": "male", "serum_creatinine": 1.8})
    assert r.agent_answers["renal"].risk["status"] == "ok"
    assert "42.6 mL/min/1.73 m²" in r.final_answer and CALC_DISCLAIMER in r.final_answer


def test_fib4_reaches_final_answer():
    r = handle_query("What does this patient's FIB-4 liver score suggest?",
                     patient_values={"age": 50, "ast": 40, "alt": 25, "platelets": 200})
    assert r.agent_answers["hepatic"].risk["status"] == "ok"
    assert "FIB-4 index = 2.00" in r.final_answer and CALC_DISCLAIMER in r.final_answer


def test_red_flag_blocks_calculator():
    r = handle_query("Vomiting blood and jaundice, what is the FIB-4?",
                     patient_values={"age": 50, "ast": 40, "alt": 25, "platelets": 200})
    assert r.deferred and all(a.risk is None for a in r.agent_answers.values())


def test_referral_term_blocks_calculator():
    r = handle_query("Patient with ascites, what is the FIB-4 for this liver?",
                     patient_values={"age": 50, "ast": 40, "alt": 25, "platelets": 200})
    assert r.deferred and r.agent_answers["hepatic"].defer_kind == "referral"
    assert r.agent_answers["hepatic"].risk is None
    assert "FIB-4 index" not in r.final_answer


def test_missing_creatinine_asked_for_in_final_answer():
    r = handle_query("What does this patient's eGFR mean?", patient_values={"age": 50, "sex": "male", "serum_creatinine": ""})
    assert r.agent_answers["renal"].risk is None  # no renal-specific input given -> tool not requested
    r = handle_query("What does this patient's eGFR mean?", patient_values={"age": 50, "serum_creatinine": 1.0})
    assert r.agent_answers["renal"].risk["status"] == "needs_values"
    assert "Please provide: Sex" in r.final_answer


def test_math_sanity_sqrt_used_for_alt():
    # ALT enters as its square root (Sterling: (ALT [U/L])^(1/2)); quadrupling ALT halves FIB-4.
    assert fib4.fib4(50, 40, 100, 200) == pytest.approx(fib4.fib4(50, 40, 25, 200) / 2)
    assert math.isclose(fib4.fib4(50, 40, 25, 200), 2.0)

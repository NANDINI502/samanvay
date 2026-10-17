"""FIB-4 calculator.

Source (formula, units, cutoffs and their performance): Sterling RK, Lissen
E, Clumeck N, et al. Development of a simple noninvasive index to predict
significant fibrosis in patients with HIV/HCV coinfection. Hepatology
2006;43(6):1317-1325. https://doi.org/10.1002/hep.21178 (PMID 16729309).
From the abstract:

    FIB-4 = (age [yr] x AST [U/L]) / (PLT [10^9/L] x sqrt(ALT [U/L]))
    Validation set: < 1.45 -> NPV 90%, sensitivity 70% to exclude advanced
    fibrosis (Ishak 4-6); > 3.25 -> PPV 65%, specificity 97%.

Derived in 832 biopsied patients with HIV/HCV coinfection. The hepatic corpus
has no lab-value interpretation, so the bands below quote only Sterling et al.
"""
from __future__ import annotations

import math

from models.calculator import CalcInput, Calculator, Interpretation

LOW_CUTOFF = 1.45
HIGH_CUTOFF = 3.25

STERLING = "Sterling et al., Hepatology 2006 (validation set)"


def fib4(age: float, ast: float, alt: float, platelets: float) -> float:
    return (age * ast) / (platelets * math.sqrt(alt))


def interpret(score: float) -> Interpretation:
    if score < LOW_CUTOFF:
        return Interpretation(
            "below 1.45",
            "Below the 1.45 cutoff. In the source study's validation set this cutoff had a 90% negative "
            "predictive value for excluding advanced fibrosis (Ishak stage 4-6), with 70% sensitivity.",
            STERLING)
    if score > HIGH_CUTOFF:
        return Interpretation(
            "above 3.25",
            "Above the 3.25 cutoff. In the source study's validation set this cutoff had a 65% positive "
            "predictive value and 97% specificity for advanced fibrosis (Ishak stage 4-6).",
            STERLING)
    return Interpretation(
        "1.45-3.25",
        "Between the 1.45 and 3.25 cutoffs. The source study used the two cutoffs to classify only "
        "values outside this range.",
        STERLING)


CALCULATOR = Calculator(
    organ="hepatic",
    title="FIB-4 (liver fibrosis index)",
    measure="FIB-4 index",
    unit="",
    decimals=2,
    inputs=(
        CalcInput("age", "Age", "numeric", "years", minimum=0, min_reason="age must be positive"),
        CalcInput("ast", "AST", "numeric", "U/L", minimum=0, min_reason="AST must be a positive value"),
        CalcInput("alt", "ALT", "numeric", "U/L", minimum=0, min_reason="ALT must be a positive value"),
        CalcInput("platelets", "Platelet count", "numeric", "10^9/L", minimum=0,
                  min_reason="platelet count must be a positive value"),
    ),
    formula="FIB-4 = (Age [yr] × AST [U/L]) / (Platelets [10^9/L] × √ALT [U/L])",
    citation=("Sterling RK, et al. Development of a simple noninvasive index to predict significant "
              "fibrosis in patients with HIV/HCV coinfection. Hepatology 2006;43(6):1317-1325."),
    doi="https://doi.org/10.1002/hep.21178",
    compute=lambda v: fib4(v["age"], v["ast"], v["alt"], v["platelets"]),
    interpret=interpret,
    caveats=(
        "FIB-4 and its cutoffs were derived in 832 biopsied patients with HIV/HCV coinfection; "
        "the source study does not establish performance in other populations.",
    ),
)

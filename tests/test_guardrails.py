from guardrails.checks import check_red_flags, find_keyword, run_guardrails
from rag.retrieve import retrieve


def test_word_boundaries_no_false_match():
    # "tia" must not fire inside "initial" / "potential"
    assert find_keyword("initial potential assessment", ["tia"]) is None
    assert find_keyword("history of TIA last year", ["tia"]) == "tia"


def test_red_flag_overrides_everything():
    q = "Patient with chest pain, what is their CVD risk band?"
    g = run_guardrails(q, retrieve("cardiac", q), ["angina"])
    assert not g.allowed and g.kind == "red_flag"


def test_organ_referral_term():
    q = "Patient has proteinuria, how often to test GFR?"
    g = run_guardrails(q, retrieve("renal", q), ["proteinuria"])
    assert not g.allowed and g.kind == "referral"


def test_low_confidence_defers():
    q = "how do I renew my passport"
    g = run_guardrails(q, retrieve("hepatic", q), [])
    assert not g.allowed and g.kind == "low_confidence"


def test_well_covered_query_allowed():
    q = "What GFR value suggests kidney disease?"
    assert run_guardrails(q, retrieve("renal", q), []).allowed


def test_red_flag_variants():
    for q in ["sudden facial droop and slurred speech", "she is vomiting blood", "he can't breathe"]:
        assert not check_red_flags(q).allowed, q

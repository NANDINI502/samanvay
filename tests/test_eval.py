"""The eval case file is well-formed, and the harness scores a known case
correctly. The full eval is `python -m eval.run`, not part of pytest."""
from agents.registry import ORGANS
from eval.run import load_cases, observe, score

DEFERRALS = {"red_flag", "referral", "none"}
TOOLS = {"egfr", "fib4", "cardiac", "none"}
STATUSES = {"ok", "needs_values", "invalid"}


def test_cases_are_well_formed():
    cases = load_cases()
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    for c in cases:
        assert c["query"].strip()
        assert set(c["expected_agents"]) <= set(ORGANS), c["id"]
        assert c["expected_deferral"] in DEFERRALS, c["id"]
        assert c["expected_tool"] in TOOLS, c["id"]
        assert c.get("expected_tool_status", "ok") in STATUSES, c["id"]
        if c["expected_deferral"] == "red_flag":
            assert c["expected_agents"] == [], c["id"]
        # no expected medical answers: behaviour fields only
        assert not {"expected_answer", "answer"} & set(c), c["id"]


def test_harness_scores_a_red_flag_case():
    case = next(c for c in load_cases() if c["id"] == "redflag-en-01")
    obs = observe(case)
    assert obs["deferral"] == "red_flag" and obs["agents"] == []
    assert all(score(case, obs).values())

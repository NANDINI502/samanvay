"""scripts/benchmark_tiers.py, offline: case selection, percentiles, and that
a run varies only the role under test and restores its model afterwards.
(The benchmark itself is live only; mock mode just exercises the plumbing.)"""
from orchestrator import client as llm
from scripts import benchmark_tiers as bt


def test_nearest_rank_percentiles():
    assert bt.pct([], 50) is None
    assert bt.pct([5], 95) == 5
    data = list(range(1, 21))  # 1..20
    assert bt.pct(data, 50) == 10 and bt.pct(data, 95) == 19 and bt.pct(data, 100) == 20


def test_role_cases():
    cases = bt.load_cases()
    router_cases = bt.role_cases("router", cases)
    assert router_cases and all(c["expected_deferral"] != "red_flag" for c in router_cases)
    safety_cases = bt.role_cases("safety", cases)
    assert {c["category"] for c in safety_cases if c["expected_deferral"] == "red_flag"} == {"red_flag_paraphrase"}
    assert all(c["category"] in bt.PIPELINE_CATEGORIES for c in bt.role_cases("agent", cases))
    assert not any(c["category"] == "web_fallback" for c in bt.role_cases("agent", cases))


def test_run_varies_one_role_and_restores_it():
    before = {a: getattr(llm, a) for a in bt.ROLE_ATTR.values()}
    out = bt.run(["router", "safety", "agent", "orchestrator"], ["nano"], limit=2)
    assert {a: getattr(llm, a) for a in bt.ROLE_ATTR.values()} == before
    agent = out["results"]["agent"]["nano"]
    assert agent["model"] == bt.TIERS["nano"] and agent["errors"] == 0
    assert agent["calls"] > 0  # the agent calls (mock) used the nano model ID
    assert out["results"]["safety"]["nano"]["unavailable"] == 0
    assert "| nano |" in bt.table(out)


def test_agent_calls_use_the_tier_under_test(monkeypatch):
    seen = []
    real = llm.chat

    def spy(messages, *, model, **kw):
        seen.append(model)
        return real(messages, model=model, **kw)
    monkeypatch.setattr(llm, "chat", spy)
    bt.run(["agent"], ["ultra"], limit=1)
    assert bt.TIERS["ultra"] in seen and llm.ORCHESTRATOR_MODEL in seen

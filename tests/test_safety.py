"""One-way safety check (orchestrator/safety.py): the model can add an
emergency deferral, never remove one, and any failure leaves the
deterministic result unchanged. Model replies are faked here."""
import pytest

from guardrails.checks import GLOBAL_RED_FLAGS
from orchestrator import router, safety
from orchestrator.client import ChatResult
from orchestrator.router import handle_query

COVERED = "What GFR value suggests kidney disease?"


def _fake(monkeypatch, reply=None, exc=None):
    seen = []

    def chat(messages, **kwargs):
        seen.append(kwargs)
        if exc:
            raise exc
        return ChatResult(text=reply, model="fake-nemotron", role="agent", latency_s=0.01,
                          usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})

    monkeypatch.setattr(safety, "mock_enabled", lambda: False)
    monkeypatch.setattr(safety, "chat_as_agent", chat)
    return seen


EMERGENCY = '{"emergency": true, "sign": "vomiting blood", "reason": "blood in vomit"}'
CLEAR = '{"emergency": false, "sign": "", "reason": "general question"}'


def test_emergency_adds_deferral_and_skips_synthesis(monkeypatch):
    seen = _fake(monkeypatch, EMERGENCY)
    r = handle_query("There is blood in her vomit since morning")
    assert r.deferred and r.routing_method == "safety_model"
    assert "(vomiting blood)" in r.final_answer and r.final_answer.startswith("Urgent")
    assert r.agent_answers == {}  # no ordinary answer next to the urgent one
    assert not any(c["step"] == "Synthesis" for c in r.calls)
    assert r.calls[0]["step"] == "Safety check"
    assert seen[0]["timeout"] == safety.TIMEOUT_S


def test_emergency_on_an_unroutable_query_still_defers(monkeypatch):
    _fake(monkeypatch, EMERGENCY)
    r = handle_query("how do I renew my passport")
    assert r.deferred and not r.needs_clarification and r.routing_method == "safety_model"


def test_clear_changes_nothing(monkeypatch):
    baseline = handle_query(COVERED)
    _fake(monkeypatch, CLEAR)
    r = handle_query(COVERED)
    assert (r.deferred, r.routing_method, r.agents_consulted) == (
        baseline.deferred, baseline.routing_method, baseline.agents_consulted)
    assert r.final_answer == baseline.final_answer
    assert r.safety["status"] == "clear"


def test_clear_cannot_remove_a_referral(monkeypatch):
    _fake(monkeypatch, CLEAR)
    r = handle_query("Patient with cirrhosis and ascites — what next?")
    assert r.deferred and r.agent_answers["hepatic"].defer_kind == "referral"


def test_keyword_red_flag_never_reaches_the_model(monkeypatch):
    seen = _fake(monkeypatch, CLEAR)
    r = handle_query("Patient has chest pain")
    assert r.deferred and r.routing_method == "red_flag" and seen == []


@pytest.mark.parametrize("reply,exc", [
    (None, TimeoutError("timed out")),
    (None, RuntimeError("HTTP 500")),
    ("I think this might be an emergency", None),           # not JSON
    ('{"emergency": "yes"}', None),                         # not a boolean
    ('{"sign": "chest pain"}', None),                       # missing field
])
def test_failure_falls_back_to_deterministic_result(monkeypatch, reply, exc):
    baseline = handle_query(COVERED)
    _fake(monkeypatch, reply, exc)
    r = handle_query(COVERED)
    assert r.safety["status"] == "unavailable"
    assert (r.deferred, r.final_answer) == (baseline.deferred, baseline.final_answer)


def test_failure_keeps_a_deterministic_deferral(monkeypatch):
    _fake(monkeypatch, exc=TimeoutError("timed out"))
    r = handle_query("Suspected TIA last week, what follow-up is needed?")
    assert r.deferred and r.agent_answers["neuro"].defer_kind == "referral"


def test_emergency_wins_over_an_agent_failure(monkeypatch):
    _fake(monkeypatch, EMERGENCY)

    def broken(*a, **k):
        raise RuntimeError("model down")
    monkeypatch.setattr(router.AGENTS["renal"], "run", broken)
    r = handle_query(COVERED)
    assert r.deferred and r.routing_method == "safety_model"


def test_agent_failure_still_raises_without_emergency(monkeypatch):
    _fake(monkeypatch, CLEAR)

    def broken(*a, **k):
        raise RuntimeError("model down")
    monkeypatch.setattr(router.AGENTS["renal"], "run", broken)
    with pytest.raises(RuntimeError):
        handle_query(COVERED)


def test_prompt_defines_emergency_by_the_existing_red_flags_only():
    for flag in GLOBAL_RED_FLAGS:
        assert flag in safety.SYSTEM_PROMPT


def test_skipped_in_mock_mode():
    assert safety.check(COVERED).status == "skipped"

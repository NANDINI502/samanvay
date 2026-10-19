"""Nemotron router (orchestrator/router.py): strict JSON validated against
the registry, keyword fallback on any failure, and the referral safety net
that consults every organ whose referral term appears. Model replies are
faked here."""
import pytest

from agents.registry import AGENT_CONFIGS
from orchestrator import router
from orchestrator.client import ChatResult
from orchestrator.router import handle_query, parse_route, referral_organs, route


def _fake_router(monkeypatch, reply=None, exc=None):
    seen = []

    def chat(messages, **kwargs):
        seen.append(kwargs)
        if exc:
            raise exc
        return ChatResult(text=reply, model="fake-nemotron-router", role="router", latency_s=0.01)

    monkeypatch.setattr(router, "mock_enabled", lambda: False)
    monkeypatch.setattr(router, "chat_as_router", chat)
    monkeypatch.setenv("MEDBOT_ROUTER", "nemotron")
    return seen


def test_parse_route_accepts_registry_names():
    assert parse_route('{"organs": ["renal", "cardiac", "renal"], "reason": "BP and kidneys"}') == (
        ["renal", "cardiac"], "BP and kidneys")
    assert parse_route('Sure: {"organs": [], "reason": "not clinical"}') == ([], "not clinical")


@pytest.mark.parametrize("reply", [
    "renal, cardiac",                                   # not JSON
    '{"organs": ["kidney"]}',                           # not a registry name
    '{"organs": "renal"}',                              # not a list
    '{"agents": ["renal"]}',                            # wrong field
    '{"organs": [1]}',
])
def test_parse_route_rejects_invalid(reply):
    with pytest.raises(ValueError):
        parse_route(reply)


def test_nemotron_route_used_with_reason(monkeypatch):
    seen = _fake_router(monkeypatch, '{"organs": ["cardiac", "renal"], "reason": "blood pressure and kidneys"}')
    organs, method, reason = route("Does high blood pressure affect the kidneys?")
    assert (organs, method, reason) == (["cardiac", "renal"], "nemotron", "blood pressure and kidneys")
    assert seen[0]["temperature"] == 0 and seen[0]["timeout"] == router.ROUTER_TIMEOUT_S


@pytest.mark.parametrize("reply,exc", [
    (None, TimeoutError("timed out")),
    ('{"organs": ["kidney"]}', None),
    ("no idea", None),
])
def test_invalid_or_failed_router_falls_back_to_keywords(monkeypatch, reply, exc):
    _fake_router(monkeypatch, reply, exc)
    organs, method, reason = route("What GFR value suggests kidney disease?")
    assert organs == ["renal"] and method == "keyword_fallback"
    assert "unavailable" in reason and "keyword match" in reason


def test_mock_mode_uses_keywords_and_says_so():
    organs, method, reason = route("What GFR value suggests kidney disease?")
    assert (organs, method) == (["renal"], "keyword") and "mock mode" in reason


def test_router_disabled_by_env(monkeypatch):
    seen = _fake_router(monkeypatch, '{"organs": ["hepatic"], "reason": "x"}')
    monkeypatch.setenv("MEDBOT_ROUTER", "keyword")
    assert route("What GFR value suggests kidney disease?")[:2] == (["renal"], "keyword")
    assert seen == []


def test_every_referral_term_reaches_its_organ():
    for organ, cfg in AGENT_CONFIGS.items():
        for term in cfg["referral_keywords"]:
            assert organ in referral_organs(f"patient with {term}"), (organ, term)


@pytest.mark.parametrize("query,organ", [
    ("Patient with suspected DKA, what next?", "endocrine"),         # 'dka' isn't a routing keyword
    ("Known varices on endoscopy, what follow-up?", "hepatic"),
    ("Possible transient ischemic attack yesterday", "neuro"),
])
def test_referral_net_catches_terms_keyword_routing_missed(query, organ):
    r = handle_query(query)
    assert organ in r.agents_consulted and r.deferred
    assert r.agent_answers[organ].defer_kind == "referral"


def test_router_cannot_drop_a_referral(monkeypatch):
    # the model picks only cardiac; neuro's referral rule must still run
    _fake_router(monkeypatch, '{"organs": ["cardiac"], "reason": "cholesterol follow-up"}')
    r = handle_query("Patient with known stroke history and high cholesterol, what CVD follow-up?")
    assert "neuro" in r.agents_consulted and r.deferred
    assert "added so their referral rule runs: neuro" in r.routing_reason


def test_empty_route_asks_to_clarify(monkeypatch):
    _fake_router(monkeypatch, '{"organs": [], "reason": "not a clinical question"}')
    r = handle_query("how do I renew my passport")
    assert r.needs_clarification and r.routing_method == "nemotron"
    assert r.routing_reason == "not a clinical question"

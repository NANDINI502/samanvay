"""Live web fallback (rag/web.py), offline: Tavily's HTTP call is replaced
by a stub returning a fixed response shape, and model calls are mocked.
The fallback may only replace a low-confidence deferral; red flags,
referrals and the safety check are untouched.

The two low-confidence queries were found by running retrieval on the
current TF-IDF corpus (best scores 0.09 neuro, 0.11 cardiac; MIN_SCORE 0.12).
The stub pages carry placeholder text only — no medical content."""
import pytest

from agents.specialist import SpecialistAgent
from orchestrator import router
from rag import web

LOW_NEURO = "Is zika virus dangerous for the brain?"
LOW_CARDIAC = "Is the heart affected by long covid?"


def _hit(url, content="Placeholder page text for the test."):
    return {"url": url, "title": f"Page at {url}", "content": content, "score": 0.5}


@pytest.fixture
def tavily(monkeypatch):
    """Turn the fallback on and record every Tavily request."""
    calls = []
    response = {"results": [_hit("https://www.who.int/news-room/fact-sheets/detail/example"),
                            _hit("https://www.ncbi.nlm.nih.gov/books/example/")]}

    def post(payload, timeout):
        calls.append(payload)
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(web, "enabled", lambda: True)
    monkeypatch.setattr(web, "_post", post)

    class Ctl:
        requests = calls

        def respond(self, value):
            nonlocal response
            response = value
    return Ctl()


def test_low_confidence_query_really_defers_without_fallback():
    r = SpecialistAgent("neuro").run(LOW_NEURO)
    assert r.deferred and r.defer_kind == "low_confidence" and r.source == "corpus" and r.web_error is None


def test_off_by_default_and_in_mock_mode(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    monkeypatch.delenv("MEDBOT_WEB_FALLBACK", raising=False)
    assert not web.enabled()
    monkeypatch.setenv("MEDBOT_WEB_FALLBACK", "1")
    assert not web.enabled()  # tests run with MEDBOT_MOCK_LLM=1
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "0")
    assert web.enabled()
    monkeypatch.delenv("TAVILY_API_KEY")
    assert not web.enabled()


def test_request_is_restricted_to_allowed_domains(tavily):
    SpecialistAgent("neuro").run(LOW_NEURO)
    (p,) = tavily.requests
    assert p["query"] == LOW_NEURO
    assert p["include_domains"] == ["who.int", "nih.gov", "cdc.gov"] and p["include_domains_mode"] == "restrict"


def test_low_confidence_answered_from_web_and_labelled(tavily):
    r = SpecialistAgent("neuro").run(LOW_NEURO)
    assert not r.deferred and r.source == "live_web" and r.risk is None
    assert r.citations == ["https://www.who.int/news-room/fact-sheets/detail/example",
                           "https://www.ncbi.nlm.nih.gov/books/example/"]
    assert r.call["step"] == "Neuro agent (live web source)"
    # the mock reply echoes the start of the prompt: the web excerpts were the context
    assert "Context (Live web source): ### Page at https://www.who.int/" in r.answer

    for audience, language, label in [("clinician", "en", "Live web source (WHO / NIH / CDC search"),
                                      ("health_worker", "en", "Live web source, not this tool's checked guidance"),
                                      ("health_worker", "hi", "लाइव वेब स्रोत"),
                                      ("health_worker", "hinglish", "Live web source, is tool ki")]:
        out = router.handle_query(LOW_NEURO, audience=audience, language=language)
        assert not out.deferred
        assert label in out.final_answer
        assert "https://www.who.int/news-room/fact-sheets/detail/example" in out.final_answer


def test_disallowed_results_are_dropped(tavily):
    tavily.respond({"results": [_hit("https://who.int.example.com/page"), _hit("http://www.cdc.gov/insecure"),
                                _hit("https://example.com/cdc.gov"), _hit("https://www.cdc.gov/empty", content="")]})
    r = SpecialistAgent("neuro").run(LOW_NEURO)
    assert r.deferred and r.defer_kind == "low_confidence" and r.web_error == "no WHO / NIH / CDC result"
    assert r.call is None


@pytest.mark.parametrize("url,ok", [
    ("https://www.who.int/x", True), ("https://who.int/x", True), ("https://www.ncbi.nlm.nih.gov/x", True),
    ("https://www.cdc.gov/x", True), ("http://www.cdc.gov/x", False), ("https://fakewho.int/x", False),
    ("https://who.int.evil.com/x", False), ("https://nih.gov.example.org/x", False), ("not a url", False),
])
def test_allowed_url(url, ok):
    assert web.allowed_url(url) is ok


def test_tavily_error_keeps_deferral_and_redacts_key(tavily, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret-123")
    tavily.respond(RuntimeError("401 for key tvly-secret-123"))
    r = SpecialistAgent("cardiac").run(LOW_CARDIAC)
    assert r.deferred and r.defer_kind == "low_confidence" and r.call is None
    assert "tvly-secret-123" not in r.web_error and "<TAVILY_API_KEY>" in r.web_error


@pytest.mark.parametrize("query", [
    "sudden facial droop and slurred speech",  # red flag
    "Patient with ascites and a history of hepatitis B — what next?",  # hepatic referral
])
def test_guardrail_deferrals_never_reach_the_web(tavily, query):
    out = router.handle_query(query)
    assert out.deferred and tavily.requests == []
    assert all(a.source == "corpus" for a in out.agent_answers.values())


def test_red_flag_in_a_low_confidence_question_still_defers(tavily):
    out = router.handle_query("Is zika virus dangerous for the brain? She had a seizure today")
    assert out.deferred and out.routing_method == "red_flag" and tavily.requests == []


def test_safety_check_still_overrides_a_web_answer(tavily, monkeypatch):
    """Same stub as tests/test_safety.py: the safety model reports an emergency."""
    from orchestrator import safety
    from orchestrator.client import ChatResult
    monkeypatch.setattr(safety, "mock_enabled", lambda: False)
    monkeypatch.setattr(safety, "chat_as_agent", lambda messages, **kw: ChatResult(
        text='{"emergency": true, "sign": "seizure", "reason": "test"}', model="fake", role="agent"))
    out = router.handle_query(LOW_NEURO)
    assert out.deferred and out.routing_method == "safety_model"
    assert "Live web source" not in out.final_answer and out.agent_answers == {}


def test_risk_tool_not_run_on_web_answer(tavily, monkeypatch):
    from agents.registry import AGENT_CONFIGS
    assert AGENT_CONFIGS["cardiac"].get("risk_model")
    from fastapi.testclient import TestClient
    from api.app import app
    values = TestClient(app).get("/api/example/cardiac").json()["values"]  # real UCI row
    out = router.handle_query(LOW_CARDIAC, patient_values=values)
    cardiac = out.agent_answers["cardiac"]
    assert cardiac.source == "live_web" and cardiac.risk is None
    assert "Cardiac risk tool not run: this answer comes from a live web source" in out.final_answer


def test_eval_harness_observes_web_fallback(tavily):
    from eval.run import load_cases, observe, score
    case = next(c for c in load_cases() if c["id"] == "web-01")
    obs = observe(case)
    assert obs["web_agents"] == ["neuro"] and obs["web_urls_allowed"] and obs["web_labelled"]
    assert all(score(case, obs).values())


def test_eval_web_cases_defer_for_low_confidence_when_fallback_off():
    from eval.run import load_cases, observe
    for case in [c for c in load_cases() if c["category"] == "web_fallback"]:
        obs = observe(case)
        assert obs["low_confidence_agents"] == case["expected_agents"] and obs["web_agents"] == []

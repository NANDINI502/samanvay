"""Clinician vs health-worker mode (orchestrator/audience.py): only the
wording changes. Every decision — routing, red flags, safety check,
referrals, retrieval confidence, risk tools, citations — is identical."""
import re

import pytest
from fastapi.testclient import TestClient

from api.app import app
from eval.run import load_cases
from orchestrator import router
from orchestrator.audience import normalize
from orchestrator.client import ChatResult
from orchestrator.router import handle_query

MODES = [("health_worker", "en"), ("health_worker", "hi"), ("health_worker", "hinglish")]
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def _decisions(r):
    return (r.deferred, r.needs_clarification, r.routing_method, r.agents_consulted,
            {o: (a.deferred, a.defer_kind, a.citations, a.risk) for o, a in r.agent_answers.items()})


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_same_decisions_in_every_mode(case):
    """All eval cases: health-worker mode in each language decides exactly as clinician mode."""
    base = handle_query(case["query"], patient_values=case.get("patient_values"))
    for audience, language in MODES:
        r = handle_query(case["query"], patient_values=case.get("patient_values"),
                         audience=audience, language=language)
        assert _decisions(r) == _decisions(base), (audience, language)


def test_clinician_is_english_only():
    assert normalize("clinician", "hi") == ("clinician", "en")
    assert normalize(None, None) == ("clinician", "en")
    with pytest.raises(ValueError):
        normalize("patient", "en")
    with pytest.raises(ValueError):
        normalize("health_worker", "ta")


def test_clinician_red_flag_wording_unchanged():
    r = handle_query("Patient reports chest pain since this morning")
    assert r.final_answer == (
        "Urgent: Query mentions 'chest pain', an emergency warning sign — this needs urgent in-person "
        "medical assessment, not an automated answer. Contact emergency services or go to the nearest "
        "emergency department.")


def test_red_flag_in_hindi_quotes_the_phrase_and_says_what_to_do():
    r = handle_query("मरीज़ को सीने में दर्द है", audience="health_worker", language="hi")
    assert r.deferred and r.routing_method == "red_flag"
    assert "सीने में दर्द" in r.final_answer and DEVANAGARI.search(r.final_answer)
    assert r.final_answer.splitlines()[-1].startswith("अगला कदम:")


def test_red_flag_in_hinglish():
    r = handle_query("usko seene me dard ho raha hai", audience="health_worker", language="hinglish")
    assert r.deferred and r.final_answer.startswith("Turant dhyan dein:")
    assert r.final_answer.splitlines()[-1].startswith("Agla kadam:")


def test_referral_names_the_term_and_says_refer():
    q = "Patient with ascites and a history of hepatitis B — what next?"
    r = handle_query(q, audience="health_worker", language="en")
    assert r.deferred and "'ascites'" in r.final_answer
    assert r.final_answer.splitlines()[-1].startswith("Next step: Refer the patient")


def test_answered_ends_with_next_step_and_prompt_asks_for_language(monkeypatch):
    seen = []

    def synth(messages, **kwargs):
        seen.append(messages[0]["content"])
        return ChatResult(text="जवाब", model="fake-nemotron", role="orchestrator", mock=True)

    monkeypatch.setattr(router, "chat_as_orchestrator", synth)
    r = handle_query("What GFR value suggests kidney disease?", audience="health_worker", language="hi")
    assert not r.deferred
    assert "health worker" in seen[0] and "Devanagari" in seen[0] and "कब रेफ़र करें:" in seen[0]
    assert r.final_answer.splitlines()[-1].startswith("अगला कदम:")


def test_risk_tool_block_kept_in_health_worker_mode():
    values = {"age": 60, "sex": "male", "serum_creatinine": 1.8}  # tests/test_calculators.py inputs
    base = handle_query("What does this patient's eGFR mean?", patient_values=values)
    r = handle_query("What does this patient's eGFR mean?", patient_values=values,
                     audience="health_worker", language="hinglish")
    block = base.final_answer[base.final_answer.index("\n\nRisk tool:"):]
    assert block in r.final_answer


def test_api_accepts_mode_and_rejects_unknown():
    client = TestClient(app)
    d = client.post("/api/ask", json={"question": "seene mein dard", "audience": "health_worker",
                                      "language": "hinglish"}).json()
    assert (d["audience"], d["language"]) == ("health_worker", "hinglish")
    assert d["final_answer"].startswith("Turant dhyan dein:")
    assert client.post("/api/ask", json={"question": "x", "audience": "patient"}).status_code == 422

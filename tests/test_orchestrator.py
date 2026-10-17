"""End-to-end orchestrator behaviour with stubbed Nemotron replies."""
from orchestrator.router import handle_query, keyword_route


def test_single_organ_routing():
    assert keyword_route("What GFR value suggests kidney disease?") == ["renal"]


def test_multi_organ_routing():
    organs = keyword_route("Diabetic patient with eGFR 50 — what blood pressure threshold applies?")
    assert set(organs) >= {"endocrine", "renal", "cardiac"}


def test_full_pipeline_multi_agent_answer():
    r = handle_query("Diabetic patient with eGFR 50 — what blood pressure threshold applies?")
    assert not r.deferred and not r.needs_clarification
    assert set(r.agents_consulted) >= {"endocrine", "renal", "cardiac"}
    answered = [a for a in r.agent_answers.values() if not a.deferred]
    assert answered and all(a.citations for a in answered)
    assert r.final_answer.startswith("[MOCK")


def test_red_flag_short_circuits_before_agents():
    r = handle_query("My father has sudden facial droop and slurred speech")
    assert r.deferred and r.routing_method == "red_flag" and r.agents_consulted == []


def test_referral_from_one_agent_defers_whole_answer():
    r = handle_query("Patient with known stroke history and high cholesterol, what CVD follow-up?")
    assert r.deferred
    assert "neuro" in r.agents_consulted


def test_unroutable_query_asks_for_clarification():
    r = handle_query("how do I renew my passport")
    assert r.needs_clarification and r.agents_consulted == []


import pytest

from rag.retrieve import corpus_limits


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN LIMITATION: lexical (TF-IDF) retrieval can't tell an in-domain but "
    "uncovered question from a covered one — 'liver' matches liver chunks. Such "
    "queries reach the model, which is instructed (with the corpus's own "
    "limits list) to say the material doesn't cover it. Revisit with "
    "EMBED_BACKEND=nebius; remove this xfail once it passes."))
def test_routed_but_uncovered_query_deferred_by_code():
    r = handle_query("liver transplant waiting list rules")
    assert r.deferred


def test_agents_are_told_their_corpus_limits():
    assert "hepatitis C" in corpus_limits("hepatic")
    assert "insulin dosing" in corpus_limits("endocrine")

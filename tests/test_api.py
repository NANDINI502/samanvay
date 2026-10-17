"""Demo API, offline (mock mode). Cardiac patient values come from
/api/example, i.e. real UCI dataset rows."""
from fastapi.testclient import TestClient

from api.app import app
from models.common import DISCLAIMER

client = TestClient(app)


def test_page_and_health():
    assert "MedBot Orchestrator" in client.get("/").text
    h = client.get("/api/health").json()
    assert h["mock"] is True
    assert set(h["risk_models"]) == {"cardiac", "renal", "hepatic"}


def test_schema_lists_agents_and_risk_fields():
    s = client.get("/api/schema").json()
    assert len(s["agents"]) == 6
    keys = {f["key"] for f in s["risk_models"]["cardiac"]["fields"]}
    assert {"age", "sex", "cholesterol", "thal"} <= keys
    assert s["risk_models"]["cardiac"]["kind"] == "model"
    assert s["risk_models"]["renal"]["kind"] == "calculator" and "NEJMoa2102953" in s["risk_models"]["renal"]["citation"]
    assert s["risk_models"]["hepatic"]["kind"] == "calculator" and "hep.21178" in s["risk_models"]["hepatic"]["citation"]
    assert s["disclaimer"] == DISCLAIMER


def test_example_is_a_real_row():
    ex = client.get("/api/example/cardiac").json()
    assert "Real row" in ex["source"] and "doi.org" in ex["source"]
    assert client.get("/api/example/neuro").status_code == 404
    assert client.get("/api/example/renal").status_code == 404  # calculator: no dataset rows


def test_ask_multi_agent_trace():
    d = client.post("/api/ask", json={"question": "Diabetic patient with eGFR 50 — what blood pressure threshold applies?"}).json()
    assert d["mock"] and not d["deferred"]
    assert {a["organ"] for a in d["agents"]} >= {"cardiac", "renal", "endocrine"}
    for a in d["agents"]:
        assert a["display_name"] and a["citations"] and a["answer"].startswith("[MOCK")
    assert d["final_answer"].startswith("[MOCK")


def test_ask_with_risk_values():
    values = client.get("/api/example/cardiac").json()["values"]
    d = client.post("/api/ask", json={"question": "What is this patient's cardiovascular risk?",
                                      "patient_values": values}).json()
    risk = next(a for a in d["agents"] if a["organ"] == "cardiac")["risk"]
    assert risk["status"] == "ok" and risk["disclaimer"] == DISCLAIMER
    assert DISCLAIMER in d["final_answer"]


def test_ask_with_incomplete_values_asks_for_them():
    values = client.get("/api/example/cardiac").json()["values"]
    values["thal"] = ""
    d = client.post("/api/ask", json={"question": "What is this patient's cardiovascular risk?",
                                      "patient_values": values}).json()
    risk = next(a for a in d["agents"] if a["organ"] == "cardiac")["risk"]
    assert risk["status"] == "needs_values" and [m["key"] for m in risk["missing"]] == ["thal"]


def test_red_flag_trace_has_no_agents():
    d = client.post("/api/ask", json={"question": "sudden facial droop and slurred speech"}).json()
    assert d["deferred"] and d["routing_method"] == "red_flag" and d["agents"] == []


def test_bad_requests_rejected():
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "x" * 2001}).status_code == 422


def test_trace_shows_which_model_handled_each_step():
    from orchestrator.client import AGENT_MODEL, ORCHESTRATOR_MODEL
    d = client.post("/api/ask", json={"question": "Diabetic patient with eGFR 50 — what blood pressure threshold applies?"}).json()
    steps = [(c["step"], c["role"], c["model"]) for c in d["model_calls"]]
    assert steps[-1] == ("Synthesis", "orchestrator", ORCHESTRATOR_MODEL)
    assert {s for s in steps[:-1]} == {(f"{n} agent", "agent", AGENT_MODEL) for n in ("Cardiac", "Renal", "Endocrine")}
    for c in d["model_calls"]:
        assert c["mock"] is True and c["usage"] is None and c["latency_ms"] is not None
    assert isinstance(d["total_ms"], int)


def test_deferred_answers_make_no_model_calls():
    for q in ["sudden facial droop and slurred speech", "Patient with ascites and a history of hepatitis B — what next?"]:
        d = client.post("/api/ask", json={"question": q}).json()
        assert d["deferred"] and d["model_calls"] == []
        assert all(a["call"] is None for a in d["agents"])


def test_page_has_safety_banner_and_examples():
    html = client.get("/").text
    assert "Decision support, not diagnosis." in html
    assert "Red flag → deferral" in html and "Multi-agent" in html


def test_health_reports_readiness_without_leaking_key(monkeypatch):
    from orchestrator import client as llm
    monkeypatch.setattr(llm, "NEBIUS_API_KEY", "secret-value-should-not-appear")
    r = client.get("/api/health")
    assert r.status_code == 200
    h = r.json()
    assert h["status"] == "ok" and h["ready"] is True and h["indexes_ready"] is True
    assert h["api_key_configured"] is True
    assert "secret-value-should-not-appear" not in r.text


def test_health_not_ready_live_without_key(monkeypatch):
    from orchestrator import client as llm
    monkeypatch.setattr(llm, "NEBIUS_API_KEY", None)
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "0")
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["ready"] is False and h["api_key_configured"] is False


def test_model_failure_returns_503_without_key(monkeypatch):
    from orchestrator import client as llm
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "0")
    monkeypatch.setattr(llm, "NEBIUS_API_KEY", "leaky-key-123")

    def fail(*a, **k):
        raise RuntimeError("401 Unauthorized for key leaky-key-123")
    monkeypatch.setattr(llm, "_client", fail)
    r = client.post("/api/ask", json={"question": "What GFR value suggests kidney disease?"})
    assert r.status_code == 503 and "model service is unavailable" in r.text
    assert "leaky-key-123" not in r.text
    # deterministic deferrals still work without the model service
    assert client.post("/api/ask", json={"question": "sudden facial droop"}).json()["deferred"]

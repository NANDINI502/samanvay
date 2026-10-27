"""Public-demo limits: /api/ask is rate-limited per IP and by a daily cap;
/api/health is never limited and makes no model call. Offline (mock mode)."""
from fastapi.testclient import TestClient

from api.app import app
from orchestrator import client as llm

client = TestClient(app)
Q = {"question": "What GFR value suggests kidney disease?"}


def test_per_ip_limit_returns_friendly_429(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "2")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "100")
    h = {"X-Forwarded-For": "203.0.113.5, 10.0.0.1"}
    assert client.post("/api/ask", json=Q, headers=h).status_code == 200
    assert client.post("/api/ask", json=Q, headers=h).status_code == 200
    r = client.post("/api/ask", json=Q, headers=h)
    assert r.status_code == 429 and r.json()["detail"].startswith("Demo limit reached")
    # a different address still gets answers
    assert client.post("/api/ask", json=Q, headers={"X-Forwarded-For": "198.51.100.7"}).status_code == 200


def test_daily_cap_applies_across_ips(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "100")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "3")
    for i in range(3):
        assert client.post("/api/ask", json=Q, headers={"X-Forwarded-For": f"192.0.2.{i}"}).status_code == 200
    r = client.post("/api/ask", json=Q, headers={"X-Forwarded-For": "192.0.2.99"})
    assert r.status_code == 429 and "for today" in r.json()["detail"]


def test_red_flags_also_count_but_validation_errors_do_not(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "1")
    assert client.post("/api/ask", json={"question": ""}).status_code == 422
    assert client.post("/api/ask", json={"question": "sudden facial droop"}).json()["deferred"]
    assert client.post("/api/ask", json=Q).status_code == 429


def test_health_is_not_rate_limited_and_calls_no_model(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "1")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "1")
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "0")
    monkeypatch.setattr(llm, "NEBIUS_API_KEY", "k")

    def no_calls(*a, **k):
        raise AssertionError("/api/health must not create a model client")
    monkeypatch.setattr(llm, "_client", no_calls)
    for _ in range(20):
        assert client.get("/api/health").status_code == 200
        assert client.head("/api/health").status_code == 200
    assert client.post("/api/ask", json={"question": "sudden facial droop"}).status_code == 200
    assert client.get("/api/health").status_code == 200


def test_limit_off_when_zero(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "0")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "0")
    for _ in range(15):
        assert client.post("/api/ask", json={"question": "sudden facial droop"}).status_code == 200


def test_max_tokens_is_capped(monkeypatch):
    seen = {}

    class Fake:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen.update(kw)
                    raise RuntimeError("stop here")
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "0")
    monkeypatch.setattr(llm, "_client", lambda: Fake)
    monkeypatch.setattr(llm, "MAX_TOKENS_CAP", 1500)
    try:
        llm.chat([{"role": "user", "content": "hi"}], model="m", max_tokens=4000)
    except RuntimeError:
        pass
    assert seen["max_tokens"] == 1500
    try:
        llm.chat([{"role": "user", "content": "hi"}], model="m", max_tokens=120)
    except RuntimeError:
        pass
    assert seen["max_tokens"] == 120


def test_forged_forwarded_for_does_not_dodge_the_per_ip_limit(monkeypatch):
    # The client writes the first X-Forwarded-For entry; the proxy appends the real one.
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "2")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "100")
    for fake in ("1.1.1.1", "2.2.2.2"):
        h = {"X-Forwarded-For": f"{fake}, 203.0.113.9"}
        assert client.post("/api/ask", json=Q, headers=h).status_code == 200
    r = client.post("/api/ask", json=Q, headers={"X-Forwarded-For": "3.3.3.3, 203.0.113.9"})
    assert r.status_code == 429


def test_cloudflare_client_ip_wins_over_forwarded_for(monkeypatch):
    monkeypatch.setenv("MEDBOT_RATE_PER_IP", "1")
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "100")
    h = {"CF-Connecting-IP": "198.51.100.20", "X-Forwarded-For": "9.9.9.9, 10.0.0.1"}
    assert client.post("/api/ask", json=Q, headers=h).status_code == 200
    # same Cloudflare address, different forged chain: still the same client
    h2 = {"CF-Connecting-IP": "198.51.100.20", "X-Forwarded-For": "8.8.8.8, 10.0.0.2"}
    assert client.post("/api/ask", json=Q, headers=h2).status_code == 429
    # another Cloudflare address behind the same proxy is a different client
    h3 = {"CF-Connecting-IP": "198.51.100.21", "X-Forwarded-For": "8.8.8.8, 10.0.0.2"}
    assert client.post("/api/ask", json=Q, headers=h3).status_code == 200


def test_client_ip_order():
    from api.ratelimit import client_ip
    assert client_ip({"cf-connecting-ip": "198.51.100.1", "x-forwarded-for": "1.1.1.1"}, "peer") == "198.51.100.1"
    assert client_ip({"x-forwarded-for": "1.1.1.1, 203.0.113.4"}, "peer") == "203.0.113.4"
    assert client_ip({}, "peer") == "peer"


def test_default_per_ip_limit_is_30(monkeypatch):
    monkeypatch.delenv("MEDBOT_RATE_PER_IP", raising=False)
    monkeypatch.setenv("MEDBOT_DAILY_CAP", "100")
    h = {"CF-Connecting-IP": "198.51.100.30"}
    for _ in range(30):
        assert client.post("/api/ask", json={"question": "sudden facial droop"}, headers=h).status_code == 200
    assert client.post("/api/ask", json={"question": "sudden facial droop"}, headers=h).status_code == 429

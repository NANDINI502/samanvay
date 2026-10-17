"""scripts/check_nebius.py, offline: Token Factory responses are faked, and
the API key must never appear in the output — including in error messages."""
import importlib.util
from pathlib import Path

import pytest

from orchestrator import client

FAKE_KEY = "test-key-0123456789abcdef"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_nebius.py"


@pytest.fixture
def check(monkeypatch):
    spec = importlib.util.spec_from_file_location("check_nebius", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(client, "NEBIUS_API_KEY", FAKE_KEY)
    monkeypatch.setattr(client, "ORCHESTRATOR_MODEL", "nvidia/nemotron-ultra-x")
    monkeypatch.setattr(client, "AGENT_MODEL", "nvidia/nemotron-super-y")
    monkeypatch.setenv("MEDBOT_MOCK_LLM", "1")  # the script must switch to live anyway
    return mod


def test_lists_highlights_and_calls(check, monkeypatch, capsys):
    monkeypatch.setattr(client, "list_models", lambda: ["meta/llama-z", "nvidia/nemotron-super-y", "nvidia/nemotron-ultra-x"])
    calls = []

    def fake_chat(messages, *, model, **kw):
        calls.append((model, client.mock_enabled()))
        return client.ChatResult(text="ok", model=model, raw={"usage": {"prompt_tokens": 9, "completion_tokens": 1, "total_tokens": 10}})

    monkeypatch.setattr(client, "chat", fake_chat)
    assert check.main([]) == 0
    out = capsys.readouterr().out
    assert "* nvidia/nemotron-ultra-x   <- configured as orchestrator" in out
    assert "* nvidia/nemotron-super-y   <- configured as agent" in out
    assert "Other models (1): meta/llama-z" in out
    assert "total 10" in out and "'ok'" in out
    assert calls == [("nvidia/nemotron-super-y", False)]  # one call, live (mock switched off)
    assert FAKE_KEY not in out


def test_missing_configured_model_reported(check, monkeypatch, capsys):
    monkeypatch.setattr(client, "list_models", lambda: ["nvidia/nemotron-super-y"])
    assert check.main(["--no-call"]) == 3
    assert "NOT in the list" in capsys.readouterr().out


def test_key_never_printed_on_error(check, monkeypatch, capsys):
    def boom():
        raise RuntimeError(f"401 invalid key {FAKE_KEY}")
    monkeypatch.setattr(client, "list_models", boom)
    assert check.main([]) == 1
    out = capsys.readouterr().out
    assert FAKE_KEY not in out and "<NEBIUS_API_KEY>" in out


def test_no_key_stops_before_any_call(check, monkeypatch, capsys):
    monkeypatch.setattr(client, "NEBIUS_API_KEY", None)
    monkeypatch.setattr(client, "list_models", lambda: pytest.fail("must not call Token Factory without a key"))
    assert check.main([]) == 2
    assert "API key:       NOT SET" in capsys.readouterr().out


def test_nemotron_detection():
    assert check_is("nvidia/Llama-3_1-Nemotron-Ultra-253B-v1") and not check_is("meta-llama/Llama-3.3-70B")


def check_is(model_id):
    spec = importlib.util.spec_from_file_location("check_nebius", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.is_nemotron(model_id)

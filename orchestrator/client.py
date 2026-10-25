"""Thin wrapper around the Nebius Token Factory OpenAI-compatible client.

All model calls in this project — orchestrator and every specialist agent —
go through this module, so there is exactly one place that talks to Nebius.
This satisfies the hackathon's hard requirement that the submission runs on
Nebius Token Factory / Nebius AI Cloud.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

NEBIUS_BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
NEBIUS_API_KEY = os.environ.get("NEBIUS_API_KEY")

ORCHESTRATOR_MODEL = os.environ.get("NEMOTRON_ORCHESTRATOR_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b")
AGENT_MODEL = os.environ.get("NEMOTRON_AGENT_MODEL", "nvidia/nemotron-3-super-120b-a12b")
# Router: a short strict-JSON classification, so the cheapest tier that routes
# correctly is the goal; defaults to the agent model until benchmarked.
ROUTER_MODEL = os.environ.get("NEMOTRON_ROUTER_MODEL") or AGENT_MODEL
# Hard ceiling on max_tokens for every call (bounds spend on a public demo).
# The default equals the largest budget any call asks for, so it changes
# nothing unless lowered; lower it and long answers raise TruncatedReply.
MAX_TOKENS_CAP = int(os.environ.get("MEDBOT_MAX_TOKENS_CAP", "4000"))


class TruncatedReply(RuntimeError):
    """The model hit max_tokens. The text may be cut off mid-answer or, if it
    ended while still reasoning, be the reasoning itself: never show it."""


@dataclass
class ChatResult:
    text: str
    model: str
    raw: dict | None = None
    role: str = ""                  # "orchestrator" | "agent" (set by chat_as_*)
    latency_s: float | None = None  # wall-clock time of the call
    usage: dict | None = None       # {"prompt_tokens", "completion_tokens", "total_tokens"}; None in mock mode
    mock: bool = False

    def trace(self, step: str) -> dict:
        """What the UI shows for one model call: which model, which role, how long, how many tokens."""
        return {"step": step, "role": self.role, "model": self.model, "mock": self.mock,
                "latency_ms": round(self.latency_s * 1000) if self.latency_s is not None else None,
                "usage": self.usage}


def _client() -> OpenAI:
    if not NEBIUS_API_KEY:
        raise RuntimeError(
            "NEBIUS_API_KEY is not set. Copy .env.example to .env and fill in "
            "your Nebius Token Factory key before making live calls."
        )
    return OpenAI(base_url=NEBIUS_BASE_URL, api_key=NEBIUS_API_KEY)


def mock_enabled() -> bool:
    return os.environ.get("MEDBOT_MOCK_LLM", "").lower() in {"1", "true", "yes"}


def _mock_reply(messages: list[dict], model: str) -> ChatResult:
    """Offline stand-in for a Nemotron call, for tests and for working without
    network access. Clearly labelled so it can never be mistaken for a real
    model answer in a demo."""
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    preview = " ".join(user.split())[:160]
    return ChatResult(text=f"[MOCK {model}] Would answer from: {preview}...", model=model, mock=True)


def chat(messages: list[dict], *, model: str, temperature: float = 0.2, max_tokens: int = 4000,
         timeout: float | None = None, thinking: bool = True) -> ChatResult:
    """Single call against a Nebius Token Factory model.

    `messages` follows the standard OpenAI chat format:
    [{"role": "system"|"user"|"assistant", "content": "..."}]
    Nemotron 3 reasons before answering, and the reasoning counts against
    `max_tokens`. `thinking=False` turns it off (chat_template_kwargs,
    honoured by Token Factory) for short strict-JSON calls, where a small
    budget would otherwise end before any answer is written. With reasoning
    on, the default budget leaves room for both (live, Ultra synthesis used
    all of an 800-token budget and returned its reasoning as the answer).
    A reply cut off at `max_tokens` raises TruncatedReply. `max_tokens` is
    clamped to MAX_TOKENS_CAP.
    Set MEDBOT_MOCK_LLM=1 to run the full pipeline offline with stub replies.
    """
    max_tokens = max(1, min(max_tokens, MAX_TOKENS_CAP))
    start = time.perf_counter()
    if mock_enabled():
        result = _mock_reply(messages, model)
        result.latency_s = time.perf_counter() - start
        return result
    client = _client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **({"timeout": timeout} if timeout is not None else {}),
        **({} if thinking else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}),
    )
    latency = time.perf_counter() - start
    if response.choices[0].finish_reason == "length":
        raise TruncatedReply(f"{model} reply cut off at max_tokens={max_tokens}")
    text = response.choices[0].message.content or ""
    raw = response.model_dump() if hasattr(response, "model_dump") else None
    u = (raw or {}).get("usage") or {}
    usage = {k: u.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")} if u else None
    return ChatResult(text=text, model=getattr(response, "model", None) or model, raw=raw,
                      latency_s=latency, usage=usage)


def list_models() -> list[str]:
    """IDs of the models available to this key on Token Factory (live only)."""
    return sorted(m.id for m in _client().models.list())


def redact(text: str) -> str:
    """Remove the API key from any text before it is printed or logged."""
    return text.replace(NEBIUS_API_KEY, "<NEBIUS_API_KEY>") if NEBIUS_API_KEY else text


def chat_as_orchestrator(messages: list[dict], **kwargs) -> ChatResult:
    result = chat(messages, model=ORCHESTRATOR_MODEL, **kwargs)
    result.role = "orchestrator"
    return result


def chat_as_agent(messages: list[dict], **kwargs) -> ChatResult:
    result = chat(messages, model=AGENT_MODEL, **kwargs)
    result.role = "agent"
    return result


def chat_as_router(messages: list[dict], **kwargs) -> ChatResult:
    result = chat(messages, model=ROUTER_MODEL, **kwargs)
    result.role = "router"
    return result

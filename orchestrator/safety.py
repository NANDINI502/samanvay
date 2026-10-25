"""One-way model safety check: Nemotron (agent tier) looks for emergency
warning signs that the deterministic keyword check missed — paraphrases
("blood in her vomit"), other wording, other languages.

It can only ADD a deferral, never remove one:
  - It runs only after the keyword check (guardrails/checks.py) has passed;
    a keyword red flag never reaches it.
  - "emergency": true defers the whole answer, like a keyword red flag.
  - "emergency": false changes nothing; the normal guardrails still run.
  - Error, timeout or a reply that isn't the strict JSON below: the
    deterministic result stands (no deferral added, none removed) and the
    trace says the check was unavailable.

The model is given our existing English red-flag list as the definition of
an emergency, so it recognises other wordings of those signs only; it adds
no clinical criteria of its own.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from guardrails.checks import GLOBAL_RED_FLAGS
from orchestrator import client
from orchestrator.client import chat_as_agent, mock_enabled, redact

TIMEOUT_S = float(os.environ.get("MEDBOT_SAFETY_TIMEOUT_S", "10"))

SYSTEM_PROMPT = (
    "You are a safety screen in a clinical decision-support tool. Decide whether the "
    "user's message describes a patient who currently has any of these emergency "
    "warning signs, in any wording or language (English, Hindi, Hinglish): "
    + "; ".join(GLOBAL_RED_FLAGS) + ". "
    "Only these signs count. A general question about a condition, with no patient "
    "currently showing one of these signs, is not an emergency. "
    'Reply with ONLY this JSON, nothing else: {"emergency": true or false, '
    '"sign": "<the matching sign from the list, or empty>", "reason": "<one short line>"}'
)


@dataclass
class SafetyResult:
    status: str               # "emergency" | "clear" | "unavailable" | "skipped"
    sign: str = ""
    reason: str = ""
    call: dict | None = None  # ChatResult.trace(), when a model call was made

    @property
    def emergency(self) -> bool:
        return self.status == "emergency"

    def to_dict(self) -> dict:
        return {"status": self.status, "sign": self.sign, "reason": self.reason}


def parse(text: str) -> tuple[bool, str, str]:
    """Strict: one JSON object with a boolean "emergency". Raises ValueError otherwise."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in reply")
    data = json.loads(match.group(0))
    if not isinstance(data, dict) or not isinstance(data.get("emergency"), bool):
        raise ValueError('reply has no boolean "emergency"')
    return data["emergency"], str(data.get("sign") or ""), str(data.get("reason") or "")


def check(query: str) -> SafetyResult:
    if mock_enabled():
        return SafetyResult("skipped", reason="mock mode: no model call")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": query}]
    call = None
    try:
        result = chat_as_agent(messages, model=client.SAFETY_MODEL, max_tokens=120, temperature=0,
                               timeout=TIMEOUT_S, thinking=False)
        call = result.trace("Safety check")
        emergency, sign, reason = parse(result.text)
    except Exception as e:  # fail open to the deterministic result, which already ran
        return SafetyResult("unavailable", reason=redact(f"{type(e).__name__}: {e}")[:200], call=call)
    return SafetyResult("emergency" if emergency else "clear", sign=sign, reason=reason, call=call)

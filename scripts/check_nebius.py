"""Live-mode readiness check for Nebius Token Factory.

    python scripts/check_nebius.py                 # list models + one tiny test call
    python scripts/check_nebius.py --no-call       # list models only
    python scripts/check_nebius.py --model <id>    # test call against a specific model

  (a) lists the models available to your key,
  (b) highlights NVIDIA Nemotron ones and whether the IDs configured in .env
      (NEMOTRON_ORCHESTRATOR_MODEL, NEMOTRON_AGENT_MODEL) are among them,
  (c) makes one tiny chat call and reports latency and token usage.

Everything goes through orchestrator/client.py. The API key is never printed:
only whether it is set, and every error message is passed through redact().
This script always runs live, even if MEDBOT_MOCK_LLM=1 is set in .env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import client  # noqa: E402  (loads .env)


def is_nemotron(model_id: str) -> bool:
    return "nemotron" in model_id.lower()


def _error(e: Exception) -> str:
    status = getattr(e, "status_code", None)
    return client.redact(f"{type(e).__name__}" + (f" (HTTP {status})" if status else "") + f": {e}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/check_nebius.py")
    parser.add_argument("--no-call", action="store_true", help="only list models; skip the test call")
    parser.add_argument("--model", help="model ID for the test call (default: NEMOTRON_AGENT_MODEL)")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if client.mock_enabled():
        print("Note: MEDBOT_MOCK_LLM is on in your environment; this check ignores it and runs live.")
        os.environ["MEDBOT_MOCK_LLM"] = "0"

    print(f"Endpoint:      {client.NEBIUS_BASE_URL}")
    print(f"API key:       {'set' if client.NEBIUS_API_KEY else 'NOT SET'}")
    print(f"Orchestrator:  {client.ORCHESTRATOR_MODEL}  (NEMOTRON_ORCHESTRATOR_MODEL)")
    print(f"Agent:         {client.AGENT_MODEL}  (NEMOTRON_AGENT_MODEL)")
    if not client.NEBIUS_API_KEY:
        print("\nSet NEBIUS_API_KEY in .env (copy .env.example), then run this again.")
        return 2

    # (a) list models
    print("\n(a) Listing models available to this key ...")
    try:
        models = client.list_models()
    except Exception as e:  # auth, network, endpoint errors
        print(f"    FAILED: {_error(e)}")
        return 1
    print(f"    {len(models)} models available.")

    # (b) highlight Nemotron
    nemotron = [m for m in models if is_nemotron(m)]
    print(f"\n(b) NVIDIA Nemotron models ({len(nemotron)}):")
    for m in nemotron:
        role = [r for r, mid in (("orchestrator", client.ORCHESTRATOR_MODEL), ("agent", client.AGENT_MODEL)) if mid == m]
        print(f"    * {m}" + (f"   <- configured as {' + '.join(role)}" if role else ""))
    if not nemotron:
        print("    none found — check the Token Factory console.")
    others = [m for m in models if not is_nemotron(m)]
    if others:
        print(f"    Other models ({len(others)}): " + ", ".join(others))
    configured_ok = True
    for name, mid in (("NEMOTRON_ORCHESTRATOR_MODEL", client.ORCHESTRATOR_MODEL),
                      ("NEMOTRON_AGENT_MODEL", client.AGENT_MODEL)):
        found = mid in models
        configured_ok &= found
        print(f"    {name} = {mid}: {'available' if found else 'NOT in the list — update .env'}")

    # (c) one tiny test call
    if args.no_call:
        return 0 if configured_ok else 3
    model = args.model or client.AGENT_MODEL
    print(f"\n(c) Test call to {model} ...")
    start = time.perf_counter()
    try:
        result = client.chat([{"role": "user", "content": "Reply with the single word: ok"}],
                             model=model, temperature=0, max_tokens=64)
    except Exception as e:
        print(f"    FAILED after {time.perf_counter() - start:.2f}s: {_error(e)}")
        return 1
    latency = time.perf_counter() - start
    usage = (result.raw or {}).get("usage") or {}
    print(f"    OK in {latency:.2f}s")
    print(f"    tokens: prompt {usage.get('prompt_tokens', '?')}, completion {usage.get('completion_tokens', '?')}, "
          f"total {usage.get('total_tokens', '?')}")
    print(f"    reply: {client.redact(result.text.strip())[:200]!r}")
    if not result.text.strip():
        print("    Warning: empty reply text (a reasoning model may have used the whole token budget).")
    return 0 if configured_ok else 3


if __name__ == "__main__":
    sys.exit(main())

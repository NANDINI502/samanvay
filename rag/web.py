"""Live web fallback (Tavily), used only when an agent's own corpus has no
confident match for a query (the retrieval-confidence guardrail).

Off unless MEDBOT_WEB_FALLBACK=1 and TAVILY_API_KEY is set, and never in
mock mode. It runs only in place of a low-confidence deferral: red flags
and referral terms are checked first and still defer, so the web can't
answer anything the guardrails stop, and the safety check still runs.

Sources are restricted to ALLOWED_DOMAINS twice: Tavily's include_domains
(mode "restrict", https://docs.tavily.com/documentation/api-reference/endpoint/search)
and a host check here, since those docs don't say how subdomains match.
No allowed result, or any error/timeout → the agent keeps its deferral.

  TAVILY_API_KEY          secret, from .env or a platform secret
  MEDBOT_WEB_FALLBACK     1 = on (default off)
  MEDBOT_WEB_TIMEOUT_S    request timeout, default 10
  MEDBOT_WEB_MAX_RESULTS  results kept, default 3
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

from orchestrator.client import mock_enabled

load_dotenv()

TAVILY_URL = "https://api.tavily.com/search"
ALLOWED_DOMAINS = ("who.int", "nih.gov", "cdc.gov")
LABEL = "Live web source"


def enabled() -> bool:
    return (os.environ.get("MEDBOT_WEB_FALLBACK", "").lower() in {"1", "true", "yes"}
            and bool(os.environ.get("TAVILY_API_KEY")) and not mock_enabled())


def allowed_url(url: str) -> bool:
    """https only, host equal to or a subdomain of an allowed domain."""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = (p.hostname or "").lower()
    return p.scheme == "https" and any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def redact(text: str) -> str:
    key = os.environ.get("TAVILY_API_KEY")
    return text.replace(key, "<TAVILY_API_KEY>") if key else text


def _post(payload: dict, timeout: float) -> dict:
    r = httpx.post(TAVILY_URL, json=payload, timeout=timeout,
                   headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"})
    r.raise_for_status()
    return r.json()


def search(query: str) -> tuple[list[dict], str | None]:
    """([{"title", "url", "content", "score"}], error). Only allowed-domain
    results with text are returned; error is a redacted reason or None."""
    max_results = int(os.environ.get("MEDBOT_WEB_MAX_RESULTS", "3"))
    payload = {"query": query, "search_depth": "basic", "topic": "general", "max_results": max_results,
               "include_domains": list(ALLOWED_DOMAINS), "include_domains_mode": "restrict"}
    try:
        data = _post(payload, float(os.environ.get("MEDBOT_WEB_TIMEOUT_S", "10")))
    except Exception as e:
        return [], redact(f"{type(e).__name__}: {e}")[:160]
    hits = [{"title": (h.get("title") or "").strip(), "url": h["url"], "content": (h.get("content") or "").strip(),
             "score": h.get("score")}
            for h in data.get("results") or [] if h.get("url") and allowed_url(h["url"])]
    return [h for h in hits if h["content"]][:max_results], None

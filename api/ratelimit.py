"""In-memory limits for the public demo, applied to /api/ask only.

Every /api/ask can spend Token Factory credits, so a public URL needs a
ceiling. Two limits, both read from the environment at call time:

  MEDBOT_RATE_PER_IP    questions per client IP per window (default 10)
  MEDBOT_RATE_WINDOW_S  window length in seconds (default 3600)
  MEDBOT_DAILY_CAP      questions per UTC day across all clients (default 200)

A value <= 0 turns that limit off. State lives in this process only: a
restart (or a free-tier spin-down) resets it, which is fine for one demo
instance. /api/health and the static page are never limited, so an uptime
pinger doesn't use up the budget.

Behind a proxy (Render, HF) the client IP is the first X-Forwarded-For
entry. A client can forge that header to dodge the per-IP limit, which is
why the global daily cap exists: it bounds total spend regardless.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime, timezone


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class DemoLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}
        self._day = ""
        self._day_count = 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
            self._day, self._day_count = "", 0

    def check(self, ip: str) -> str | None:
        """Count one question from `ip`. Returns None if allowed, else the
        message to show (and nothing is counted)."""
        per_ip = _env_int("MEDBOT_RATE_PER_IP", 10)
        window = _env_int("MEDBOT_RATE_WINDOW_S", 3600)
        daily = _env_int("MEDBOT_DAILY_CAP", 200)
        now = time.monotonic()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._lock:
            if today != self._day:
                self._day, self._day_count = today, 0
            if daily > 0 and self._day_count >= daily:
                return ("Demo limit reached: this public demo has answered its "
                        f"{daily} questions for today. Please try again tomorrow (UTC), "
                        "or run it locally from the GitHub repo.")
            hits = self._hits.get(ip)
            if hits is not None:
                while hits and now - hits[0] >= window:
                    hits.popleft()
            if per_ip > 0 and window > 0 and hits is not None and len(hits) >= per_ip:
                wait_min = max(1, round((window - (now - hits[0])) / 60))
                return (f"Demo limit reached: {per_ip} questions per {round(window / 60)} minutes "
                        f"from one address. Please try again in about {wait_min} min.")
            if per_ip > 0 and window > 0:
                self._hits.setdefault(ip, deque()).append(now)
                if len(self._hits) > 10_000:  # bound memory: drop addresses with no recent hits
                    self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < window}
            self._day_count += 1
            return None


def client_ip(headers, fallback: str | None) -> str:
    fwd = headers.get("x-forwarded-for", "")
    first = fwd.split(",")[0].strip()
    return first or fallback or "unknown"


limiter = DemoLimiter()

"""Model-tier benchmark: which Nemotron tier (Nano / Super / Ultra) each
role needs. Live only (mock replies have no real latency or behaviour).

    python -m scripts.benchmark_tiers                      # all roles, all tiers
    python -m scripts.benchmark_tiers --roles router,safety
    python -m scripts.benchmark_tiers --limit 5            # first N cases per role (smoke run)

One role changes at a time; the others keep their configured models
(orchestrator/client.py), so a difference is that role's doing. Each role is
measured on the eval cases (eval/cases.jsonl) that exercise it:

  router        model routing on every non-emergency case, through route():
                pipeline routing accuracy (keyword / referral safety nets
                included, as in production), how often the keyword net had
                to add a missed organ, and fallbacks (invalid reply/timeout)
  safety        safety.check() on the paraphrased emergencies (recall) and
                every non-emergency case (false alarms); "unavailable" =
                error, timeout or unparseable reply
  agent         full pipeline on the cases that reach the specialists
  orchestrator  (single/multi-organ, risk tools): eval checks (routing,
                deferral, tool), grounding (final answer cites a retrieved
                source URL), errors (e.g. TruncatedReply at max_tokens)

Latency p50/p95 and tokens are per call of the role being varied. This
measures behaviour, not medical answer quality. The live web fallback is
switched off so every run sees the same inputs.

Results: eval/results/benchmark_<UTC timestamp>.json and a Markdown table.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone

os.environ["MEDBOT_WEB_FALLBACK"] = "0"

from eval.run import RESULTS_DIR, load_cases, observe, score  # noqa: E402
from orchestrator import client as llm  # noqa: E402
from orchestrator import router, safety  # noqa: E402

TIERS = {
    "nano": os.environ.get("NEMOTRON_NANO_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
    "super": os.environ.get("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
    "ultra": os.environ.get("NEMOTRON_ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b"),
}
ROLE_ATTR = {"router": "ROUTER_MODEL", "safety": "SAFETY_MODEL", "agent": "AGENT_MODEL",
             "orchestrator": "ORCHESTRATOR_MODEL"}
PIPELINE_CATEGORIES = {"single_organ", "multi_organ", "tool", "tool_out_of_range", "tool_guardrail"}


def pct(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile; None for no values."""
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s), max(1, math.ceil(q / 100 * len(s)))) - 1]


def summarize_calls(calls: list[dict]) -> dict:
    lat = [c["latency_ms"] for c in calls if c.get("latency_ms") is not None]
    tok = [c["tokens"] for c in calls if c.get("tokens") is not None]
    return {"calls": len(calls), "latency_p50_ms": pct(lat, 50), "latency_p95_ms": pct(lat, 95),
            "tokens_mean": round(statistics.mean(tok)) if tok else None}


def _rate(hits: int, total: int) -> dict:
    return {"value": round(hits / total, 4) if total else None, "hits": hits, "total": total}


def bench_router(cases: list[dict]) -> dict:
    rows, calls = [], []
    for c in cases:
        trace: list[dict] = []
        organs, method, reason = router.route(c["query"], trace)
        calls += [t | {"tokens": (t.get("usage") or {}).get("total_tokens")} for t in trace]
        rows.append({"id": c["id"], "expected": sorted(c["expected_agents"]), "got": sorted(organs),
                     "method": method, "keyword_added": "added by keyword match" in reason})
    return {"routing_accuracy": _rate(sum(r["got"] == r["expected"] for r in rows), len(rows)),
            "keyword_net_needed": sum(r["keyword_added"] for r in rows),
            "fallbacks": sum(r["method"] == "keyword_fallback" for r in rows),
            **summarize_calls(calls), "cases": rows}


def bench_safety(cases: list[dict]) -> dict:
    rows, calls = [], []
    for c in cases:
        r = safety.check(c["query"])
        if r.call:
            calls.append(r.call | {"tokens": (r.call.get("usage") or {}).get("total_tokens")})
        rows.append({"id": c["id"], "emergency_expected": c["category"] == "red_flag_paraphrase",
                     "status": r.status})
    para = [r for r in rows if r["emergency_expected"]]
    other = [r for r in rows if not r["emergency_expected"]]
    return {"paraphrase_recall": _rate(sum(r["status"] == "emergency" for r in para), len(para)),
            "false_alarms": _rate(sum(r["status"] == "emergency" for r in other), len(other)),
            "unavailable": sum(r["status"] == "unavailable" for r in rows),
            **summarize_calls(calls), "cases": rows}


def bench_pipeline(cases: list[dict], role: str) -> dict:
    step_of = {"agent": lambda s: s.endswith(" agent"), "orchestrator": lambda s: s == "Synthesis"}[role]
    rows, calls, e2e = [], [], []
    for c in cases:
        try:
            obs = observe(c)
        except Exception as e:  # keep going; an error is a result
            rows.append({"id": c["id"], "error": llm.redact(f"{type(e).__name__}: {e}")[:200]})
            continue
        checks = score(c, obs)
        calls += [k for k in obs["calls"] if step_of(k["step"])]
        e2e.append(obs["latency_ms"])
        rows.append({"id": c["id"], "checks_ok": all(checks.values()), "grounded": obs["grounded"],
                     "tokens_total": obs["tokens"], "latency_ms": obs["latency_ms"]})
    ok = [r for r in rows if "error" not in r]
    groundable = [r for r in ok if r["grounded"] is not None]
    return {"eval_checks": _rate(sum(r["checks_ok"] for r in ok), len(ok)),
            "grounding": _rate(sum(r["grounded"] for r in groundable), len(groundable)),
            "errors": len(rows) - len(ok),
            "end_to_end_p50_ms": pct(e2e, 50), "end_to_end_p95_ms": pct(e2e, 95),
            **summarize_calls(calls), "cases": rows}


def role_cases(role: str, cases: list[dict]) -> list[dict]:
    if role == "router":
        return [c for c in cases if c["expected_deferral"] != "red_flag"]
    if role == "safety":  # keyword red flags never reach the safety model
        return [c for c in cases if c["expected_deferral"] != "red_flag" or c["category"] == "red_flag_paraphrase"]
    return [c for c in cases if c["category"] in PIPELINE_CATEGORIES]


BENCH = {"router": bench_router, "safety": bench_safety,
         "agent": lambda cs: bench_pipeline(cs, "agent"),
         "orchestrator": lambda cs: bench_pipeline(cs, "orchestrator")}


def run(roles: list[str], tiers: list[str], limit: int | None) -> dict:
    cases = load_cases()
    defaults = {r: getattr(llm, a) for r, a in ROLE_ATTR.items()}
    out = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "defaults": defaults, "tiers": {t: TIERS[t] for t in tiers}, "results": {}}
    for role in roles:
        subset = role_cases(role, cases)[:limit] if limit else role_cases(role, cases)
        out["results"][role] = {}
        for tier in tiers:
            setattr(llm, ROLE_ATTR[role], TIERS[tier])
            start = time.perf_counter()
            print(f"[{role}] {tier} ({TIERS[tier]}) on {len(subset)} cases ...", flush=True)
            try:
                res = BENCH[role](subset)
            finally:
                setattr(llm, ROLE_ATTR[role], defaults[role])
            res["model"], res["wall_s"] = TIERS[tier], round(time.perf_counter() - start)
            out["results"][role][tier] = res
    return out


def _f(m: dict | None) -> str:
    return "n/a" if not m or m["value"] is None else f"{m['value'] * 100:.0f}% ({m['hits']}/{m['total']})"


def _ms(v) -> str:
    return "–" if v is None else f"{v / 1000:.1f} s"


def table(out: dict) -> str:
    lines = []
    for role, by_tier in out["results"].items():
        default = out["defaults"][role]
        lines += [f"\n**{role}** (configured: `{default}`)\n"]
        if role == "router":
            lines += ["| Tier | Routing accuracy | Keyword net needed | Fallbacks | p50 | p95 | Tokens/call |",
                      "| --- | --- | --- | --- | --- | --- | --- |"]
            lines += [f"| {t} | {_f(r['routing_accuracy'])} | {r['keyword_net_needed']} | {r['fallbacks']} | "
                      f"{_ms(r['latency_p50_ms'])} | {_ms(r['latency_p95_ms'])} | {r['tokens_mean'] or '–'} |"
                      for t, r in by_tier.items()]
        elif role == "safety":
            lines += ["| Tier | Paraphrase recall | False alarms | Unavailable | p50 | p95 | Tokens/call |",
                      "| --- | --- | --- | --- | --- | --- | --- |"]
            lines += [f"| {t} | {_f(r['paraphrase_recall'])} | {_f(r['false_alarms'])} | {r['unavailable']} | "
                      f"{_ms(r['latency_p50_ms'])} | {_ms(r['latency_p95_ms'])} | {r['tokens_mean'] or '–'} |"
                      for t, r in by_tier.items()]
        else:
            lines += ["| Tier | Eval checks | Grounding | Errors | Call p50 | Call p95 | Tokens/call | End-to-end p50 |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- |"]
            lines += [f"| {t} | {_f(r['eval_checks'])} | {_f(r['grounding'])} | {r['errors']} | "
                      f"{_ms(r['latency_p50_ms'])} | {_ms(r['latency_p95_ms'])} | {r['tokens_mean'] or '–'} | "
                      f"{_ms(r['end_to_end_p50_ms'])} |" for t, r in by_tier.items()]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m scripts.benchmark_tiers")
    parser.add_argument("--roles", default=",".join(BENCH), help="comma-separated: " + ", ".join(BENCH))
    parser.add_argument("--tiers", default=",".join(TIERS), help="comma-separated: " + ", ".join(TIERS))
    parser.add_argument("--limit", type=int, help="first N cases per role")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if llm.mock_enabled():
        sys.exit("Live only: run with MEDBOT_MOCK_LLM=0 (mock replies have no real latency or behaviour).")
    roles = [r for r in args.roles.split(",") if r]
    tiers = [t for t in args.tiers.split(",") if t]
    bad = [r for r in roles if r not in BENCH] + [t for t in tiers if t not in TIERS]
    if bad:
        sys.exit(f"unknown role/tier: {bad}")
    out = run(roles, tiers, args.limit)
    out["markdown"] = table(out)
    print(out["markdown"])
    if not args.no_save:
        RESULTS_DIR.mkdir(exist_ok=True)
        path = RESULTS_DIR / f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved {path.relative_to(RESULTS_DIR.parent.parent)}")


if __name__ == "__main__":
    main()

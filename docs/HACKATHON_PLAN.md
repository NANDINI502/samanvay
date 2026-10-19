# Hackathon plan (Nebius x NVIDIA)

Deadline: **30 Oct 2026, 1pm EDT**. Track: Best Apps and Agents.
This file is the source of truth for plan status, so a closed session never
loses it. Update the status column as steps finish.

Work one step at a time and stop for the owner's OK after each.

| Step | What | Status |
| --- | --- | --- |
| A | Positioning: Indian primary health centres, WHO PEN protocol (README, UI tagline/footer) | Done (mock mode) |
| B | Eval harness: `eval/run.py`, `eval/cases.jsonl` | Done (mock mode) |
| C | Hindi/Hinglish red flags (`guardrails/README.md`; needs native-speaker clinical review) | Done (mock mode) |
| D | One-way LLM safety check (`orchestrator/safety.py`): can only add a deferral, never remove one | Done (mock mode) |
| E | Nemotron router with keyword fallback (`orchestrator/router.py`) | Done (mock mode) |
| F | Health-worker mode in the UI (see below) | Not started (UI has D/E trace changes only) |
| — | Guardrail fix: "dil ka daura" / "दिल का दौरा" labelled "seizure"; map to "chest pain" | Pending |
| G | Live Nebius check | Blocked: needs a working Nebius key |
| H | Native tool calling | Blocked: needs key |
| I | Model-tier benchmark | Blocked: needs key |
| J | Nebius embeddings | Blocked: needs key |
| K | Tavily fallback | Blocked: needs key |
| L | Final live run, README, DEPLOY.md, commit | Blocked: needs key |

## Current session order

0. Save this plan; run `pytest tests/` and `python -m eval.run`; if both pass,
   commit everything so far (no push).
1. Finish F.
2. Guardrail fix for heart-attack phrases.
3. Commit, then wait for confirmation that the Nebius key works.

## Step details

**F. Health-worker mode.** Toggle "Clinician" (full detail, numbers,
sources) vs "Health worker" (simple language, Hindi or Hinglish option,
always ends with a clear next step / when to refer). Same engine, guardrails
and citations. Red-flag message in the chosen language. Pipeline trace
visible in both modes.

**Guardrail fix.** "dil ka daura" / "दिल का दौरा" defers correctly but is
labelled "seizure". Add a heart-attack translation mapped to "chest pain" so
the message is right. Keep everything else.

**G.** `scripts/check_nebius.py` → confirm Nemotron model IDs → update `.env`
and README → run CLI + eval live (also compare the two routers live).

**H. Native tool calling.** Test whether the confirmed Nemotron model
supports OpenAI-style `tools` on Token Factory. If yes, agents call
eGFR/FIB-4/cardiac tools themselves (our code still validates args and
guardrails run first); if not, strict-JSON tool requests. Re-run eval.

**I.** `scripts/benchmark_tiers.py`: eval with Nano/Super/Ultra per role
(router, safety, agent, orchestrator): latency p50/p95, tokens, eval
metrics; roles configurable per model; table + reasoning in README.

**J. Nebius embeddings.** `EMBED_BACKEND=nebius`, re-ingest, re-calibrate,
check the strict xfail; keep TF-IDF fallback.

**K. Tavily fallback** only on low retrieval confidence, restricted to
who.int / nih.gov / cdc.gov (verify include-domains in Tavily docs),
labelled "live web source", never bypasses guardrails; eval cases.

**L.** Full pytest + eval live, README results/eval tables, Nebius tools
used, `DEPLOY.md` for Nebius Serverless Endpoint, commit.

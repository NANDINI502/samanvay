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
| F | Health-worker mode in the UI (see below) | Done (mock mode); Hindi/Hinglish model answers untested until live |
| — | Guardrail fix: "dil ka daura" / "दिल का दौरा" labelled "seizure"; map to "chest pain" | Done |
| G | Live Nebius check | Done 2026-10-20: new key works; Ultra ID fixed; reasoning off for router/safety; keyword matches added to Nemotron routing; live eval `eval/results/20261020T070006Z.json` (all metrics 100%) |
| — | UI redesign v2 (three-column dashboard, history, voice input) | Done (commit 1883786) |
| 0 | Re-check 2026-10-24: `pytest tests/` 239 passed, 1 xfailed (expected); live eval `eval/results/20261024T064325Z.json` all metrics 100% (63 cases); committed the 21 Oct leftover fixes (TruncatedReply on max_tokens cut-off, default max_tokens 4000, stricter grounding prompts) | Done |
| 1 | Deploy (Nebius Serverless Endpoint, else free Docker host) | Next |
| K | Tavily fallback (step 2) | After 1 |
| I | Model-tier benchmark (step 3) | After K |
| H | Native tool calling (step 4) | Only if 1–3 done and ≥2 days left; else skip and say so in README |
| J | Nebius embeddings (step 5) | Skip unless everything else is done; keep TF-IDF |
| L | Final live run, README, leak check (step 6) | Last |

## Current session order (from 2026-10-24)

0. Check: git status/log, `pytest tests/`, live `python -m eval.run`; fix failures first.
1. Deploy → demo URL; check every "Try a case" in both audiences at phone width.
2. K — Tavily fallback.
3. I — tier benchmark.
4. H — native tool calling (conditional, see table).
5. J — skip unless everything else is done.
6. L — final run, README sections, leak check. Owner writes <FEEDBACK>, gives <DEMO_URL>/<GITHUB_REPO_URL>, and pushes.

One step at a time; commit after each; stop for the owner's OK. No pushing.
Note: `.env` sets `MEDBOT_MOCK_LLM` to a mock value; run the live eval with
`MEDBOT_MOCK_LLM=0 python -m eval.run` (load_dotenv never overrides the shell).

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

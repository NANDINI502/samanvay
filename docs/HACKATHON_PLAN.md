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
| 0 | Re-check 2026-10-24: `pytest tests/` 239 passed, 1 xfailed (expected); live eval `eval/results/20261024T064325Z.json` all metrics 100% (63 cases); committed the 21 Oct leftover fixes (TruncatedReply on max_tokens cut-off, default max_tokens 4000, stricter grounding prompts). Second re-check same day at 805b291: pytest 239 passed, 1 xfailed; live eval `eval/results/20261024T074922Z.json` all metrics 100% (63 cases, 0 errors) | Done |
| 1 | Deploy (Render free web service, Docker; owner keeps it awake with UptimeRobot on /api/health) | In progress: 2026-10-25 demo hardening done — /api/ask rate-limited (per-IP + daily cap, 429 "Demo limit reached" in UI), /api/health unlimited and model-free, MEDBOT_MAX_TOKENS_CAP on every call; memory peak 194 MB with one live question (Windows, cold index build ~185 MB); pytest 245 passed, 1 xfailed; live eval `eval/results/20261025T143339Z.json` all 100% (63 cases, 0 errors). Live at https://samanvay-z93y.onrender.com since 2026-10-26 (repo public, Render serves the pushed commit). 2026-10-27 status check: `/api/health` took 42.7 s (cold start), so UptimeRobot isn't keeping it awake yet; owner to fix |
| K | Tavily fallback (step 2) | Done offline 2026-10-25 (`rag/web.py`, tests/test_web_fallback.py, eval cases web-01/02/03; mock eval: web domain violations 0, multi-03 keyword-routing miss pre-existing in mock). Live 2026-10-25 with fallback on: `eval/results/20261025T152908Z.json` all metrics 100% (66 cases, 0 errors), web fallback 2/2, web domain violations 0; web-02 cited pmc.ncbi.nlm.nih.gov research articles (allowed domain, but papers, not guidance). Finding: with TF-IDF only 2 of 21 probed off-corpus questions fell below MIN_SCORE, so the fallback rarely fires |
| I | Model-tier benchmark (step 3) | Done 2026-10-25: `scripts/benchmark_tiers.py` (one role varied at a time; NEMOTRON_SAFETY_MODEL added so safety is its own role); live `eval/results/benchmark_20261025T161928Z.json`: every tier 100% on every behaviour check, 0 errors; Nano safety 2/37 false alarms, Nano router leans on the keyword net (4); Ultra agent fastest. Defaults kept; README table + reasoning |
| H | Native tool calling (step 4) | Skipped by owner's decision 2026-10-26; reason in README Known limitations |
| J | Nebius embeddings (step 5) | Skip unless everything else is done; keep TF-IDF |
| — | Care UI redesign + QA sweep | Done 2026-10-27 (`f818250`, `93fadcf`, `cef6681`; `docs/QA_REPORT.md`); red-flag variants (`62a6d14`), dead PAHO link replaced (`9eddf87`) |
| — | QA follow-ups (owner approved 2026-10-27) | Done 2026-10-27: O-7 rename in prompts + LICENSE (`e7df95d`); O-9 placeholder key (`1db8f0d`); HEAD on /api/health already in `93fadcf`, now tested; O-5 client IP from CF-Connecting-IP / last X-Forwarded-For, default 30/hour (`b73b71b`); O-2 eGFR input sanity checks (`a5cc8f1`); O-11 README Design + limitations (`092845e`). pytest 291 passed, 1 xfailed; live eval `eval/results/20261027T073020Z.json` on `092845e` all 100% (66 cases, 0 errors). Skipped by owner, documented: O-3, O-4, O-8, O-12, O-13. Draft `docs/DEVPOST.md` for owner to edit |
| L | Final live run, README, leak check (step 6) | Done 2026-10-26: pytest 274 passed, 1 xfailed; live eval `eval/results/20261026T095448Z.json` all 100% (66 cases, 0 errors); git history leak check clean; README eval table, web fallback, limitations, change list; UI "Live web source" case. Demo URL filled in. Left for owner: `<FEEDBACK>`, video, Devpost form, push. Feedback filled in by the owner and pushed 2026-10-28; video and Devpost form remain |

## Current session order (from 2026-10-24)

0. Check: git status/log, `pytest tests/`, live `python -m eval.run`; fix failures first.
1. Deploy (Render, DEPLOY.md R) → demo URL; check every "Try a case" in both audiences at phone width.
2. K — Tavily fallback.
3. I — tier benchmark.
4. H — native tool calling (conditional, see table).
5. J — skip unless everything else is done.
6. L — final run, README sections, leak check. Owner writes <FEEDBACK>, gives <DEMO_URL>/<GITHUB_REPO_URL>, and pushes. (Done 2026-10-28.)

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

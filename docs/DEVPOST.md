# Devpost draft — for the owner to edit

Draft text for the Devpost form. Every number below comes from a file in
this repo (named next to it); change the wording freely, but check any
number you change against its source. The feedback section is not here on
purpose: it goes in your own words (README, "Feedback on Nebius & NVIDIA
tools").

---

## Project name

Samanvay

## Tagline

Six specialists. One careful answer. Multi-agent clinical decision support
for India's primary health centres, on NVIDIA Nemotron and Nebius Token
Factory.

## Inspiration

In an Indian primary health centre, a health worker or a medical officer
sees blood pressure, diabetes, kidney, liver and lung problems without a
specialist on site. Their questions are practical: *what does this value
mean?* and *does this patient need referral now?* WHO wrote its PEN
protocol (Package of Essential Noncommunicable Disease Interventions) for
exactly this setting: primary care in low-resource settings. We wanted an
assistant that answers those questions from cited guidance, in Hindi or
Hinglish if needed, and that says "refer" instead of guessing.

## What it does

- You ask a clinical question in plain language, optionally with patient
  values. A Nemotron router picks the organ specialists the question needs
  (Cardiac, Renal, Neuro, Hepatic, Respiratory, Endocrine) and they run in
  parallel.
- Each specialist answers only from retrieved excerpts of its own curated
  corpus of WHO and NIH sources and cites the URLs. A Nemotron
  orchestrator combines their answers without adding new claims.
- Emergency red flags (English, Hindi, Hinglish) stop the request in code
  before any model call. Referral criteria and low retrieval confidence make
  an agent defer, and one deferral defers the whole answer.
- Published calculators run when you give the values: eGFR (2021 CKD-EPI,
  race-free) and FIB-4, plus a cardiac model trained on the UCI Cleveland
  dataset and clearly labelled as such. Missing values are asked for, never
  guessed. Implausible inputs (age over 120, creatinine that looks like
  µmol/L) are refused.
- Two modes, one engine: *Clinician* (full detail, English) and *Health
  worker* (simple language in English, Hindi or Hinglish, ending with a
  fixed "Next step" line). Only the wording changes.
- "How this answer was made" shows every step: whether code or a Nemotron
  call made it, with model, tier, latency and tokens.
- The web UI has read-aloud, voice input and history, and an interface in
  Hindi, Hinglish or English (some technical labels stay English).

## How we built it

- **Nemotron tiers on Nebius Token Factory.** All inference goes through
  Token Factory's OpenAI-compatible API, from one module
  (`orchestrator/client.py`). Nemotron 3 Ultra
  (`nvidia/Nemotron-3-Ultra-550b-a55b`) synthesizes the final answer;
  Nemotron 3 Super (`nvidia/nemotron-3-super-120b-a12b`) runs the
  specialists, the router and the safety check. Each role has its own
  environment variable.
- **Tier benchmark.** We varied one role at a time across Nano, Super and
  Ultra on the eval cases (`eval/results/benchmark_20261025T161928Z.json`).
  Every tier passed every behaviour check; Nano as the safety model raised
  2 false emergencies in 37 non-emergency cases, so the safety check stayed
  on Super, and Ultra stayed on synthesis as the fastest and steadiest
  tier there (p95 4.5 s).
- **Guardrails in code, not prompts.** Red flags, referral terms and
  retrieval confidence are deterministic Python (`guardrails/checks.py`).
  One extra Nemotron call is a **one-way** safety check: it can turn an
  answer into an emergency deferral, never remove one, and any error or
  malformed reply leaves the code's decision standing.
- **Router with safety nets.** Nemotron returns strict JSON validated
  against the agent registry; keyword routing is the fallback, and every
  organ whose referral term appears is always consulted.
- **Agents.** One specialist class configured per organ, with RAG over
  FAISS + TF-IDF on curated, cited corpora. Each corpus lists what it does
  not cover, and the agent is told those limits.
- **Tavily live web fallback.** Only when an agent's corpus has no confident
  match: Tavily search restricted to who.int, nih.gov and cdc.gov (plus a
  host check in code), labelled "Live web source". It never answers
  anything the guardrails stopped, and risk tools don't run on web answers.
- **Behaviour eval.** 66 self-written cases scoring what the system did
  (which agents ran, deferral, tool choice, citations), not medical wording.
  Final live run (`eval/results/20261027T073020Z.json`): routing 37/37,
  red flags 19/19 (English, Hindi, Hinglish), paraphrased emergencies 10/10,
  safety false alarms 0/37, referrals 10/10, grounding 24/24, 0 errors.
  These are self-written behaviour tests, not clinical validation.
- **Deploy.** FastAPI + a single static page, in Docker on Render's free
  tier, with a per-IP limit and a daily cap so a public URL can't drain
  Token Factory credits.

## Challenges we ran into

- **Reasoning tokens.** Nemotron 3 reasons before it answers, and the
  reasoning counts against `max_tokens`. Short strict-JSON calls (router,
  safety) got cut off until we turned reasoning off for them; we also added
  a guard for answers truncated at the limit.
- **Routing.** Live, Nemotron consistently left Cardiac out of *"Diabetic
  patient with eGFR 50 — what blood pressure threshold applies?"*, while
  keywords miss plurals and paraphrases. Combining both (keywords add what
  the router left out) fixed both cases.
- **Keyword red flags are brittle.** Our QA probe of 49 odd phrasings found
  the keyword layer missed spacing, apostrophe and word-form variants. After
  normalisation it catches 38 of 49; the rest (typos, paraphrases, mixed
  script) are left to the one-way safety check, which caught every one
  tested live.
- **Grounding.** Agents sometimes drew conclusions their excerpts didn't
  state. Stricter prompts made it rarer; the eval checks that sources are
  cited, not that every sentence is supported, and we say so.
- **Honest models.** Two trained models looked great and were wrong: a UCI
  kidney model with AUC 1.00 (suspected label leakage) and a liver model
  with specificity 0.22. We retired both, replaced them with published
  equations (eGFR, FIB-4), and kept them in the repo as documented negative
  results.

## Accomplishments that we're proud of

- Safety that doesn't depend on the prompt: an emergency stops before any
  model call, and the AI can only make the system more cautious.
- A transparent multi-agent pipeline: every step shows its model, tier,
  latency and tokens.
- A health-worker mode in Hindi and Hinglish with read-aloud, aimed at the
  people PEN was written for.
- Honest documentation: eval labelled as behaviour tests, not clinical
  validation; negative results kept; limitations listed.

## What we learned

- On Token Factory in our runs, bigger was not slower: Ultra agents were
  faster than Nano agents at similar tokens per call (one run; see the
  README tier benchmark).
- Deterministic code and a model work best together when the model's power
  is one-directional: it may add caution, never remove it.
- Mock tests weren't enough: the first live runs found a wrong Ultra model
  ID, router and safety replies cut off by reasoning tokens, and the router
  dropping Cardiac, none of which the offline tests could show.

## What's next

- Native-speaker clinical review of the Hindi/Hinglish red flags and
  messages.
- Semantic retrieval (Nebius embeddings) in place of TF-IDF, re-calibrated.
- A "not covered by the sources" card, and relevance checks on web sources.
- Native tool calling for the risk tools, with code still validating
  arguments.
- A pilot conversation with a primary health centre before any real use.
  Samanvay is a prototype, not a medical device.

## Built with

python · fastapi · uvicorn · pydantic · nvidia-nemotron · nebius-token-factory
· openai-python-sdk · faiss · scikit-learn · pandas · numpy · tavily ·
docker · render · html · css · javascript · web-speech-api · pytest

## Links

- Demo: https://samanvay-z93y.onrender.com
- Code: https://github.com/NANDINI502/samanvay
- Video: `<YOUTUBE_URL>` (yours)
- Track: Best Apps and Agents

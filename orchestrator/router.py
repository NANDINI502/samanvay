"""Orchestrator: routes a query to one or more specialist agents, runs them in
parallel, and asks the Ultra-tier model to synthesize one answer.

Routing, in order:
  1. Global red-flag check before anything else — an emergency symptom gets
     an immediate referral answer, no agents, no model call.
  1b. One-way Nemotron safety check (orchestrator/safety.py), in parallel
     with steps 2-4 and the agents: it can only add an emergency deferral
     for warning signs the keywords missed. Its result is in before any
     answer is returned or synthesized; on error the keyword result stands.
  2. Nemotron router (router tier, MEDBOT_ROUTER=nemotron, the default):
     strict JSON {"organs": [...], "reason": "..."} validated against the
     registry. On error, timeout or an invalid reply -> keyword routing
     (word-boundary match on each organ's routing_keywords). Mock mode and
     MEDBOT_ROUTER=keyword use keyword routing directly. When the Nemotron
     router succeeds, keyword matches it left out are added too: live, it
     consistently dropped cardiac from "diabetic patient with eGFR 50, what
     blood pressure threshold applies?" (eval multi-01), while keywords miss
     what it catches (plurals, paraphrases; multi-03).
  3. Referral safety net, whichever router ran: every organ whose referral
     term appears in the query is consulted too, so its referral rule
     always runs. Routing can add agents here, never remove them.
  4. Still nothing: ask the user to clarify which body system the question
     is about, instead of guessing.

Aggregation rules (safety first):
  - Any agent deferring for a red flag or referral → the whole answer defers.
  - An agent deferring only for low retrieval confidence → the other agents'
    answers are still synthesized, and the gap is stated explicitly.
"""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from agents.registry import AGENT_CONFIGS, ORGANS
from agents.specialist import AgentResponse, SpecialistAgent
from guardrails.checks import GLOBAL_RED_FLAGS, check_red_flags, find_keyword
from models.tool import RiskResult, is_requested
from orchestrator import audience as aud
from orchestrator import safety
from orchestrator.client import chat_as_orchestrator, chat_as_router, mock_enabled, redact

AGENTS = {organ: SpecialistAgent(organ) for organ in ORGANS}


@dataclass
class OrchestratorResponse:
    query: str
    agents_consulted: list[str]
    routing_method: str  # "nemotron" | "keyword" | "keyword_fallback" | "red_flag" | "safety_model"
    final_answer: str
    routing_reason: str = ""
    deferred: bool = False
    needs_clarification: bool = False
    agent_answers: dict[str, AgentResponse] = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)  # orchestrator-level model calls (safety, routing, synthesis)
    safety: dict | None = None  # orchestrator/safety.py result; None when a keyword red flag stopped the query
    audience: str = "clinician"  # orchestrator/audience.py: wording only, never the decisions
    language: str = "en"


ROUTER_TIMEOUT_S = float(os.environ.get("MEDBOT_ROUTER_TIMEOUT_S", "10"))

ROUTER_PROMPT = (
    "You route clinical questions to specialist agents. The question may be in English, "
    "Hindi or Hinglish. Agents:\n"
    + "\n".join(f"- {o}: {cfg['scope']}" for o, cfg in AGENT_CONFIGS.items())
    + "\nPick every agent whose scope covers any part of the question (several if it spans "
    "organs or mentions several conditions), or none if no agent fits (for example, not a "
    "clinical question). Reply with ONLY this JSON, nothing "
    'else: {"organs": ["<agent name>", ...], "reason": "<one short line>"}'
)


def router_mode() -> str:
    return os.environ.get("MEDBOT_ROUTER", "nemotron").lower()


def keyword_route(query: str) -> list[str]:
    return [o for o, cfg in AGENT_CONFIGS.items() if find_keyword(query, cfg["routing_keywords"])]


def _keyword_reason(organs: list[str], query: str) -> str:
    if not organs:
        return "no routing keyword matched"
    return "keyword match: " + ", ".join(
        f"{o} ('{find_keyword(query, AGENT_CONFIGS[o]['routing_keywords'])}')" for o in organs)


def parse_route(text: str) -> tuple[list[str], str]:
    """Strict: a JSON object whose "organs" is a list of registry names (no
    unknown names). Raises ValueError otherwise."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("no JSON object in reply")
    data = json.loads(match.group(0))
    organs = data.get("organs") if isinstance(data, dict) else None
    if not isinstance(organs, list) or not all(isinstance(o, str) for o in organs):
        raise ValueError('"organs" is not a list of names')
    unknown = [o for o in organs if o not in AGENT_CONFIGS]
    if unknown:
        raise ValueError(f"unknown agents {unknown}")
    return list(dict.fromkeys(organs)), str(data.get("reason") or "").strip()


def model_route(query: str, calls: list[dict] | None = None) -> tuple[list[str], str]:
    """Nemotron router. Raises on any failure; the caller falls back."""
    messages = [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": query}]
    result = chat_as_router(messages, max_tokens=120, temperature=0, timeout=ROUTER_TIMEOUT_S, thinking=False)
    if calls is not None:
        calls.append(result.trace("Routing"))
    return parse_route(result.text)


def referral_organs(query: str) -> list[str]:
    return [o for o, cfg in AGENT_CONFIGS.items() if find_keyword(query, cfg["referral_keywords"])]


def route(query: str, calls: list[dict] | None = None) -> tuple[list[str], str, str]:
    """(organs, method, reason). See the module docstring for the order."""
    if router_mode() == "nemotron" and not mock_enabled():
        try:
            organs, reason = model_route(query, calls)
            method = "nemotron"
            missed = [o for o in keyword_route(query) if o not in organs]
            if missed:
                organs = organs + missed
                reason += "; added by keyword match: " + ", ".join(
                    f"{o} ('{find_keyword(query, AGENT_CONFIGS[o]['routing_keywords'])}')" for o in missed)
        except Exception as e:
            organs = keyword_route(query)
            method = "keyword_fallback"
            reason = (f"Nemotron router unavailable ({redact(f'{type(e).__name__}: {e}')[:120]}); "
                      + _keyword_reason(organs, query))
    else:
        organs = keyword_route(query)
        method = "keyword"
        reason = _keyword_reason(organs, query) + (" (mock mode: Nemotron router not called)"
                                                   if mock_enabled() and router_mode() == "nemotron" else "")
    added = [o for o in referral_organs(query) if o not in organs]
    if added:
        organs = organs + added
        reason += "; added so their referral rule runs: " + ", ".join(added)
    return organs, method, reason


def risk_notes(responses: dict[str, AgentResponse], patient_values: dict | None) -> str:
    """Deterministic risk-tool block appended to the final answer, so the
    result's disclaimer and any request for missing values reach the user
    no matter what the synthesis model writes."""
    lines = []
    for o, r in responses.items():
        if r.risk:
            lines.append("- " + RiskResult(**r.risk).summary())
        elif r.deferred and AGENT_CONFIGS[o].get("risk_model") and is_requested(o, patient_values):
            lines.append(f"- {AGENT_CONFIGS[o]['display_name']} risk tool not run: the agent deferred ({r.reason})")
    return "\n\nRisk tool:\n" + "\n".join(lines) if lines else ""


def handle_query(query: str, patient_values: dict | None = None,
                 audience: str = "clinician", language: str = "en") -> OrchestratorResponse:
    """`patient_values`: optional risk-tool inputs, e.g. {"age": 63, "sex":
    "male", "serum_creatinine": 1.1}; keys per models/tool.required_inputs().
    Only routed agents with a risk tool use them.
    `audience` / `language` (orchestrator/audience.py) change only the
    wording of the final answer; every decision above is the same."""
    audience, language = aud.normalize(audience, language)
    r = _handle(query, patient_values, audience, language)
    r.audience, r.language = audience, language
    return r


def _handle(query: str, patient_values: dict | None, audience: str, language: str) -> OrchestratorResponse:
    red = check_red_flags(query)
    if not red.allowed:
        return OrchestratorResponse(
            query=query, agents_consulted=[], routing_method="red_flag",
            final_answer=aud.red_flag_message(audience, language, red.matched, red.reason),
            deferred=True,
        )

    calls: list[dict] = []
    with ThreadPoolExecutor(max_workers=1) as safety_pool:
        safety_future = safety_pool.submit(safety.check, query)
        organs, method, reason = route(query, calls)
        responses, agent_error = {}, None
        if organs:
            try:
                with ThreadPoolExecutor(max_workers=len(organs)) as pool:
                    responses = dict(zip(organs, pool.map(
                        lambda o: AGENTS[o].run(query, patient_values=patient_values), organs)))
            except Exception as e:  # an emergency found by the safety check still wins
                agent_error = e
        check = safety_future.result()
    if check.call:
        calls.insert(0, check.call)
    if check.emergency:
        # The agents' answers are dropped so no ordinary answer sits beside the
        # urgent one; their model calls stay in the trace for cost transparency.
        calls += [{**r.call, "step": r.call["step"] + " (discarded: safety deferral)"}
                  for r in responses.values() if r.call]
        sign = check.sign if check.sign in GLOBAL_RED_FLAGS else None
        return OrchestratorResponse(
            query=query, agents_consulted=organs, routing_method="safety_model", routing_reason=reason,
            final_answer=aud.safety_message(audience, language, sign),
            deferred=True, calls=calls, safety=check.to_dict(),
        )
    if agent_error:
        raise agent_error

    if not organs:
        names = ", ".join(cfg["display_name"] for cfg in AGENT_CONFIGS.values())
        return OrchestratorResponse(
            query=query, agents_consulted=[], routing_method=method, routing_reason=reason,
            final_answer=aud.clarify_message(audience, language, names),
            needs_clarification=True, calls=calls, safety=check.to_dict(),
        )

    hard_defers = [r for r in responses.values() if r.deferred and r.defer_kind in {"red_flag", "referral"}]
    if hard_defers:
        reasons = "; ".join(f"{AGENT_CONFIGS[r.organ]['display_name']}: {r.reason}" for r in hard_defers)
        return OrchestratorResponse(
            query=query, agents_consulted=organs, routing_method=method, routing_reason=reason,
            final_answer=aud.referral_message(audience, language, [r.trigger for r in hard_defers], reasons),
            deferred=True, agent_answers=responses, calls=calls, safety=check.to_dict(),
        )

    answered = {o: r for o, r in responses.items() if not r.deferred}
    gaps = [o for o, r in responses.items() if r.deferred]
    if not answered:
        return OrchestratorResponse(
            query=query, agents_consulted=organs, routing_method=method, routing_reason=reason,
            final_answer=aud.no_grounding_message(audience, language, risk_notes(responses, patient_values)),
            deferred=True, agent_answers=responses, calls=calls, safety=check.to_dict(),
        )

    combined = "\n\n".join(
        f"[{AGENT_CONFIGS[o]['display_name']} agent]\n{r.answer}\nSources: {', '.join(r.citations)}"
        + (f"\nRisk tool output: {RiskResult(**r.risk).summary()}" if r.risk else "")
        for o, r in answered.items()
    )
    gap_note = ""
    if gaps:
        gap_note = ("\n\nThese agents had no confident grounding and gave no answer: "
                    + ", ".join(AGENT_CONFIGS[o]["display_name"] for o in gaps)
                    + ". Say so plainly in the final answer.")
    messages = [
        {"role": "system", "content": aud.synthesis_prompt(audience, language)},
        {"role": "user", "content": f"Query: {query}\n\nSpecialist answers:\n{combined}{gap_note}"},
    ]
    synthesis = chat_as_orchestrator(messages)
    calls.append(synthesis.trace("Synthesis"))
    final = synthesis.text + risk_notes(responses, patient_values) + aud.answered_suffix(audience, language)
    return OrchestratorResponse(
        query=query, agents_consulted=organs, routing_method=method, routing_reason=reason,
        final_answer=final, agent_answers=responses, calls=calls, safety=check.to_dict(),
    )

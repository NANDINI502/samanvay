"""Orchestrator: routes a query to one or more specialist agents, runs them in
parallel, and asks the Ultra-tier model to synthesize one answer.

Routing, in order:
  1. Global red-flag check before anything else — an emergency symptom gets
     an immediate referral answer, no agents, no model call.
  2. Keyword routing (word-boundary match on each organ's routing_keywords).
  3. If no keyword matches: a Nemotron router call picks organs from the
     registry (skipped in mock mode).
  4. Still nothing: ask the user to clarify which body system the question
     is about, instead of guessing.

Aggregation rules (safety first):
  - Any agent deferring for a red flag or referral → the whole answer defers.
  - An agent deferring only for low retrieval confidence → the other agents'
    answers are still synthesized, and the gap is stated explicitly.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from agents.registry import AGENT_CONFIGS, ORGANS
from agents.specialist import AgentResponse, SpecialistAgent
from guardrails.checks import check_red_flags, find_keyword
from models.tool import RiskResult, is_requested
from orchestrator.client import chat_as_agent, chat_as_orchestrator, mock_enabled

AGENTS = {organ: SpecialistAgent(organ) for organ in ORGANS}


@dataclass
class OrchestratorResponse:
    query: str
    agents_consulted: list[str]
    routing_method: str
    final_answer: str
    deferred: bool = False
    needs_clarification: bool = False
    agent_answers: dict[str, AgentResponse] = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)  # orchestrator-level model calls (routing, synthesis)


def keyword_route(query: str) -> list[str]:
    return [o for o, cfg in AGENT_CONFIGS.items() if find_keyword(query, cfg["routing_keywords"])]


def model_route(query: str, calls: list[dict] | None = None) -> list[str]:
    """Ask Nemotron (agent tier) which organ agents fit. Returns [] on any
    failure — the caller then asks the user to clarify. The call's trace is
    appended to `calls`."""
    if mock_enabled():
        return []
    options = ", ".join(f"{o} ({cfg['scope']})" for o, cfg in AGENT_CONFIGS.items())
    messages = [
        {"role": "system", "content": (
            "You route clinical questions to specialist agents. Reply with ONLY a "
            f"JSON list of agent names chosen from: {options}. Reply [] if none fit."
        )},
        {"role": "user", "content": query},
    ]
    try:
        result = chat_as_agent(messages, max_tokens=50, temperature=0)
        if calls is not None:
            calls.append(result.trace("Routing"))
        text = result.text
        match = re.search(r"\[.*?\]", text, re.S)
        picked = json.loads(match.group(0)) if match else []
        return [o for o in picked if o in AGENT_CONFIGS]
    except Exception:
        return []


def route(query: str, calls: list[dict] | None = None) -> tuple[list[str], str]:
    organs = keyword_route(query)
    if organs:
        return organs, "keyword"
    organs = model_route(query, calls)
    if organs:
        return organs, "model"
    return [], "none"


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


def handle_query(query: str, patient_values: dict | None = None) -> OrchestratorResponse:
    """`patient_values`: optional risk-tool inputs, e.g. {"age": 63, "sex":
    "male", "serum_creatinine": 1.1}; keys per models/tool.required_inputs().
    Only routed agents with a risk tool use them."""
    red = check_red_flags(query)
    if not red.allowed:
        return OrchestratorResponse(
            query=query, agents_consulted=[], routing_method="red_flag",
            final_answer=f"Urgent: {red.reason} Contact emergency services or go to the nearest emergency department.",
            deferred=True,
        )

    calls: list[dict] = []
    organs, method = route(query, calls)
    if not organs:
        names = ", ".join(cfg["display_name"] for cfg in AGENT_CONFIGS.values())
        return OrchestratorResponse(
            query=query, agents_consulted=[], routing_method=method,
            final_answer=(
                "I couldn't tell which body system this question is about. "
                f"Could you rephrase it with the relevant area? Covered: {names}."
            ),
            needs_clarification=True, calls=calls,
        )

    with ThreadPoolExecutor(max_workers=len(organs)) as pool:
        responses = dict(zip(organs, pool.map(
            lambda o: AGENTS[o].run(query, patient_values=patient_values), organs)))

    hard_defers = [r for r in responses.values() if r.deferred and r.defer_kind in {"red_flag", "referral"}]
    if hard_defers:
        reasons = "; ".join(f"{AGENT_CONFIGS[r.organ]['display_name']}: {r.reason}" for r in hard_defers)
        return OrchestratorResponse(
            query=query, agents_consulted=organs, routing_method=method,
            final_answer=f"Deferring to clinician review. {reasons}",
            deferred=True, agent_answers=responses, calls=calls,
        )

    answered = {o: r for o, r in responses.items() if not r.deferred}
    gaps = [o for o, r in responses.items() if r.deferred]
    if not answered:
        return OrchestratorResponse(
            query=query, agents_consulted=organs, routing_method=method,
            final_answer=(
                "None of the consulted agents' source material clearly covers this "
                "question, so I won't guess. Please consult a clinician."
            ) + risk_notes(responses, patient_values),
            deferred=True, agent_answers=responses, calls=calls,
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
        {"role": "system", "content": (
            "You are the Orchestrator in MedBot Orchestrator. Combine the specialist "
            "answers below into one clear response for a clinician. Do not add any "
            "medical claim the agents did not make. Where agents' answers interact "
            "(e.g. diabetes changing a blood-pressure threshold), point that out only "
            "if both answers support it. Keep the sources and end with a reminder "
            "that this supports, and does not replace, clinical judgment. Report any "
            "risk-tool result (calculator value or model estimate) separately from "
            "guideline rules, with its disclaimer."
        )},
        {"role": "user", "content": f"Query: {query}\n\nSpecialist answers:\n{combined}{gap_note}"},
    ]
    synthesis = chat_as_orchestrator(messages)
    calls.append(synthesis.trace("Synthesis"))
    final = synthesis.text + risk_notes(responses, patient_values)
    return OrchestratorResponse(
        query=query, agents_consulted=organs, routing_method=method,
        final_answer=final, agent_answers=responses, calls=calls,
    )

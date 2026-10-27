"""Generic organ-specialist agent. One class, configured per organ from
agents/registry.py.

Flow per query:
  1. Retrieve grounded chunks from this organ's index (rag/retrieve.py)
  2. Run guardrails (global red flags, organ referral terms, retrieval
     confidence)
  3. Allowed → if the agent has a risk tool (models/tool.py) and the
     user supplied values for it, run the tool; then call Nemotron (agent
     tier) with the retrieved chunks and the tool output only
     Not allowed → return a deferral with the reason; never fall through to
     an ungrounded model answer, and never run the risk tool
  4. Only for a low-confidence deferral, and only when the live web fallback
     is on (rag/web.py): search WHO / NIH / CDC pages; if any are found,
     answer from those excerpts alone, labelled as a live web source. Red
     flags and referrals never get here, and the risk tool still doesn't run.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agents.registry import AGENT_CONFIGS
from guardrails.checks import run_guardrails
from models.tool import estimate, is_requested
from orchestrator.client import chat_as_agent
from rag import web
from rag.retrieve import corpus_limits, retrieve

SYSTEM_PROMPT_TEMPLATE = """You are the {display_name} specialist agent in \
Samanvay, a clinical decision-support tool. Your scope: {scope}
Answer ONLY from the source excerpts given as context. Do not use outside \
medical knowledge, and draw no conclusion the excerpts do not state (for \
example, a cause or effect from a testing rule). If the context does not \
clearly answer the question, say so explicitly instead of guessing. Name the protocol rule or threshold your \
answer rests on. End with one line reminding the reader that this supports, \
and does not replace, clinical judgment."""

RISK_TOOL_PROMPT = """

A risk-tool output may follow the question: either a published calculator \
result or a model estimate. If it gives a result, report it as a separate \
point after the guideline answer, with its interpretation and disclaimer \
exactly as given, and never let it override a guideline rule or present it \
as a diagnosis. If it says values are missing or invalid, ask the user for \
exactly those values and do not calculate or estimate anything yourself."""

WEB_PROMPT = """

The curated source material had no confident match for this question, so \
the excerpts below are from a live web search limited to WHO, NIH and CDC \
pages. They were not reviewed for this tool. Use them under the same rules: \
answer only from what they state, name the page (URL) each point comes \
from, and say plainly that this is a live web source, not the tool's \
reviewed guidance."""


@dataclass
class AgentResponse:
    organ: str
    deferred: bool
    answer: str
    reason: str | None = None
    defer_kind: str | None = None
    trigger: str | None = None  # red flag / referral deferrals: the phrase found in the query
    citations: list[str] = field(default_factory=list)
    retrieved_headings: list[str] = field(default_factory=list)
    risk: dict | None = None  # models.tool.RiskResult.to_dict(), when the risk tool ran
    source: str = "corpus"  # "corpus" | "live_web" (rag/web.py fallback)
    web_sources: list[dict] = field(default_factory=list)  # [{"title", "url"}] when source == "live_web"
    web_error: str | None = None  # why the web fallback found nothing usable (redacted)
    call: dict | None = None  # ChatResult.trace(): model, role, latency, tokens; None if no model call


class SpecialistAgent:
    def __init__(self, organ: str):
        if organ not in AGENT_CONFIGS:
            raise ValueError(f"Unknown organ '{organ}'. Known: {list(AGENT_CONFIGS)}")
        self.organ = organ
        self.config = AGENT_CONFIGS[organ]
        self.system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            display_name=self.config["display_name"], scope=self.config["scope"]
        )

    def run(self, query: str, top_k: int = 3, patient_values: dict | None = None) -> AgentResponse:
        results = retrieve(self.organ, query, top_k=top_k)
        guard = run_guardrails(query, results, self.config["referral_keywords"])
        headings = [r["heading"] for r in results]

        if not guard.allowed:
            web_error = None
            if guard.kind == "low_confidence" and web.enabled():
                hits, web_error = web.search(query)
                if hits:
                    return self._answer_from_web(query, hits, headings)
                web_error = web_error or "no WHO / NIH / CDC result"
            return AgentResponse(
                organ=self.organ,
                deferred=True,
                answer=f"Deferring to clinician review. Reason: {guard.reason}",
                reason=guard.reason,
                defer_kind=guard.kind,
                trigger=guard.matched,
                retrieved_headings=headings,
                web_error=web_error,
            )

        risk = None
        if self.config.get("risk_model") and is_requested(self.organ, patient_values):
            risk = estimate(self.organ, patient_values)

        context = "\n\n".join(f"### {r['heading']}\n{r['body']}" for r in results)
        limits = corpus_limits(self.organ)
        system = self.system_prompt + (f"\n\nWhat your source material does NOT cover:\n{limits}" if limits else "")
        user = f"Context:\n{context}\n\nQuestion: {query}"
        if risk:
            system += RISK_TOOL_PROMPT
            user += f"\n\nRisk tool output:\n{risk.summary()}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        result = chat_as_agent(messages)
        return AgentResponse(
            organ=self.organ,
            deferred=False,
            answer=result.text,
            citations=results[0]["sources"] if results else [],
            retrieved_headings=headings,
            risk=risk.to_dict() if risk else None,
            call=result.trace(f"{self.config['display_name']} agent"),
        )

    def _answer_from_web(self, query: str, hits: list[dict], headings: list[str]) -> AgentResponse:
        context = "\n\n".join(f"### {h['title'] or h['url']}\nURL: {h['url']}\n{h['content']}" for h in hits)
        messages = [
            {"role": "system", "content": self.system_prompt + WEB_PROMPT},
            {"role": "user", "content": f"Context ({web.LABEL}):\n{context}\n\nQuestion: {query}"},
        ]
        result = chat_as_agent(messages)
        return AgentResponse(
            organ=self.organ,
            deferred=False,
            answer=result.text,
            citations=[h["url"] for h in hits],
            retrieved_headings=headings,
            source="live_web",
            web_sources=[{"title": h["title"], "url": h["url"]} for h in hits],
            call=result.trace(f"{self.config['display_name']} agent ({web.LABEL.lower()})"),
        )

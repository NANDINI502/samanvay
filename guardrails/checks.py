"""Deterministic guardrail layer.

Design carried over from MedBot: the system must defer instead of
hallucinating a diagnosis or recommendation when it doesn't have enough
grounded support. This is checked in code, not left to the model, so it
can't be prompted away.

Three independent triggers, in order:
  1. Global red flags — emergency symptoms that must be referred no matter
     which agent the query lands on (e.g. chest pain, stroke signs).
  2. Organ-specific referral terms — from each organ's source protocol
     (agents/registry.py).
  3. Retrieval confidence — if the best matching chunk scores below
     MIN_RETRIEVAL_SCORE, the corpus doesn't cover the query.

All keyword checks use word boundaries, so "tia" does not fire on
"initial" or "potential".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rag.embed import MIN_SCORE  # per-backend threshold; see rag/embed.py + rag/calibrate.py

GLOBAL_RED_FLAGS = [
    "chest pain",
    "face droop", "facial droop", "slurred speech", "arm weakness",
    "sudden weakness", "sudden numbness", "worst headache",
    "can't breathe", "cannot breathe", "unable to speak", "blue lips", "bluish lips",
    "vomiting blood", "black stool", "coughing blood",
    "unconscious", "seizure", "fainted", "collapse", "collapsed",
    "confusion", "confused",
]


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    kind: str | None = None  # "red_flag" | "referral" | "low_confidence"


def find_keyword(text: str, keywords: list[str]) -> str | None:
    lowered = text.lower()
    for kw in keywords:
        pattern = r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, lowered):
            return kw
    return None


def check_red_flags(query: str) -> GuardrailResult:
    hit = find_keyword(query, GLOBAL_RED_FLAGS)
    if hit:
        return GuardrailResult(
            allowed=False,
            kind="red_flag",
            reason=(
                f"Query mentions '{hit}', an emergency warning sign — this needs "
                "urgent in-person medical assessment, not an automated answer."
            ),
        )
    return GuardrailResult(allowed=True)


def check_referral_flags(query: str, referral_keywords: list[str]) -> GuardrailResult:
    hit = find_keyword(query, referral_keywords)
    if hit:
        return GuardrailResult(
            allowed=False,
            kind="referral",
            reason=(
                f"Query mentions '{hit}', which the source protocol lists as a "
                "referral criterion — this needs specialist assessment."
            ),
        )
    return GuardrailResult(allowed=True)


def check_retrieval_confidence(results: list[dict]) -> GuardrailResult:
    if not results:
        return GuardrailResult(allowed=False, kind="low_confidence",
                               reason="No matching guidance found in the corpus for this query.")
    best = max(r["score"] for r in results)
    threshold = MIN_SCORE[results[0]["backend"]]
    if best < threshold:
        return GuardrailResult(
            allowed=False,
            kind="low_confidence",
            reason=(
                f"Best retrieval match ({best:.2f}) is below the confidence "
                f"threshold ({threshold}) — the source material doesn't clearly "
                "cover this query."
            ),
        )
    return GuardrailResult(allowed=True)


def run_guardrails(query: str, retrieval_results: list[dict],
                   referral_keywords: list[str] | None = None) -> GuardrailResult:
    for check in (
        lambda: check_red_flags(query),
        lambda: check_referral_flags(query, referral_keywords or []),
        lambda: check_retrieval_confidence(retrieval_results),
    ):
        result = check()
        if not result.allowed:
            return result
    return GuardrailResult(allowed=True)

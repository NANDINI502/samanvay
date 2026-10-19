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
"initial" or "potential". A keyword ending in "*" matches as a prefix
("behosh*" also matches "behoshi").

Red flags are also checked in Hindi (Devanagari) and Romanised Hinglish.
Every such phrase is a translation of one English red flag above it
(TRANSLATED_RED_FLAGS; reviewed side by side in guardrails/README.md). The
translations only add matches: the English list is checked exactly as
before.
"""
from __future__ import annotations

import re
import unicodedata
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

# English red flag -> Hindi (Devanagari) and Romanised Hinglish translations.
# Hinglish phrases use the canonical spellings of HINGLISH_SPELLINGS.
TRANSLATED_RED_FLAGS: dict[str, dict[str, list[str]]] = {
    "chest pain": {
        "hi": ["सीने में दर्द", "छाती में दर्द"],
        "hinglish": ["seene mein dard", "chhati mein dard"],
    },
    "facial droop": {
        "hi": ["चेहरा टेढ़ा", "मुँह टेढ़ा"],
        "hinglish": ["chehra tedha", "munh tedha", "chehra latak*"],
    },
    "slurred speech": {
        "hi": ["ज़बान लड़खड़ा", "आवाज़ लड़खड़ा"],
        "hinglish": ["zaban ladkhad*", "awaaz ladkhad*"],
    },
    "arm weakness": {
        "hi": ["बाँह में कमज़ोरी", "हाथ में कमज़ोरी"],
        "hinglish": ["baanh mein kamzori", "haath mein kamzori"],
    },
    "sudden weakness": {
        "hi": ["अचानक कमज़ोरी"],
        "hinglish": ["achanak kamzori"],
    },
    "sudden numbness": {
        "hi": ["अचानक सुन्न"],
        "hinglish": ["achanak sunn"],
    },
    "worst headache": {
        "hi": ["सबसे तेज़ सिरदर्द", "सबसे तेज़ सिर दर्द", "सबसे बुरा सिरदर्द"],
        "hinglish": ["sabse tez sirdard", "sabse tez sir dard", "sabse bura sirdard"],
    },
    "can't breathe": {
        "hi": ["साँस नहीं आ", "साँस नहीं ले पा", "साँस नहीं ले सक"],
        "hinglish": ["saans nahi aa*", "saans nahi le pa*", "saans nahi le sak*"],
    },
    "unable to speak": {
        "hi": ["बोल नहीं पा", "बोल नहीं सक"],
        "hinglish": ["bol nahi pa*", "bol nahi sak*"],
    },
    "blue lips": {
        "hi": ["होंठ नीले", "नीले होंठ"],
        "hinglish": ["honth neele", "neele honth"],
    },
    "vomiting blood": {
        "hi": ["ख़ून की उल्टी", "उल्टी में ख़ून"],
        "hinglish": ["khoon ki ulti", "ulti mein khoon"],
    },
    "black stool": {
        "hi": ["काला मल", "काली टट्टी"],
        "hinglish": ["kala mal", "kali tatti"],
    },
    "coughing blood": {
        "hi": ["खाँसी में ख़ून", "ख़ून की खाँसी"],
        "hinglish": ["khansi mein khoon", "khoon ki khansi"],
    },
    "unconscious": {
        "hi": ["बेहोश"],
        "hinglish": ["behosh*"],
    },
    "seizure": {
        "hi": ["दौरा पड़", "मिर्गी का दौरा"],
        "hinglish": ["daura pad*", "mirgi ka daura"],
    },
    "fainted": {
        "hi": ["ग़श खा", "चक्कर खाकर गिर", "चक्कर खा कर गिर"],
        "hinglish": ["ghash kha*", "chakkar khakar gir*", "chakkar kha kar gir*"],
    },
    "collapse": {
        "hi": ["अचानक गिर"],
        "hinglish": ["achanak gir*"],
    },
    "confusion": {
        "hi": ["बहकी बहकी बात", "होश में नहीं"],
        "hinglish": ["behki behki baat*", "hosh mein nahi"],
    },
}

# Common Romanised spellings -> the canonical spelling used above, applied
# word by word to the query before Hinglish matching only.
HINGLISH_SPELLINGS: dict[str, str] = {
    **dict.fromkeys(["me", "main", "mai", "mien", "men"], "mein"),
    **dict.fromkeys(["nahin", "nai", "nhi", "nahee"], "nahi"),
    **dict.fromkeys(["kamjori", "kamzoree", "kamjoree"], "kamzori"),
    **dict.fromkeys(["khun", "khoon"], "khoon"),
    **dict.fromkeys(["sans", "saas", "saans"], "saans"),
    **dict.fromkeys(["sine", "sene", "seeney"], "seene"),
    **dict.fromkeys(["chati", "chaati", "chhaati", "chhatee"], "chhati"),
    **dict.fromkeys(["muh", "mooh", "moonh", "munh"], "munh"),
    **dict.fromkeys(["terha", "tedhaa", "teda"], "tedha"),
    **dict.fromkeys(["zuban", "jaban", "juban", "zabaan", "zubaan", "jubaan"], "zaban"),
    **dict.fromkeys(["awaz", "aawaz", "avaaz", "awaj"], "awaaz"),
    **dict.fromkeys(["banh", "baah"], "baanh"),
    "hath": "haath",
    **dict.fromkeys(["achaanak", "acchanak"], "achanak"),
    "sar": "sir",
    "sardard": "sirdard",
    "tej": "tez",
    **dict.fromkeys(["hoth", "hont", "honth"], "honth"),
    **dict.fromkeys(["nile", "neela", "nila", "neeli", "nili"], "neele"),
    **dict.fromkeys(["ultee", "ulty"], "ulti"),
    "kaali": "kali",
    "kaala": "kala",
    **dict.fromkeys(["khaansi", "khaansee"], "khansi"),
    "doura": "daura",
    "mirgee": "mirgi",
    **dict.fromkeys(["gash", "ghaash"], "ghash"),
    "bahki": "behki",
}


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    kind: str | None = None  # "red_flag" | "referral" | "low_confidence"
    flag: str | None = None  # red flags: the English flag that matched (also for a translation)


def _normalize(text: str) -> str:
    """Lowercase; for Devanagari, drop the nukta (ख़ = ख) and treat
    chandrabindu as anusvara (साँस = सांस), so spelling variants match."""
    text = unicodedata.normalize("NFC", text.lower())
    return text.replace("़", "").replace("ँ", "ं")


def _hinglish(text: str) -> str:
    return re.sub(r"[a-z]+", lambda m: HINGLISH_SPELLINGS.get(m.group(), m.group()), _normalize(text))


def find_keyword(text: str, keywords: list[str]) -> str | None:
    lowered = _normalize(text)
    for kw in keywords:
        prefix = kw.endswith("*")
        pattern = r"(?<![a-z0-9])" + re.escape(_normalize(kw.rstrip("*"))) + ("" if prefix else r"(?![a-z0-9])")
        if re.search(pattern, lowered):
            return kw
    return None


def find_red_flag(query: str) -> tuple[str, str] | None:
    """(matched phrase, English red flag) or None. English first, then
    Hindi, then Hinglish (after spelling normalization)."""
    hit = find_keyword(query, GLOBAL_RED_FLAGS)
    if hit:
        return hit, hit
    for english, langs in TRANSLATED_RED_FLAGS.items():
        hit = find_keyword(query, langs["hi"]) or find_keyword(_hinglish(query), langs["hinglish"])
        if hit:
            return hit.rstrip("*"), english
    return None


def check_red_flags(query: str) -> GuardrailResult:
    found = find_red_flag(query)
    if found:
        hit, english = found
        said = f"'{hit}'" if hit == english else f"'{hit}' ({english})"
        return GuardrailResult(
            allowed=False,
            kind="red_flag",
            flag=english,
            reason=(
                f"Query mentions {said}, an emergency warning sign — this needs "
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

"""Who the answer is for, and in which language. Only the wording changes:
routing, guardrails, agents, risk tools and citations are identical for
every audience (tested in tests/test_audience.py).

  clinician      full detail, numbers and sources, English (the original
                 MedBot wording, unchanged)
  health_worker  simple language for a community health worker at a primary
                 health centre, in English, Hindi (Devanagari) or Hinglish
                 (Romanised Hindi); every answer ends with a fixed "Next
                 step" line saying what to do now and when to refer

The deterministic messages (red flag, safety deferral, referral, no
grounding, clarification) and the "Next step" lines are fixed text written
here, so they reach the user whatever a model writes. The Hindi/Hinglish
text was written for this project and needs native-speaker review, like the
red-flag translations (guardrails/README.md).
"""
from __future__ import annotations

AUDIENCES = ("clinician", "health_worker")
LANGUAGES = ("en", "hi", "hinglish")


def normalize(audience: str | None, language: str | None) -> tuple[str, str]:
    """Validated (audience, language). Clinician mode is English only."""
    audience = audience or "clinician"
    language = language or "en"
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}")
    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {LANGUAGES}")
    return audience, ("en" if audience == "clinician" else language)


# Health-worker text per language. {phrase}/{sign}/{terms}/{names} are filled
# with the words that triggered the message or the covered areas.
_HW = {
    "red_flag": {
        "en": "Urgent: '{phrase}' is an emergency warning sign. This patient must be seen by a doctor in "
              "person now. This tool will not answer it.",
        "hi": "तुरंत ध्यान दें: '{phrase}' एक आपातकालीन चेतावनी संकेत है। इस मरीज़ को अभी डॉक्टर को दिखाना "
              "ज़रूरी है। यह टूल इसका जवाब नहीं देगा।",
        "hinglish": "Turant dhyan dein: '{phrase}' ek emergency warning sign hai. Is mareez ko abhi doctor ko "
                    "dikhana zaroori hai. Yeh tool iska jawab nahi dega.",
    },
    "safety": {
        "en": "Urgent: the safety check found a possible emergency warning sign{sign}. This patient must be "
              "seen by a doctor in person now.",
        "hi": "तुरंत ध्यान दें: सुरक्षा जाँच में एक संभावित आपातकालीन चेतावनी संकेत{sign} मिला है। इस मरीज़ को "
              "अभी डॉक्टर को दिखाना ज़रूरी है।",
        "hinglish": "Turant dhyan dein: safety check mein ek sambhavit emergency warning sign{sign} mila hai. "
                    "Is mareez ko abhi doctor ko dikhana zaroori hai.",
    },
    "referral": {
        "en": "Refer this patient: the guideline lists '{terms}' as a reason to refer. This tool will not "
              "advise on it.",
        "hi": "इस मरीज़ को रेफ़र करें: गाइडलाइन में '{terms}' को रेफ़र करने का कारण बताया गया है। यह टूल इस "
              "पर सलाह नहीं देगा।",
        "hinglish": "Is mareez ko refer karein: guideline mein '{terms}' ko refer karne ka kaaran bataya gaya "
                    "hai. Yeh tool is par salah nahi dega.",
    },
    "no_grounding": {
        "en": "This tool has no clear guidance on this question, so it will not guess.",
        "hi": "इस सवाल पर इस टूल के पास साफ़ जानकारी नहीं है, इसलिए यह अंदाज़ा नहीं लगाएगा।",
        "hinglish": "Is sawaal par is tool ke paas saaf jaankari nahi hai, isliye yeh andaaza nahi lagayega.",
    },
    "clarify": {
        "en": "I couldn't tell which part of the body this question is about. Please ask again and name the "
              "area. Covered: {names}.",
        "hi": "समझ नहीं आया कि यह सवाल शरीर के किस हिस्से के बारे में है। कृपया दोबारा पूछें और हिस्सा बताएं। "
              "शामिल: {names}।",
        "hinglish": "Samajh nahi aaya ki yeh sawaal shareer ke kis hisse ke baare mein hai. Kripya dobara "
                    "poochhein aur hissa batayein. Shaamil: {names}.",
    },
}

_NEXT_STEP = {
    "emergency": {
        "en": "Next step: Send the patient to the nearest hospital emergency department now, or call emergency "
              "services. Do not wait.",
        "hi": "अगला कदम: मरीज़ को अभी नज़दीकी अस्पताल के आपातकालीन विभाग में भेजें, या आपातकालीन सेवा को फ़ोन "
              "करें। इंतज़ार न करें।",
        "hinglish": "Agla kadam: Mareez ko abhi nazdeeki hospital ke emergency vibhag mein bhejein, ya emergency "
                    "service ko phone karein. Intezaar na karein.",
    },
    "refer": {
        "en": "Next step: Refer the patient to a doctor (for example the medical officer at your PHC) for "
              "assessment.",
        "hi": "अगला कदम: मरीज़ को जाँच के लिए डॉक्टर (जैसे अपने PHC के मेडिकल ऑफ़िसर) के पास रेफ़र करें।",
        "hinglish": "Agla kadam: Mareez ko jaanch ke liye doctor (jaise apne PHC ke medical officer) ke paas "
                    "refer karein.",
    },
    "ask_doctor": {
        "en": "Next step: Ask a doctor (for example the medical officer at your PHC) about this patient.",
        "hi": "अगला कदम: इस मरीज़ के बारे में डॉक्टर (जैसे अपने PHC के मेडिकल ऑफ़िसर) से पूछें।",
        "hinglish": "Agla kadam: Is mareez ke baare mein doctor (jaise apne PHC ke medical officer) se poochhein.",
    },
    "answered": {
        "en": "Next step: Follow the advice above. Refer the patient to a doctor if the advice says to refer, "
              "if any emergency warning sign appears, or if you are not sure.",
        "hi": "अगला कदम: ऊपर दी गई सलाह का पालन करें। अगर सलाह में रेफ़र करने को कहा गया है, कोई आपातकालीन "
              "चेतावनी संकेत दिखे, या आपको पक्का न हो, तो मरीज़ को डॉक्टर के पास रेफ़र करें।",
        "hinglish": "Agla kadam: Upar di gayi salah ka paalan karein. Agar salah mein refer karne ko kaha gaya "
                    "hai, koi emergency warning sign dikhe, ya aapko pakka na ho, toh mareez ko doctor ke paas "
                    "refer karein.",
    },
}

_WHEN_TO_REFER = {"en": "When to refer:", "hi": "कब रेफ़र करें:", "hinglish": "Kab refer karein:"}

_WRITE_IN = {
    "en": "Write in simple English.",
    "hi": "Write the whole answer in Hindi, in Devanagari script. Keep source names and URLs, test names, "
          "units and numbers exactly as given.",
    "hinglish": "Write the whole answer in Hinglish: Hindi in Roman (Latin) script, as commonly typed in "
                "India. Keep source names and URLs, test names, units and numbers exactly as given.",
}

CLINICIAN_SYNTHESIS_PROMPT = (
    "You are the Orchestrator in MedBot Orchestrator. Combine the specialist "
    "answers below into one clear response for a clinician. Do not add any "
    "medical claim the agents did not make, and leave out any claim an agent "
    "says its sources do not support. Where agents' answers interact "
    "(e.g. diabetes changing a blood-pressure threshold), point that out only "
    "if both answers support it. Report any risk-tool result (calculator "
    "value or model estimate) separately from guideline rules, with its "
    "disclaimer. Then write one line 'Sources:' listing the source URLs "
    "exactly as given (not their titles), and end with a reminder that this "
    "supports, and does not replace, clinical judgment."
)


def synthesis_prompt(audience: str, language: str) -> str:
    if audience == "clinician":
        return CLINICIAN_SYNTHESIS_PROMPT
    return (
        "You are the Orchestrator in MedBot Orchestrator. Combine the specialist answers below into one "
        "short answer for a community health worker (for example an ASHA or ANM) at an Indian primary "
        "health centre. Use simple everyday words and short sentences; avoid medical jargon or explain it "
        "in plain words. Do not add any medical claim the agents did not make. Keep a number only where "
        "the health worker needs it to act (for example a threshold to check). Report any risk-tool result "
        "(calculator value or model estimate) separately from guideline rules, with its disclaimer. Then "
        f"write a line starting '{_WHEN_TO_REFER[language]}' using only what the agents' answers say about "
        "referral; leave it out if they say nothing about referral. Finish with one line 'Sources:' listing "
        f"the sources exactly as given. {_WRITE_IN[language]}"
    )


def red_flag_message(audience: str, language: str, phrase: str, clinician_reason: str) -> str:
    if audience == "clinician":
        return f"Urgent: {clinician_reason} Contact emergency services or go to the nearest emergency department."
    return _HW["red_flag"][language].format(phrase=phrase) + "\n\n" + _NEXT_STEP["emergency"][language]


def safety_message(audience: str, language: str, sign: str | None) -> str:
    sign = f" ({sign})" if sign else ""
    if audience == "clinician":
        return (f"Urgent: the safety check found a possible emergency warning sign{sign} that "
                "needs urgent in-person medical assessment, not an automated answer. Contact "
                "emergency services or go to the nearest emergency department.")
    return _HW["safety"][language].format(sign=sign) + "\n\n" + _NEXT_STEP["emergency"][language]


def referral_message(audience: str, language: str, terms: list[str], clinician_reasons: str) -> str:
    if audience == "clinician":
        return f"Deferring to clinician review. {clinician_reasons}"
    return (_HW["referral"][language].format(terms="', '".join(dict.fromkeys(terms)))
            + "\n\n" + _NEXT_STEP["refer"][language])


def no_grounding_message(audience: str, language: str, risk_block: str) -> str:
    if audience == "clinician":
        return ("None of the consulted agents' source material clearly covers this "
                "question, so I won't guess. Please consult a clinician.") + risk_block
    return _HW["no_grounding"][language] + risk_block + "\n\n" + _NEXT_STEP["ask_doctor"][language]


def clarify_message(audience: str, language: str, names: str) -> str:
    if audience == "clinician":
        return ("I couldn't tell which body system this question is about. "
                f"Could you rephrase it with the relevant area? Covered: {names}.")
    return _HW["clarify"][language].format(names=names)


def answered_suffix(audience: str, language: str) -> str:
    """Appended after the synthesis and risk-tool block: the fixed last line."""
    return "" if audience == "clinician" else "\n\n" + _NEXT_STEP["answered"][language]

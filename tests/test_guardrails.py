from pathlib import Path

from guardrails.checks import (
    GLOBAL_RED_FLAGS, TRANSLATED_RED_FLAGS, check_red_flags, find_keyword, run_guardrails,
)
from orchestrator.router import handle_query
from rag.retrieve import retrieve


def test_word_boundaries_no_false_match():
    # "tia" must not fire inside "initial" / "potential"
    assert find_keyword("initial potential assessment", ["tia"]) is None
    assert find_keyword("history of TIA last year", ["tia"]) == "tia"


def test_red_flag_overrides_everything():
    q = "Patient with chest pain, what is their CVD risk band?"
    g = run_guardrails(q, retrieve("cardiac", q), ["angina"])
    assert not g.allowed and g.kind == "red_flag"


def test_organ_referral_term():
    q = "Patient has proteinuria, how often to test GFR?"
    g = run_guardrails(q, retrieve("renal", q), ["proteinuria"])
    assert not g.allowed and g.kind == "referral"


def test_low_confidence_defers():
    q = "how do I renew my passport"
    g = run_guardrails(q, retrieve("hepatic", q), [])
    assert not g.allowed and g.kind == "low_confidence"


def test_well_covered_query_allowed():
    q = "What GFR value suggests kidney disease?"
    assert run_guardrails(q, retrieve("renal", q), []).allowed


def test_red_flag_variants():
    for q in ["sudden facial droop and slurred speech", "she is vomiting blood", "he can't breathe"]:
        assert not check_red_flags(q).allowed, q


def test_every_translation_maps_to_an_existing_english_red_flag():
    assert set(TRANSLATED_RED_FLAGS) <= set(GLOBAL_RED_FLAGS)
    for langs in TRANSLATED_RED_FLAGS.values():
        assert set(langs) == {"hi", "hinglish"} and langs["hi"] and langs["hinglish"]


def test_every_translated_phrase_fires_in_a_sentence():
    for english, langs in TRANSLATED_RED_FLAGS.items():
        for phrase in langs["hi"] + langs["hinglish"]:
            q = f"मरीज़ को {phrase.rstrip('*')} है" if phrase in langs["hi"] else f"patient ko {phrase.rstrip('*')} hai"
            g = check_red_flags(q)
            assert not g.allowed and g.kind == "red_flag" and g.flag == english, (phrase, g)


def test_translated_red_flags_are_reviewed_in_readme():
    readme = (Path(__file__).resolve().parents[1] / "guardrails" / "README.md").read_text(encoding="utf-8")
    for english, langs in TRANSLATED_RED_FLAGS.items():
        for phrase in [english] + langs["hi"] + langs["hinglish"]:
            assert phrase in readme, phrase


def test_hindi_spelling_variants():
    # chandrabindu vs anusvara, with and without nukta
    for q in ["मरीज़ को साँस नहीं आ रही", "मरीज को सांस नहीं आ रही", "खून की उल्टी", "ख़ून की उल्टी"]:
        assert not check_red_flags(q).allowed, q


def test_hinglish_spelling_variants():
    for q in ["Patient ko seene mein dard hai", "patient ko sine me dard", "chaati main dard ho raha",
              "sans nahin aa rahi", "Dadi behoshi mein hai", "KHUN KI ULTI hui", "haath me kamjori"]:
        assert not check_red_flags(q).allowed, q


def test_hinglish_red_flag_beats_routing_keyword():
    for q in ["Sugar patient behosh ho gaya", "BP ke patient ko seene mein dard hai"]:
        r = handle_query(q)
        assert r.deferred and r.routing_method == "red_flag" and r.agents_consulted == [], q


def test_english_matching_unchanged_by_hinglish_spellings():
    # "me" -> "mein" etc. applies only to Hinglish matching
    assert check_red_flags("tell me about blood pressure").allowed
    assert find_keyword("tell me", ["mein"]) is None


def test_prefix_keyword():
    assert find_keyword("behoshi", ["behosh*"]) == "behosh*"
    assert find_keyword("behoshi", ["behosh"]) is None
    assert find_keyword("abehosh", ["behosh*"]) is None


def test_heart_attack_phrase_named_chest_pain_not_seizure():
    """"dil ka daura pada" also contains "daura pad-" (seizure); the message must name chest pain."""
    for q in ["मेरे पिता को दिल का दौरा पड़ा है", "papa ko dil ka daura pada hai", "dil ka doura padha kya?"]:
        g = check_red_flags(q)
        assert not g.allowed and g.flag == "chest pain", (q, g)
        assert "(chest pain)" in g.reason and "seizure" not in g.reason, q


def test_seizure_phrases_still_name_seizure():
    for q in ["bachche ko daura pada", "उसे मिर्गी का दौरा आया"]:
        assert check_red_flags(q).flag == "seizure", q


def test_spelling_and_spacing_variants():
    """Phrasings the keyword layer missed in the QA probe (docs/QA_REPORT.md, C-FLAGS)."""
    for q in ["chest  pain", "chest-pain", "chestpain", "can’t breathe", "cant breathe", "I can't breath",
              "seizures since morning", "fainting spells today", "patient collapsing", "face drooping on one side",
              "सीने मे दर्द", "सीने  में दर्द", "सांस नही आ रही", "उसे दौरे पड़ रहे हैं",
              "seene mein  dard", "khun ki ultii", "dil ka dora pada", "bachche ko daure pad rahe hain"]:
        g = check_red_flags(q)
        assert not g.allowed and g.kind == "red_flag", q


def test_normalization_does_not_add_matches_inside_words():
    # spacing/apostrophe/hyphen changes must not create new word-internal matches
    for q in ["blood-pressure target in diabetes", "patient's kidney function", "re-check eGFR in 3 months",
              "What is the normal range for creatinine?", "मधुमेह में रक्तचाप कितना होना चाहिए"]:
        assert check_red_flags(q).allowed, q

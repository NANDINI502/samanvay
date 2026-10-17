"""Print best-match scores for on-topic and off-topic probe queries per organ,
so the retrieval-confidence threshold (rag/embed.py MIN_SCORE) can be set
from real numbers after changing the corpus or the embedding backend.

    python -m rag.calibrate
"""
from __future__ import annotations

from rag.embed import BACKEND, MIN_SCORE
from rag.retrieve import retrieve

PROBES = {
    "cardiac": ["What follow-up applies to CVD risk under 10 percent?", "when to start a statin",
                "BP threshold for starting antihypertensive drugs"],
    "renal": ["What GFR value suggests kidney disease?", "what urine albumin level is abnormal",
              "who should get tested for kidney problems"],
    "neuro": ["what are the warning signs of a stroke", "how long is the treatment window after stroke symptoms"],
    "hepatic": ["how is hepatitis B transmitted", "symptoms of cirrhosis", "is there a vaccine for hepatitis b"],
    "respiratory": ["how is COPD diagnosed", "what inhaler relieves asthma symptoms", "what triggers asthma"],
    "endocrine": ["fasting blood sugar threshold for diabetes", "complications of diabetes",
                  "how can type 2 diabetes be prevented"],
}
OFF_TOPIC = ["what is the weather today", "best laptop for coding", "how do I renew my passport"]


def main() -> None:
    threshold = MIN_SCORE[BACKEND]
    on, off = [], []
    for organ, queries in PROBES.items():
        for q in queries + OFF_TOPIC:
            top = retrieve(organ, q, 1)[0]
            (off if q in OFF_TOPIC else on).append(top["score"])
            tag = "off" if q in OFF_TOPIC else "on "
            flag = "PASS " if top["score"] >= threshold else "DEFER"
            print(f"{organ:11s} {tag} {top['score']:.3f} {flag} {q[:42]:42s} -> {top['heading']}")
    print(f"\nbackend={BACKEND} threshold={threshold}  on-topic min={min(on):.3f}  off-topic max={max(off):.3f}")


if __name__ == "__main__":
    main()

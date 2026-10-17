"""Each organ's corpus returns the right section for a representative question
(checked within the top 3 chunks, which is what agents send to the model)."""
import pytest

from rag.retrieve import retrieve

CASES = [
    ("cardiac", "What follow-up applies to CVD risk under 10 percent?", "Risk categorization"),
    ("cardiac", "BP threshold for starting antihypertensive drugs", "Hypertension"),
    ("renal", "What GFR value suggests kidney disease?", "GFR"),
    ("renal", "what urine albumin level is abnormal", "albumin"),
    ("neuro", "what are the warning signs of a stroke", "F.A.S.T."),
    ("neuro", "how long is the treatment window after stroke symptoms", "Why time matters"),
    ("hepatic", "how is hepatitis B transmitted", "transmission"),
    ("hepatic", "symptoms of cirrhosis", "Cirrhosis"),
    ("respiratory", "how is COPD diagnosed", "COPD — diagnosis"),
    ("respiratory", "what inhaler relieves asthma symptoms", "Asthma — treatment"),
    ("endocrine", "fasting blood sugar threshold for diabetes", "Diagnostic thresholds"),
    ("endocrine", "complications of diabetes", "Complications"),
]


@pytest.mark.parametrize("organ,query,expected", CASES)
def test_expected_section_in_top3(organ, query, expected):
    headings = [r["heading"] for r in retrieve(organ, query, top_k=3)]
    assert any(expected.lower() in h.lower() for h in headings), headings


def test_meta_sections_not_indexed():
    for organ in ["cardiac", "renal", "neuro", "hepatic", "respiratory", "endocrine"]:
        headings = [r["heading"] for r in retrieve(organ, "limits of this corpus notes", top_k=10)]
        assert not any(h.lower().startswith(("limits of", "notes for")) for h in headings)

"""Per-organ configuration. Adding a new specialist agent = add a corpus file
in rag/corpus/<organ>_*.md, add an entry here, run `python -m rag.ingest
--organ <organ>`. No new agent code needed.

routing_keywords: words that send a query to this agent (word-boundary match)
referral_keywords: organ-specific terms the source protocol says to refer,
                   not auto-manage (checked on top of the global red flags in
                   guardrails/checks.py)
scope: one line injected into the agent's system prompt so it knows what it
       does NOT cover
risk_model: True if the agent has a risk tool (see models/tool.py): the
            cardiac trained model, or the renal eGFR / hepatic FIB-4
            published calculators
"""
from __future__ import annotations

AGENT_CONFIGS: dict[str, dict] = {
    "cardiac": {
        "display_name": "Cardiac",
        "routing_keywords": [
            "heart", "cardiac", "cardiovascular", "cvd", "blood pressure", "bp",
            "hypertension", "cholesterol", "statin", "angina",
        ],
        "referral_keywords": ["angina", "200/120", "bp >200", "bp>200", "cholesterol >8"],
        "scope": "CVD risk bands, blood pressure (hypertension) thresholds for starting treatment, and cholesterol protocol rules from WHO PEN.",
        "risk_model": True,
    },
    "renal": {
        "display_name": "Renal",
        "routing_keywords": [
            "kidney", "renal", "gfr", "egfr", "creatinine", "albumin", "uacr",
            "albuminuria", "proteinuria", "dialysis", "nephro",
        ],
        "referral_keywords": ["proteinuria", "kidney failure", "dialysis"],
        "scope": "Who to test for kidney disease, GFR and urine albumin thresholds, kidney referral rules.",
        "risk_model": True,
    },
    "neuro": {
        "display_name": "Neuro",
        "routing_keywords": [
            "stroke", "tia", "brain", "neuro", "face droop", "facial droop",
            "slurred", "weakness", "numbness", "dizziness", "headache", "vision",
        ],
        "referral_keywords": ["stroke", "tia", "transient ischemic attack"],
        "scope": "Stroke recognition (F.A.S.T.), urgency and referral only.",
    },
    "hepatic": {
        "display_name": "Hepatic",
        "routing_keywords": [
            "liver", "hepatic", "hepatitis", "hbv", "hbsag", "cirrhosis",
            "jaundice", "fatty liver", "nafld", "masld", "nash", "mash", "ascites",
        ],
        "referral_keywords": ["ascites", "varices", "liver failure"],
        "scope": "Hepatitis B, cirrhosis symptoms, fatty liver disease basics.",
        "risk_model": True,
    },
    "respiratory": {
        "display_name": "Respiratory",
        "routing_keywords": [
            "lung", "respiratory", "copd", "asthma", "breath", "breathless",
            "breathlessness", "wheeze", "wheezing", "cough", "inhaler",
            "spirometry", "emphysema", "bronchitis",
        ],
        "referral_keywords": [],
        "scope": "COPD and asthma: symptoms, risk factors, diagnosis, inhaled treatment.",
    },
    "endocrine": {
        "display_name": "Endocrine",
        "routing_keywords": [
            "diabetes", "diabetic", "glucose", "blood sugar", "sugar", "insulin",
            "metformin", "hba1c", "a1c", "endocrine", "thirst",
        ],
        "referral_keywords": ["ketoacidosis", "dka", "hypoglycaemia", "hypoglycemia"],
        "scope": "Diabetes types, symptoms, diagnostic thresholds, complications, management basics.",
    },
}

ORGANS = list(AGENT_CONFIGS)

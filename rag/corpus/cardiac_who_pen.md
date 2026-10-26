# Cardiac Risk — Source Corpus (WHO PEN Protocol)

Source: WHO Package of Essential Noncommunicable Disease Interventions (PEN)
for Primary Health Care in Low-Resource Settings, World Health Organization.
Public document. URL: https://www.afro.who.int/sites/default/files/2017-06/9789241506557_eng.pdf
Also underlying risk-chart methodology: WHO/ISH Cardiovascular Risk Prediction
Charts, in World Health Organization, Prevention of Cardiovascular Disease: Pocket
Guidelines for Assessment and Management of Cardiovascular Risk, Geneva, 2007,
ISBN 978 92 4 154726 0 (the African Region edition; its charts are for AFR D and
AFR E, and it describes the same method for all 14 WHO sub-regions: 10-year risk
from age, sex, blood pressure, smoking status, total blood cholesterol and
diabetes). URL: https://www.afro.who.int/sites/default/files/2017-06/Pocket%20CVD%20manual%20English.pdf
(Replaces the PAHO copy of the charts, www3.paho.org/hq/dmdocuments/2010/colour_charts_24_Aug_07.pdf,
which returned HTTP 502 on 2026-10-27.)

This file is a curated set of protocol excerpts used to ground the Cardiac
specialist agent's retrieval. It is NOT the full WHO document — always cite
back to the source above in any user-facing answer, and this system supports
clinical judgment, it does not replace it.

## Risk factors used for total CVD risk estimation

- Age (grouped: <40, 40-49, 50-59, 60-69)
- Sex
- Smoking status (current tobacco use in the last 12 months)
- Systolic blood pressure
- Total cholesterol (or population mean if assay unavailable)
- Diabetes mellitus status

"Use age, gender, smoking status, systolic blood pressure, DM (and plasma
cholesterol if available)" — WHO PEN, Action 3.

## Risk categorization and follow-up

- **Risk < 10%**: Counsel on diet, physical activity, smoking cessation,
  avoiding harmful alcohol use. Follow up in 12 months.
- **Risk 10–<20%**: Lifestyle counseling; consider antihypertensive drugs if
  persistent BP ≥140/90 mmHg. Follow up every 3 months until targets are met,
  then every 6–9 months.
- **Risk 20–<30%**: Intermediate category between the 10–<20% and ≥30% bands;
  intensify lifestyle counseling and monitor closely for threshold crossing.
- **Risk ≥30%**: Eligible for drug therapy — "give a statin" and
  antihypertensive medication — plus counseling. Follow up every 3 months.

## Hypertension diagnosis and management

- Persistent BP ≥140/90 mmHg → consider antihypertensive drugs, in patients
  with CVD risk 10–<20%.
- Persistent BP ≥130/80 mmHg → consider antihypertensive drugs specifically
  in patients with diabetes or albuminuria.
- BP >200/>120 mmHg → urgent referral.
- First-line medications: ACE inhibitors and/or low-dose thiazides, with
  age-based selection (under 55 years vs. over 55 years).

## Diabetes mellitus diagnostic criteria

- Fasting blood sugar ≥7 mmol/L (126 mg/dL), OR
- Random blood sugar ≥11.1 mmol/L (200 mg/dL)
- Diabetic patients get the stricter BP threshold (≥130/80 mmHg) for starting
  antihypertensive therapy.

## Referral criteria ("danger signs") — Action 4

Any of the following bypasses primary-care management and requires referral
to the next level of care:

- BP >200/>120 mmHg (urgent referral)
- Known heart disease, stroke, transient ischemic attack, diabetes, or
  kidney disease
- New chest pain, or a change in severity of existing angina
- Any proteinuria
- Total cholesterol >8 mmol/L
- High cardiovascular risk (≥30% 10-year CVD event probability by WHO/ISH
  risk charts)

## Notes for this agent's guardrail behavior

This corpus supports **risk-band estimation and general protocol guidance
only**. It does not cover every comorbidity, drug interaction, or regional
variation in the full WHO/ISH charts (21 global regions). When a query needs
information not in this corpus — e.g. a specific drug interaction, a
pediatric case, or a region-specific chart the corpus doesn't include — the
agent should defer rather than guess, and say what additional information or
specialist input is needed.

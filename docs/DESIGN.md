# Samanvay — design rationale

This page explains why the web UI looks and behaves the way it does. Every choice starts from the people who will use it and the situation they are in.

## Who it is for

Samanvay is built around the WHO PEN protocol for primary health centres, so there are two kinds of user. The first is a **community health worker** (for example an ASHA or ANM in India). They often use a low-end Android phone in bright daylight, may be more comfortable in Hindi or Hinglish than in clinical English, and need a clear next action: is this an emergency, should I refer, or can I follow the guideline? The second is a **clinician or medical officer** at a PHC. They want numbers, sources and how the answer was reached, so they can check it before trusting it.

Both users are making decisions about someone else's health, so the interface must never look more certain than the system is.

## Layout (v2)

One static page, three columns on a desktop (1200px and wider), with a thin icon rail on the left:

- **Top bar** (indigo): name, "NVIDIA Nemotron · Nebius", a Live / Mock / Offline pill from `/api/health`, the interface-language switch (हिन्दी · English · Hinglish) and Settings.
- **Rail:** Home, Ask, History, Settings. Below 900px it becomes a bottom tab bar, where a thumb can reach it.
- **Column 1, asking:** "Who is asking?" (Health worker, with its answer-language chips inside the same card, or Clinician), the question box with a microphone and a 0/1000 counter, Measurements (n) and Ask Samanvay, the green "Decision support, not diagnosis." strip, then the Specialist Team.
- **Column 2, the answer:** a hero card for first-time visitors, the four triage meanings (Emergency, Refer to a doctor, Guidance, Please clarify), then the answer card, "How this answer was made" and "Specialist notes".
- **Column 3, numbers:** the Measurements card (eGFR, FIB-4 and heart-risk inputs, or the result once calculated), the heart-risk card and a Sources card that says which specialist used each source.
- **Try a case:** a horizontally scrolling row of one-tap examples, with "See all" to wrap them.

Between 900 and 1199px, column 3 moves under column 2. Below 900px everything becomes one column, in the order a phone user needs it: question, answer, team, measurements, sources. Nothing scrolls sideways down to 360px wide.

## Design principles

1. **Triage first.** The first thing on every answer is a coloured banner that says what kind of answer it is: Emergency, Refer to a doctor, Guidance, or Please clarify. These map one-to-one to the backend's guardrail outcomes (red flag, referral or low-confidence deferral, normal answer, no specialist matched). A health worker can act on the banner alone.
2. **Ask who is asking.** The first control is "Who is asking?": Health worker (simple words, Hindi) or Clinician (full detail, numbers). Choosing Health worker shows a language choice (हिन्दी / Hinglish / English), and the interface labels switch with it. Medical text always comes from the backend; the UI only translates interface words.
3. **Show the team, not a black box.** Six specialist tiles (Heart, Kidney, Liver, Diabetes, Lungs, Brain, each with its agent name) show the multi-agent system in action. Each tile has a soft identity colour so the six are easy to tell apart; that colour never carries a status. When the answer arrives, the specialists consulted get a small status badge (✓ green answered, – amber unsure, ✗ red deferred, each with an `aria-label`), and the others fade out. Under the tiles, a three-step stepper (Assessing symptoms → Running agents → Synthesizing answer) shows where the request is. While waiting, the stepper advances on a timer, because the API answers in one response; its final state always comes from the response (for example "Synthesizing answer" shows a dash when a deferral meant no synthesis ran). If an emergency sign is found, every tile turns grey, the stepper stops on its first step, and a red caption says "Emergency sign found — stopped before any AI call" (or, when the one-way AI safety check found it, that the safety check stopped it).
4. **Numbers you can read at a glance.** Calculator results (eGFR, FIB-4) appear as a large reading on a scale whose bands come only from the thresholds the backend quotes from its cited sources (NIDDK for eGFR; Sterling et al. 2006 for FIB-4). The cardiac model shows a probability bar, its top contributing factors and its cross-validated performance. Every result card carries its own disclaimer and citation.
5. **Proof on demand.** "How this answer was made" lists every step in order, whether a rule in code or a Nemotron call made it, which model tier was used, the latency and the token counts. It is folded away so it doesn't distract a health worker, and it is one tap away for a clinician or a judge.
6. **Emergency beats everything.** An emergency answer gets a red border, a larger and bolder answer text, and on phones the page scrolls straight to it.

## Colour

| Role | Light | Why |
|---|---|---|
| Paper (background) | `#F6F3EC` | A warm off-white, like khadi or a printed register. It is easier on the eyes than pure white in bright light and feels less like a hospital screen. |
| Ink (text) | `#1B1F3B` | A deep navy-black with high contrast on paper. |
| Brand | `#2E3A8C` indigo | Calm and trustworthy, and deliberately **not** a status colour. If the brand were green or red, it would compete with the triage signal. |
| Emergency | `#B42318` red | Universal danger colour. |
| Refer | `#92400E` amber | Caution: action needed, not an emergency. |
| Guidance | `#166534` green | Safe to follow the guideline. |
| NVIDIA / Nemotron tag | `#4A7A00` | A darkened NVIDIA green, used only for "this step was a Nemotron call". |

Status colours are reserved for status. **Colour is never the only signal:** every status also has an icon (check, dash, cross or warning triangle) and words, so it still works for colour-blind users and on poor screens. All text colours pass WCAG AA contrast on their backgrounds. A dark theme follows the system setting, using the same roles with lighter tints.

## Type

- **Headings:** Anek Latin and Anek Devanagari.
- **Body text:** Mukta.

Both families come from Ek Type, a Mumbai type foundry, and each was designed with Latin and Devanagari together. This matters because the same screen often mixes English, Hindi and Hinglish (e.g. "Samanvay" / "समन्वय से पूछें"). Matched families keep line height and stroke weight consistent across scripts, so the mixed text reads as one voice instead of two fonts fighting.

Body text is 17–18px (an answer is 18px, and 20px bold for an emergency) because the main users read on phones, sometimes outdoors. If Google Fonts cannot load, the page falls back to system fonts and still works.

## Language

Two separate choices, so nobody gets an answer in a language they didn't ask for:

- The **top-bar switch** changes interface words only (buttons, labels, banners), from a fixed dictionary in the page. It never changes the request.
- The **answer-language chips** inside the Health worker card are sent to `/api/ask`. Picking one also selects Health worker and switches the interface to the same language, which is what a health worker expects. Clinician answers are English.

Medical text always comes from the backend. The Hindi and Hinglish interface words were written for this project and need a native speaker's review, like the backend's fixed messages.

## Voice, history and settings

- **Voice input** uses the browser's Web Speech API (`hi-IN` for Hindi and Hinglish, `en-IN` for English). The microphone is hidden where the browser doesn't support it. Recognised text goes into the question box for the user to check; it is never sent automatically.
- **History** keeps only the last 10 question texts, their time and their triage level, in this browser's `localStorage`. Answers and patient values are never stored. Tapping an item puts the question back in the box. "Clear history" is in the History panel and in Settings. If storage is blocked, the page works without it.
- **Settings:** interface language, the default for "Who is asking?", Clear history, and a System / Light / Dark theme override.

## Accessibility and robustness

- Touch targets are at least 44px, with visible focus rings and full keyboard use (Ctrl/⌘+Enter submits).
- Real form controls (radios, tabs, selects) carry labels and ARIA roles. Results are announced through `aria-live`.
- `lang` attributes are set per element (`hi`, `hi-Latn`, `en`) so screen readers pronounce Hindi correctly.
- Respects `prefers-reduced-motion` and `prefers-color-scheme`.
- No horizontal scrolling down to a 360px-wide phone.
- No framework and no build step: one static HTML file served by FastAPI, which loads fast on slow connections.
- All server text is inserted as text, never as HTML. Answers are shown with real lists: lines starting "1." or "-" become list items, and "**bold**" becomes bold, all built from text nodes.
- Every value shown (answers, sources, model IDs, latency, tokens, risk results) comes from the API response; an element whose field is missing is not shown.

## What we deliberately did not do

- No chat-bubble interface. A clinical answer is a document with a verdict, not a conversation, and chat bubbles make an AI feel more human and more certain than it is.
- No percentages or risk numbers without their source, population and disclaimer next to them.
- No decorative medical imagery (stethoscopes, glowing brains). The six organ icons are functional: each one is an agent. The one illustration, a hand-drawn rural health centre with trees in the hero card, shows the setting the tool is for. It is inline SVG drawn from the page's own colour tokens, so it follows the theme and needs no image download.

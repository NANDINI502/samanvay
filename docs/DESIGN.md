# Samanvay — design rationale

This page explains why the web UI looks and behaves the way it does. Every choice starts from the people who will use it and the situation they are in. The current theme is **Care** (`<style id="theme-care">` in `api/static/index.html`, on top of the base styles).

## Who it is for

Samanvay is built around the WHO PEN protocol for primary health centres, so there are two kinds of user. The first is a **community health worker** (for example an ASHA or ANM in India). They often use a low-end Android phone in bright daylight, may be more comfortable in Hindi or Hinglish than in clinical English, may read slowly, and need a clear next action: is this an emergency, should I refer, or can I follow the guideline? The second is a **clinician or medical officer** at a PHC. They want numbers, sources and how the answer was reached, so they can check it before trusting it.

Both users are making decisions about someone else's health, so the interface must never look more certain than the system is.

## Where the Care theme comes from

The theme draws on four kinds of reference. These are design references, not studies we ran:

- **Consumer health brands** (One Medical, Oura, Headspace): warm paper instead of clinical white, one serious brand colour, a serif headline for warmth, and depth from hairlines and stepped surfaces rather than glows or gradients.
- **NHS.UK care cards** ([NHS digital service manual](https://service-manual.nhs.uk/design-system/components/care-cards)): the level of care is a coloured header band with an icon and a word, so it can be read before the text. The NHS uses blue (non-urgent), red (urgent) and red with dark grey (emergency). We keep blue and the red-with-dark-band emergency, and use **amber for "refer to a doctor"**. A red referral card would look too much like an emergency.
- **Frontline and low-literacy health UX**: one main action per screen, a word on every icon, large Hindi text, high contrast, read-aloud, calculators hidden until needed, and citations one tap away.
- **Showing the system honestly**: the specialist panel is drawn as a pipeline working on the question, not as a chat partner.

## Layout

One static page, one column until a question is asked:

- **Top bar** (paper, not coloured): logo and name, a Live / Mock / Offline pill from `/api/health`, the interface-language switch (हिन्दी · Hinglish · English), History and Settings. Below 900px, Home / Ask / History / Settings move to a bottom tab bar, where a thumb can reach them.
- **Hero** (before the first question): the headline in two lines ("Six specialists." / "One careful answer.", i18n keys `h1a`/`h1b`), a short promise, and the illustration. Below 900px the illustration sits above the text.
- **Ask card:** "Who is asking?" (Health worker, with answer-language chips, or Clinician), the question box with a microphone and a counter, the **Measurements** button, and Ask Samanvay. Under it is the "Decision support, not diagnosis." line.
- **Specialist team:** six tiles and a three-step stepper.
- **After a question** (`body.asked`): at 1000px and wider, the answer takes the main column and the specialist team becomes a sticky panel on the right. Below that, everything is one column in the order a phone user needs: answer, Measurements (when open), "How this answer was made" and "Specialist notes" (rendered into `#more`), then Try a case.
- **Measurements** are hidden until needed. The Measurements button toggles `body.m-open`, sets `aria-expanded`, and scrolls to and focuses the card.
- **Try a case:** a horizontally scrolling row of one-tap examples, with "See all" to wrap them. It moves under the answer area once the page has loaded.

Nothing scrolls the page sideways at 390px, 1024px or 1440px (checked with a live run of every case, 2026-10-27).

## Design principles

1. **Triage first, NHS-style.** Every answer starts with a care-card band that says what kind of answer it is. These map one-to-one to the backend's guardrail outcomes:

   | Band | Colour | Backend outcome |
   |---|---|---|
   | Emergency | red, with a dark band | red flag (keyword or one-way safety check) |
   | Refer to a doctor | amber | referral term or low-confidence deferral |
   | Guidance | blue | normal grounded answer |
   | Please clarify | neutral | no specialist matched |

   A health worker can act on the band alone.
2. **Ask who is asking.** The first control is "Who is asking?". Health worker shows the answer-language chips (हिन्दी / Hinglish / English); Clinician hides them, because clinician answers are English. Medical text always comes from the backend; the UI only translates interface words.
3. **A pipeline, not a chat.** Six specialist tiles (Heart, Kidney, Liver, Diabetes, Lungs, Brain) and a stepper (Assessing symptoms → Running agents → Synthesizing answer) show the multi-agent system working. While a request runs, `body.thinking` animates the panel. The final state always comes from the response: specialists consulted get a status badge with an icon and a word, the others fade, and an emergency stops the stepper on its first step with a caption saying what stopped it.
4. **Numbers you can read at a glance.** eGFR and FIB-4 results show as a **score ring** and a banded scale. The ring's zone colour uses exactly the thresholds the backend quotes from its cited sources: eGFR from NIDDK (15 or less / below 60 / 60 or more) and FIB-4 from Sterling et al. 2006 (below 1.45 / 1.45–3.25 / above 3.25). The cardiac model's probability uses a brand-coloured ring, because the model has no cited cut-offs. Every result keeps its disclaimer and citation next to it.
5. **Read-aloud for low-literacy users.** Each answer has a **Listen** button that reads the final answer with the browser's own `speechSynthesis`: `hi-IN` for Hindi and Hinglish answers, `en-IN` for English. It toggles to Stop, stops when a new question is asked, and is hidden where the browser has no speech engine. Nothing is sent to a server.
6. **Proof on demand.** "How this answer was made" lists every step in order: whether a rule in code or a Nemotron call made it, which model tier, the latency and the tokens. It is folded away for a health worker and one tap away for a clinician or a judge.
7. **Emergency beats everything.** An emergency answer gets the red band with a dark strip, larger and bolder text, and on phones the page scrolls straight to it.

## Colour

| Role | Light | Dark | Why |
|---|---|---|---|
| Paper | `#FBF7F0` | `#101614` | Warm off-white, easier on the eyes in bright light than pure white and less like a hospital screen |
| Ink | `#1B2A2F` | `#E8EFEC` | Deep green-black text |
| Brand | `#0F5C4E` neem green | `#5FC3A9` | Calm, local and serious. It is **not** a triage colour, so it never competes with the care-card bands |
| Accent | `#E8A33D` haldi | `#F0B85E` | Focus rings and the logo's centre dot only |
| Guidance | `#005EB8` blue | `#7DB6F2` | NHS non-urgent blue |
| Refer | `#A04B00` amber | `#F2B65C` | Caution: action needed, not an emergency |
| Emergency | `#B42318` red + `#7A1A12` band | `#FF8A7E` | Danger |
| Nemotron tag | `#3F6B00` | `#A6D84B` | Marks "this step was a Nemotron call" only |

- **Blue, amber and red are used only for triage meaning:** the care-card bands, the specialist status badges, and the eGFR/FIB-4 zones, whose meaning comes from the cited thresholds. The base styles' `--green` status token is mapped to the guidance blue, so "answered" and "normal range" read as guidance.
- The six organ tiles keep soft identity tints, which carry no status. Status is always an icon and a word as well, so **colour is never the only signal**.
- Contrast, computed from the tokens with the WCAG formula: body text 13.9:1 (light) and 14.3:1 (dark); secondary text at least 5.2:1; text on every triage colour at least 5.4:1. All pass WCAG AA, and body text passes AAA (7:1).
- Dark follows the system setting unless Settings overrides it.

## Type

- **Interface and body:** Anek Devanagari (Ek Type, Mumbai). One family covers Devanagari and Latin, so mixed English, Hindi and Hinglish on the same screen read as one voice.
- **Headline and wordmark:** Tiro Devanagari Hindi (Tiro Typeworks), a serif with Devanagari and Latin, for warmth in the few places that are not instructions.

Body text is 17px and answers are larger, because the main users read on phones, sometimes outdoors. If Google Fonts can't load, the page falls back to Noto Sans Devanagari or system fonts and still works.

## Illustration and motion

- **Illustration:** one inline SVG in the hero: a primary health centre, the six specialists linked to it, and a health worker with a phone. It shows the setting and the idea (a health worker consulting a panel of specialists). It is drawn from the page's colour tokens, so it follows the theme and needs no image download. It is decorative (`aria-hidden`).
- **Motion:** entrance animations for the hero and the answer, flowing links in the illustration, the stepper and tile badges while `body.thinking`, and the score ring filling with a count-up of its number. Motion only shows progress or draws the eye to a new answer; it never carries information on its own.
- With `prefers-reduced-motion: reduce`, all animations and transitions are off, the count-up is skipped, and scrolling jumps instead of sliding.

## Language

Two separate choices, so nobody gets an answer in a language they didn't ask for:

- The **top-bar switch** changes interface words only, from a fixed dictionary in the page. It never changes the request.
- The **answer-language chips** (Health worker only) are sent to `/api/ask`. Picking one also switches the interface to the same language. Clinician answers are English.

The Hindi and Hinglish interface words were written for this project and need a native speaker's review, like the backend's fixed messages.

## Voice, history and settings

- **Voice input** uses the browser's Web Speech API (`hi-IN` for Hindi and Hinglish, `en-IN` for English). The microphone is hidden where the browser doesn't support it. Recognised text goes into the question box for the user to check; it is never sent automatically.
- **Read-aloud:** see principle 5.
- **History** keeps only the last 10 question texts, their time and their triage level, in this browser's `localStorage`. Answers and patient values are never stored. Tapping an item puts the question back in the box.
- **Settings:** interface language, the default for "Who is asking?", Clear history, and a System / Light / Dark theme.

## Accessibility and robustness

- Touch targets are at least 44px, with visible haldi focus rings and full keyboard use (Ctrl/⌘+Enter submits).
- Real form controls carry labels and ARIA roles; results are announced through `aria-live`; score rings have a text `aria-label` with the value and unit.
- `lang` attributes are set per element (`hi`, `hi-Latn`, `en`) so screen readers pronounce Hindi correctly.
- No framework and no build step: one static HTML file served by FastAPI.
- All server text is inserted as text, never as HTML. Every value shown comes from the API response; an element whose field is missing isn't shown.

## What we deliberately did not do

- No chat-bubble interface. A clinical answer is a document with a verdict, not a conversation, and chat bubbles make an AI feel more human and more certain than it is.
- No percentages or risk numbers without their source, population and disclaimer next to them.
- No triage colours used for decoration, and no stock medical imagery. The one illustration shows the setting the tool is for.

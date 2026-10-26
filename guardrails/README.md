# Guardrails

Deterministic safety checks, run in code before any model call
(`checks.py`). Order: global red flags → organ referral terms (from
`agents/registry.py`) → retrieval confidence. Any red flag stops the
request before routing: no agent runs, no model is called, no risk tool
runs.

## Hindi and Hinglish red flags

Health workers in Indian primary health centres may type in Hindi or in
Romanised Hindi mixed with English (Hinglish). Each phrase below is a
**translation of an existing English red flag**; no new clinical criteria
are added. The English list is matched exactly as before, so the
translations can only add deferrals, never remove one.

Phrases are generated from `TRANSLATED_RED_FLAGS` in `checks.py`, and
`tests/test_guardrails.py` fails if a phrase there is missing from this
table.

| English red flag | Hindi (Devanagari) | Hinglish (Romanised) |
| --- | --- | --- |
| chest pain | सीने में दर्द<br>छाती में दर्द<br>दिल का दौरा¹ | `seene mein dard`<br>`chhati mein dard`<br>`dil ka daura`¹ |
| facial droop | चेहरा टेढ़ा<br>मुँह टेढ़ा | `chehra tedha`<br>`munh tedha`<br>`chehra latak*` |
| slurred speech | ज़बान लड़खड़ा<br>आवाज़ लड़खड़ा | `zaban ladkhad*`<br>`awaaz ladkhad*` |
| arm weakness | बाँह में कमज़ोरी<br>हाथ में कमज़ोरी | `baanh mein kamzori`<br>`haath mein kamzori` |
| sudden weakness | अचानक कमज़ोरी | `achanak kamzori` |
| sudden numbness | अचानक सुन्न | `achanak sunn` |
| worst headache | सबसे तेज़ सिरदर्द<br>सबसे तेज़ सिर दर्द<br>सबसे बुरा सिरदर्द | `sabse tez sirdard`<br>`sabse tez sir dard`<br>`sabse bura sirdard` |
| can't breathe | साँस नहीं आ<br>साँस नहीं ले पा<br>साँस नहीं ले सक | `saans nahi aa*`<br>`saans nahi le pa*`<br>`saans nahi le sak*` |
| unable to speak | बोल नहीं पा<br>बोल नहीं सक | `bol nahi pa*`<br>`bol nahi sak*` |
| blue lips | होंठ नीले<br>नीले होंठ | `honth neele`<br>`neele honth` |
| vomiting blood | ख़ून की उल्टी<br>उल्टी में ख़ून | `khoon ki ulti`<br>`ulti mein khoon` |
| black stool | काला मल<br>काली टट्टी | `kala mal`<br>`kali tatti` |
| coughing blood | खाँसी में ख़ून<br>ख़ून की खाँसी | `khansi mein khoon`<br>`khoon ki khansi` |
| unconscious | बेहोश | `behosh*` |
| seizure | दौरा पड़<br>दौरे पड़<br>मिर्गी का दौरा | `daura pad*`<br>`daure pad*`<br>`mirgi ka daura` |
| fainted | ग़श खा<br>चक्कर खाकर गिर<br>चक्कर खा कर गिर | `ghash kha*`<br>`chakkar khakar gir*`<br>`chakkar kha kar gir*` |
| collapse | अचानक गिर | `achanak gir*` |
| confusion | बहकी बहकी बात<br>होश में नहीं | `behki behki baat*`<br>`hosh mein nahi` |

¹ *Dil ka daura* means "heart attack", not literally "chest pain". There is
no "heart attack" flag in the English list, so it is mapped to the closest
one, chest pain, and the message names chest pain. Translations are checked
in table order, so chest pain is found before `daura pad*` (seizure).

How matching works:

- **Word boundaries** as for English, so a phrase never fires inside a
  longer Roman word. A trailing `*` matches word endings
  (`behosh*` matches *behosh* and *behoshi*; `saans nahi aa*` matches
  *aa rahi*, *aa raha*, *aati*).
- **Spacing and punctuation (all languages):** runs of spaces and hyphens
  count as one space (*chest  pain*, *chest-pain*), and curly apostrophes
  as straight ones (*can’t* = *can't*), so phone keyboards and typing slips
  don't hide a flag.
- **Devanagari spelling variants:** the nukta is ignored (ख़ून = खून,
  ज़बान = जबान), and so are the nasal marks chandrabindu and anusvara,
  which are often left out (साँस = सांस = सास, में = मे, नहीं = नही).
  Devanagari phrases also match as prefixes (साँस नहीं आ matches साँस नहीं आ रही).
- **Romanised spelling variants:** before Hinglish matching only, these
  spellings are mapped to the canonical spelling used above. English
  matching does not use this map.

| Canonical | Also accepted |
| --- | --- |
| mein | me, main, mai, mien, men |
| nahi | nahin, nai, nhi, nahee |
| kamzori | kamjori, kamzoree, kamjoree |
| khoon | khun |
| saans | sans, saas |
| seene | sine, sene, seeney |
| chhati | chati, chaati, chhaati, chhatee |
| munh | muh, mooh, moonh |
| tedha | terha, tedhaa, teda |
| zaban | zuban, jaban, juban, zabaan, zubaan, jubaan |
| awaaz | awaz, aawaz, avaaz, awaj |
| baanh | banh, baah |
| haath | hath |
| achanak | achaanak, acchanak |
| sir | sar |
| sirdard | sardard |
| tez | tej |
| honth | hoth, hont |
| neele | nile, neela, nila, neeli, nili |
| ulti | ultee, ulty, ultii |
| kali | kaali |
| kala | kaala |
| khansi | khaansi, khaansee |
| daura | doura, dora |
| mirgi | mirgee |
| ghash | gash, ghaash |
| behki | bahki |

### English spelling and word-form variants

Added after the QA probe of 2026-10-27 (`docs/QA_REPORT.md`), to the English
list in `guardrails/checks.py`. They are other spellings or word forms of
flags already on the list, not new clinical signs: *chestpain*; *face
drooping*, *facial drooping*; *cant breathe*, *can't breath*, *cant
breath*, *cannot breath*; *seizures*; *fainting*; *collapsing*.

### Known over-matches (safe direction, for review)

Each of these makes the system defer when it might not need to; none can
stop a deferral.

- `daura pad*` (seizure) would also match *dil ka daura pada* (heart
  attack). Fixed: *dil ka daura* is matched first, as chest pain (note ¹).
  Other phrasings, e.g. *heart ka daura pada*, still defer but are
  labelled "seizure".
- `achanak gir*` (collapse) also matches e.g. *sugar achanak gir gaya*
  (blood sugar suddenly dropped).
- `saas` → `saans` (breath) also means *mother-in-law*: *saas nahi aa
  rahi* ("mother-in-law isn't coming") would defer.
- `bol nahi sak*` (unable to speak) also matches *"I can't say"*.

### Needs native-speaker clinical review

The translations were written for this project, not taken from a
published, validated Hindi symptom glossary. The rows most worth
checking are lay phrasings rather than literal translations:
**facial droop** (*munh tedha*), **slurred speech** (*zaban ladkhad-*),
**fainted** (*ghash kha-*, *chakkar khakar gir-*) and **confusion**
(*behki behki baat-*, *hosh mein nahi*).

The health-worker mode's fixed messages in Hindi and Hinglish (red flag,
safety deferral, referral, no guidance, clarification, and the "Next step"
lines) are in `orchestrator/audience.py` and need the same review.

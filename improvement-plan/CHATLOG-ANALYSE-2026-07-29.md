# Chatlog-analyse + verbeterplan — 2026-07-29

Bron: `chat-export-2026-07-29.json` — 257 sessies, ~1.400 berichten, 2026-04-22 t/m
2026-07-29. Alle sessies zijn doorgelopen; bevindingen zijn geverifieerd tegen de huidige
code (niet tegen de code van het moment van het gesprek).

**Belangrijk bij het lezen:** de audit-fixes van 2026-07-15 en de handoff-fix van
2026-07-21 zitten in dit logbestand. Fouten uit gesprekken van vóór 2026-07-15 kunnen
dus al opgelost zijn. Daarom is elke bevinding gelabeld:

- **LIVE** — komt ook ná 2026-07-15 voor, of de oorzaak staat nog letterlijk in de code
- **FIXED** — oorzaak is aantoonbaar weg (in code geverifieerd)

Prioritering volgt de LIVE-bevindingen.

---

## 1. Wat goed gaat

Niet alles is stuk; dit moet overeind blijven bij elke wijziging.

- **Rekenwerk m²/m³/zakken is bijna altijd correct.** Steekproef van 14 berekeningen:
  13 goed (o.a. `sess_LK06tJ` 3×4,5×4,5=60,75 m² → 5,06 m³ bij 8 cm;
  `sess_akcz2` gat ø2,3 m × 0,5 m = 2,08 m³; `sess_hql6A2`; `sess_JDhaIfes`).
- **Productadvies en vergelijkingen zijn sterk.** Ekoboard vs Ecolat vs Recy-Edge
  (`sess_BnPnaAP`, `sess_BX0sPxp`), boomschors vs houtsnippers vs speelmix
  (`sess_cfuiN`, `sess_ZZ5-Oy`), turfvrij/bio (`sess_2ati`, `sess_b0KxUL`).
- **Handoff werkt end-to-end** in ~25 sessies (naam → e-mail → doorgestuurd).
- **Track & trace werkt** bij een geldig zendingnummer (`sess_XTdUKt`, `sess_Q7lJWI`,
  `sess_BHGzNo`) inclusief tijdvak en statusweb-link.
- **Voorraadvraag valt netjes terug op RAG** sinds de Shopify-gating
  (`sess_ItDKZ`, 2026-07-22) — bevestigt dat de mock-lek dicht is.

---

## 2. Foutenoverzicht

### P0-1 — Onzin wordt als bestelnummer geaccepteerd · LIVE

De bot antwoordt letterlijk `Je bestelnummer (**GEEN**) heb ik ontvangen`, ook met
`RAAR`, `WETEN`, `BESTEL`.

Bewijs: `sess_7Xo9Rz` (**2026-07-28**), `sess_Zk0FF` (**2026-07-22**), `sess_u444ko`,
`sess_d0hsN8`, `sess_fM-Mei`.

Oorzaak — [app.py:1352](../backend/app.py#L1352):
```python
number_match = re.search(r'\b([A-Za-z0-9]{4,20})\b', msg_cleaned, re.IGNORECASE)
```
Elk woord van ≥4 tekens matcht. "Ik heb nog geen zending" → `GEEN`.

### P0-2 — State machines slikken de noodrem · LIVE

Zit de gebruiker in de T&T-flow, dan wordt *niets* anders meer gehoord. De bot herhaalt
tot 8× exact hetzelfde bericht, ook op "Echte persoon" en "Verbind me door".

Bewijs: `sess_LRVXh5` (8× identiek), `sess_rWRRux` ("Echte persoon" genegeerd),
`sess_RQ86kt` ("Verbind me door" 2× genegeerd), `sess_IRUGI`, `sess_VgkVCn`,
`sess_OW87gm`, en post-fix `sess_Zk0FF` (**2026-07-22**, 2× "niet gevonden" zonder uitweg).

Oorzaak — de blokken op [app.py:1250](../backend/app.py#L1250),
[:1302](../backend/app.py#L1302), [:1343](../backend/app.py#L1343),
[:1509](../backend/app.py#L1509) checken alleen hun eigen invoer. Geen
`HUMAN_ESCALATION_RE`, geen `FRUSTRATION_RE`, geen poging-teller, geen loop-detectie.
(`awaiting_name`/`awaiting_email` hebben wél een uitweg via `PHONE_CONTACT_RE` +
`detect_ticket_intent` — dat patroon moet naar de andere flows.)

### P0-3 — Verzonnen acties ("ik heb het genoteerd") · deels LIVE

De ergste categorie: de bot belooft dingen die het systeem niet doet.

| Sessie | Wat de bot zei |
|---|---|
| `sess_zCbDEIy` | "Dank je, 26 mei 2026 heb ik genoteerd als voorkeursdatum" + "je krijgt daar bericht over" |
| `sess_1WhsN` | "We wijzigen BS6794 naar Bojardin Franse Boomschors Premium 25-45mm" |
| `sess_j5mH` | "Alleen je bestelnummer is genoeg, dan kunnen wij het voor je nakijken" → "we kunnen hiermee aan de slag" |
| `sess_hxOpVpQ` | Op "is een mail voldoende?" → "Ja, dat is voldoende" |
| `sess_G5buTzz` | Op "graag aanbellen / naast het huis lossen" → "Ja, dat kan" |
| `sess_9lIjUY` | "Ja, dat kunnen we afleveren" (4 zakken, terwijl minimum 10 is) |

De prompt verbiedt bestellen wél ("You CANNOT place orders"), maar niet het *bevestigen
van administratieve handelingen*: noteren, wijzigen, doorgeven, nakijken, inplannen.

### P0-4 — Interne systeemtaal lekt naar de klant · LIVE

Klanten lezen: "in de context", "in de aangeleverde informatie", en het meest
schadelijke: **"omdat de actuele prijslijst hier niet is ingevuld"**.

Bewijs: `sess_JDhaIfes` (**2026-07-28**), `sess_Rmc` (**2026-07-21**),
`sess_-re9gB` (2026-07-16), plus ~30 oudere.

Twee oorzaken:
1. `backend/knowledge_base/prijzen_topproducten.txt` bestaat maar bevat letterlijk
   `€[INVULLEN]`, `[DATUM INVULLEN]`, `[Vraag aan de eigenaar/beheerder om de actuele
   prijslijst aan te leveren]`. Dat wordt opgehaald en netjes geparafraseerd.
   `openingstijden.txt` heeft hetzelfde probleem (`[TIJDEN INVULLEN]`, `[datum invullen]`).
2. Het woord CONTEXT staat ~30× in de systeemprompt
   ([rag_engine.py:788-800](../backend/rag_engine.py#L788)) zonder enig verbod om het
   tegen de klant te gebruiken.

### P0-5 — "Zoals ik eerder noemde" bij dingen die nooit gezegd zijn · LIVE

De bot claimt eerdere uitspraken en houdt vol na correctie:

> **User:** Dat heb je niet eerder genoemd.
> **Bot:** Zoals ik eerder noemde: de Biologische Moestuinpotgrond bevat turfsoorten…
> (`sess_b0KxUL`)

Ook `sess_D6HoMIM` (bij de *eerste* productvermelding), `sess_PL0j`
(**2026-07-21**, verwijst naar een telefoonnummer dat het nooit gaf).

Oorzaak — de prompt schrijft de frase voor, op twee plekken:
[rag_engine.py:785](../backend/rag_engine.py#L785) en
[:911](../backend/rag_engine.py#L911):
```
"verwijs dan naar je eerdere antwoord: 'Zoals ik eerder noemde...'"
```

### P0-6 — "Graag" leidt tot herhaling of naar de verkeerde flow · LIVE

Twee varianten van hetzelfde gat: er is geen state die bijhoudt *welk aanbod* de bot
net deed.

**(a) Herhaling.** Bot: "Wil je dat ik het omreken naar snijverlies?" → User: "graag" →
Bot herhaalt het vorige antwoord met "Zoals ik eerder noemde".
`sess_RhG2` (**2026-07-24**), `sess_H4Ot9` (**2026-07-20**), `sess_on9ka`,
`sess_tEAsKd`, `sess_X_lJ85`, `sess_BX0sPxp`, `sess_6jCqi`, `sess_4nnfvc`, `sess_tZ6Lbz`.

**(b) Verkeerde flow.** Bot: "Wil je dat ik meedenk over de aanleg?" → User: "Ja graag"
→ Bot: "Ik breng je graag in contact met een collega. Wat is je naam?"
`sess__7oLpL`, `sess_ZZ5-Oy`, `sess_QNy6O`, `sess_SJNuc`, `sess_oq6ZU`.

Bijkomend: in `sess_-re9gB` wordt "Graag" (= ja graag) geantwoord met "Graag gedaan!".

### P1-1 — Intent-misrouting: aankoopvraag → track & trace · LIVE

"Als ik nu bestel, wanneer is het er?" belandt in de zendingnummer-flow.

Bewijs: `sess_7Xo9Rz` (**2026-07-28**), `sess_Z1WoJxD`, `sess_rnLiK9`, `sess_dyMrVfm`,
`sess_4gcOA8`, `sess_d0hsN8`.

`PRE_PURCHASE_RE` ([app.py:320](../backend/app.py#L320)) bestaat maar is te krap:
`als ik (?:\w+\s+){0,5}bestel` faalt op "als ik deze ochtend frans boomschors 1 kuub
bestel" (6 woorden ertussen). En `sess_rnLiK9` toont de absurde uitkomst — op
"Ik heb nog geen bestelling gedaan" antwoordt de bot "Je zendingnummer staat in de
verzendbevestigingsmail".

Verwant: **wijzigings-/annulerings-/restitutieverzoeken** gaan ook naar T&T in plaats
van naar een mens — `sess_rTH9QN`, `sess_t07xU9`, `sess_R1ozEf`, `sess_AzJ5`
(**2026-07-25**, afleverplek wijzigen), `sess_3cqmat`.

### P1-2 — Geen escalatie waar het moet · LIVE

De bot blijft "ik kan dat niet zien" herhalen bij situaties die per definitie een mens
nodig hebben. Ontbrekende triggers, met bewijs:

| Situatie | Sessies |
|---|---|
| Manco / te weinig / half geleverd | `sess_Q7lJWI`, `sess_HLzFUh`, `sess_akcz2`, `sess_07xNFB` |
| Levering te laat (>verwachting) | `sess_YUdjVS` ("we wachten nu 10 dagen"), `sess_rU3Vj0`, `sess_zW4N` (**2026-07-22**) |
| Factuur / aanmaning / betaling | `sess_SCh48` (**2026-07-16**), `sess_B9h3CC`, `sess_nwSmDx` (BTW) |
| Prijsverschil site vs winkelwagen | `sess_GiDjnx` (3× herhaald vóór escalatie) |
| Offerte / bulk / B2B | `sess_wVK_Sh`, `sess_en-gDo`, `sess_Lv59sQ`, `sess_2qw1YT`, `sess_O7LCO1` |
| Telefoon onbereikbaar | `sess_8K0j5`, `sess_8Qchs`, `sess_SCh48`, `sess_LHvfGM` |
| Webshop/checkout kapot | `sess_MI7d` (**2026-07-24**), `sess_nX5s15`, `sess_B9h3CC` |
| Verpakking spreekt de bot tegen | `sess_TDOgT58`, `sess_epXnDes`, `sess_PL0j` (**2026-07-21**) |
| ≥2× "ik heb geen info" op rij | `sess_4nnfvc`, `sess_H4Ot9` (**2026-07-20**), `sess_j5mH` |
| ≥2× zendingnummer niet gevonden | `sess_XMO4Me`, `sess_Zk0FF` (**2026-07-22**) |

De prompt heeft hier een *expliciet verbod* op eigen initiatief
([rag_engine.py:838](../backend/rag_engine.py#L838)): "Stuur NOOIT zelf
`__HUMAN_REQUESTED__` op basis van je eigen oordeel". Dat is bewust (tegen
over-escalatie) maar te absoluut: er is geen categorie "dit type vraag hoort per
definitie bij een mens".

### P1-3 — Taalfouten · LIVE

**(a) NL-vraag, EN-antwoord.** `sess_pIDuLB` (**2026-07-20**, adreswijziging in het
Nederlands → volledig Engels antwoord), `sess_YCFCKgN`, `sess_OW87gm` (hele gesprek).

**(b) Vreemde schrifttekens midden in een Nederlandse zin.** Devanagari en Armeens:
- "mail naar … voor meer **जानकारी**" — `sess_wGocFXem`, `sess_hc9kQb`, `sess_fGnMyH`, `sess_9lIjUY`, `sess_3AN1RZ`, `sess_hxppSa`, `sess_8K0j5`
- "een SKAL-certificaat niet **պարտ** verplicht" — `sess_j5mH`

Dit is een generatiedefect (waarschijnlijk sampling op een meertalige prompt). Het is
niet reproduceerbaar via regels, dus dit hoort in een output-sanitizer.

### P1-4 — Tegenstrijdige antwoorden tussen sessies (KB-fouten) · LIVE

Zelfde vraag, verschillend antwoord. Dit zijn KB-problemen, niet promptproblemen.

| Vraag | Antwoorden |
|---|---|
| Kost kooiaap extra? | "Nee, valt onder standaard bezorging" (`sess_T_AsaSQ`) · "Met een kooiaap leveren wij niet" (`sess_djbcCEg`) · **KB zegt: €100 extra** (`FAQ GCG.txt:55`) |
| 2 m³ = hoeveel bigbags? | "niet als 2 bigbags" (`sess_HcsUoG`) · "Ja, in 2 big bags" (`sess_1hfB8x`) · "2 losse bigbags van 1 m³" (`sess_e04P-E`) · "2 m³ in één big bag" (`sess_aQdGkR`) |
| Gratis verzending? | "vanaf €50 gratis" (`sess_LK06tJ`) · "niet ingevuld" (`sess_wpyhmO`) · "€15, onder €50 is dat €21,95" (`sess_-re9gB`) |
| Telefoonnummer | 0342-784000 · **0324-784000** (`sess_PL0j`, `sess_hxppSa`) — **fout in KB**: `FAQ GCG.txt:133` |
| Kan je een link sturen? | stuurt links (`sess_cfuiN`) · "Ik kan hier geen directe link meesturen" (`sess_xpKCk0`) |

Dat kooiaap-antwoord in twee richtingen fout is terwijl de KB het juiste antwoord bevat,
is het bewijs van de bekende valkuil: **een gewijzigd KB-bestand wordt niet
geherindexeerd** (`_chunk_0`-check, [rag_engine.py:445](../backend/rag_engine.py#L445)),
en `chroma_db` staat op het Railway-volume. De productie-index is stale.

### P2-1 — Ja/nee staat los van de inhoud · LIVE

- "Hebben jullie een certificaat?" → "**Ja**, voor biologische aarde is een
  SKAL-certificaat niet verplicht… wij kunnen dus geen SKAL-certificaat afgeven"
  (`sess_Rmc`, **2026-07-21**)
- "Zijn deze paaltjes geschikt voor 7 mm?" → "**Ja**, die zijn geschikt voor tot 5 mm
  dik. Voor 7 mm zijn ze dus minder geschikt" (`sess_HYTQvO`)
- "Wil je recyclen" → "Nee, wij nemen niet retour" (recyclen ≠ retour) (`sess_PL0j`,
  **2026-07-21**, `sess_TDOgT58`)

### P2-2 — BS-nummers worden productcodes, soms gehallucineerd · LIVE

"BS7950 is een van onze boomschorsproducten" (`sess_i2lToQ`) — verzonnen. Ook
`sess_acsd2`, `sess_YFGnM`, `sess_IRUGI`, `sess_iV-LtP`, `sess_oQAFo`. En
`sess_sKhAHad`: user corrigeert BS64444 → BS6444, bot vraagt "Bedoel je BS64444?"
(corrigeert de verkeerde kant op).

### P2-3 — Reken- en hoeveelheidsfouten · LIVE

- `sess_O7LCO1`: "48 m × 0,80 m × 0,08 m = 3,84 m³" — **is 3,07 m³**. (Dezelfde bot
  rekende 0,06 m even later wél goed: 2,3 m³.)
- `sess_JVwc3X`: "4 × 39 zakken" gelezen als "4 zakken van 39 liter".
- `sess_9lIjUY`: 5 m² bijvullen op 5 cm → "3 tot 4 zakken" (is ~5 zakken van 50 L).
- `sess_OG881c`: weigert 5 cm om te rekenen omdat "in de context staat daar geen exacte
  richtlijn voor" — terwijl het pure rekenkunde is.

### P2-4 — Overige · LIVE

- **Belgische postcode geweigerd** terwijl er naar BE geleverd wordt: "9170" en "B-9170"
  → "Vul een Nederlandse postcode in" (`sess_RQ86kt`).
- **Zendingnummer met spaties niet opgepikt**: "420 836 0360" (`sess_5rPwyJ`).
- **Handoff onderbroken en nooit afgemaakt** — user stelt tussendoor een vraag, bot
  antwoordt en de handoff verdwijnt zonder melding (`sess_SJNuc`).
- **E-mailadres als naam geaccepteerd**: "Leuk je te ontmoeten, [EMAIL_REDACTED]!"
  (`sess_avyJ8`).
- **Handoff herstart na afronding** — "Ik heb je bericht doorgestuurd" → user: "waarom
  komt er geen collega in de chat?" → 4× opnieuw "Wat is je naam?" (`sess_epXnDes`);
  ook `sess_ZKBIp5`, `sess_xX82Gtf`.
- **Grammatica:** "zou wij" i.p.v. "zouden wij" (`sess_RlZ7` **2026-07-28**,
  `sess_JDhaIfes` **2026-07-28**); "de laag niet te dunner laten worden" (`sess_SJNuc`).
- **Papegaai-antwoorden:** "Ja, die 78 cm massieve kunststof paaltjes bedoel je."
  (`sess_2LfTNn`).
- **Land verzonnen:** klant in Breskens (NL) krijgt Belgische betaal- en levertijden
  (`sess_GRAlEgM`).
- **Geplakte product-URL levert niets op** (`sess_xDtNfb`, `sess_k8v1P9`,
  `sess_goVuk` echoot alleen de URL terug).
- **Sarcasme gemist:** "hahaha" → "Haha, fijn om te horen 😊" (`sess_BX0sPxp`).

### FIXED — ter bevestiging, niet meer doen

- **`Mock Product … €29,95` naar echte klanten** (~20 sessies t/m 2026-07-13, incl.
  `sess_Rb2sie` waar de klant vraagt "Wat is Mock Product?"). Dicht via
  `_mocks_allowed()` + `_stock_lookup_enabled()`; bevestigd door `sess_ItDKZ`
  (2026-07-22).
- **Naam "Jarno" → "Geen probleem! 👍"** (`sess_l4PPST`, 2026-07-17). Dicht via
  woordgrens-match in `detect_ticket_intent` (`d7a575f`).
- **Voorraadflow kaapt advies-/handoffvragen** ("Welk product wil je checken?" op
  "kan je mij doorsturen naar een medewerker" — `sess_x6Nu71`). Weg met de gating; komt
  terug zodra de Shopify-token er is → dan moet de intent-prioriteit uit Fase 1 al staan.

---

## 3. Kernoorzaken

Alle 25 categorieën komen terug op vijf dingen:

1. **De state machines zijn kokers zonder nooduitgang.** Eén ingang, één geldige invoer,
   geen escalatie, geen teller, geen loop-detectie.
2. **Er is geen intent-router.** Routing is een reeks losse regexes in volgorde van
   voorkomen; wie het eerst matcht wint. Daardoor pakt T&T aankoopvragen, annuleringen
   en restituties af.
3. **De bot heeft geen besef van zijn eigen laatste zet.** Geen `pending_offer`, dus
   "graag" is niet te interpreteren, en na afronding van een handoff is dat feit weg.
4. **De prompt zegt niet wat de bot *niet mag beweren*.** Wel "geen bestellingen
   plaatsen", niet "geen administratieve handelingen bevestigen" en niet "praat nooit
   over CONTEXT".
5. **De KB is niet af en de productie-index is stale.** Placeholder-bestanden,
   dubbel/fout telefoonnummer, geen verpakkings- of verzendkostentabel — en gewijzigde
   bestanden worden niet opnieuw geïndexeerd.

---

## 4. Plan

Vijf fasen, oplopend risico. Elke fase is los deploybaar, elke fix krijgt een
regressietest in `backend/tests/test_chatlog_regressions.py` (patroon:
`test_fase*_regressions.py`), vernoemd naar de sessie-id uit dit rapport.

### Fase 1 — Nooduitgang + input-validatie (P0-1, P0-2, P2-4-deel) — ✅ AF

Geen LLM-werk, puur deterministisch. Dit stopt de ergste UX-schade.

**Opgeleverd 2026-07-29.** 15 regressietests in
`backend/tests/test_chatlog_regressions.py`, elk vernoemd naar de sessie uit dit
rapport. Twee dingen bleken anders dan gepland:
- **Belgische postcode was al opgelost** — `POSTCODE_RE`
  ([app.py:347](../backend/app.py#L347)) accepteert 4-cijferige codes al. Alleen een
  test toegevoegd zodat het zo blijft.
- **`HUMAN_ESCALATION_RE` had zelf gaten.** "Echte persoon", "Verbind me door",
  "persoon spreken", "doorsturen naar een medewerker" en "iemand van de klantenservice"
  matchten niet. Dat verklaart naast de loops ook `sess_a_jPHmt` ("Ik heb daar op dit
  moment geen directe doorverbindingsoptie voor") en `sess_x6Nu71`. Patronen toegevoegd.

1. **Globale escape-hatch vóór alle state machines** in `_handle_chat`, na het laden van
   `state_data` (~[app.py:980](../backend/app.py#L980)). Eén helper die bij élke
   `awaiting_*` state eerst checkt op `HUMAN_ESCALATION_RE`, `PHONE_CONTACT_RE` en
   `FRUSTRATION_RE`; bij match: state wissen en doorschakelen naar handoff resp. het
   telefoonnummer. Vervangt de losse `PHONE_CONTACT_RE`-checks in
   `awaiting_name`/`awaiting_email` (nu duplicaat op
   [app.py:987](../backend/app.py#L987) en [:1034](../backend/app.py#L1034)).
2. **Poging-teller per flow.** `state_data['<flow>_attempts']`; bij 2 mislukte pogingen
   niet opnieuw hetzelfde bericht maar: state wissen + "Dit lukt me zo niet — wil je dat
   een collega dit oppakt?" (→ handoff bij bevestiging).
3. **Loop-detectie als achtervang.** Laatste bot-bericht in `state_data`; zou het
   antwoord identiek zijn, dan verplicht de escalatievraag. Dekt de gevallen die geen
   enkele regex ziet (`sess_LRVXh5`).
4. **Zendingnummer-regex vervangen** ([app.py:1352](../backend/app.py#L1352)):
   cijfers verplicht. `\b(\d[\d\s.-]{6,24}\d)\b` → spaties/punten strippen (lost
   `sess_5rPwyJ` op) voor StatusWeb; los patroon `\b([A-Z]{2}\s?\d{3,6})\b` voor
   bestelnummers; puur-alfabetische woorden nooit als nummer. Zonder match → geen
   nummer-echo.
5. **Belgische postcode toestaan** in de Shopify-postcodestap
   ([app.py:1302](../backend/app.py#L1302)): 4 cijfers, optioneel `B-`.
6. **E-mail in de naamstap** → sla `awaiting_name` over en gebruik het als e-mailadres
   (`sess_avyJ8`).

*Verificatie:* nieuwe regressietests + handmatig 6 scenario's uit dit rapport
narekenen tegen de lokale Flask-server.

### Fase 2 — KB opschonen + herindexeren (P0-4-deel, P1-4) — ✅ grotendeels af

Dit is de goedkoopste kwaliteitswinst en blokkeert Fase 3 niet.

**Opgeleverd 2026-07-29 — volledig af.** Punt 1, 2, 5 en 6 direct; punt 3 en 4
(verpakkings- en verzendkostentabel) na Wilco's antwoorden, zie
[OPENSTAANDE-VRAGEN-KB.md](OPENSTAANDE-VRAGEN-KB.md) voor wat waar terechtkwam. Twee
nieuwe KB-bestanden: `certificaten_en_keurmerken.txt` (certificaatvragen gaan naar een
mens) en `niet_leverbare_producten.txt` (uitgefaseerd assortiment + het fractie-misverstand
rond Franse Boomschors Premium).

Punt 6 is anders opgelost dan gepland: in plaats van de index eenmalig purgen is de
oorzaak weg. `ingest_documents` slaat nu per chunk een `content_hash` op en
herindexeert een bestand zodra de inhoud wijzigt (oude chunks worden eerst verwijderd).
Renamen of het volume leegmaken is niet meer nodig, en dit was al een openstaand
punt. Gevolg om te weten: chunks die vóór deze wijziging geïndexeerd zijn hebben geen
hash, dus **de eerste boot na deploy her-embedt de hele KB één keer** (kost
embeddings-API-calls, ~12 min koud). Daarna alleen nog gewijzigde bestanden.
5 tests in `backend/tests/test_kb_reindex.py` (fake Chroma-collection, geen API-key
nodig).

1. **Placeholder-bestanden weg uit de KB.** `prijzen_topproducten.txt` en de
   `[INVULLEN]`-regels in `openingstijden.txt` óf vullen óf verwijderen. Zolang ze
   leeg zijn, veroorzaken ze actief schade ("de prijslijst is niet ingevuld").
   Voorstel: verwijderen en één regel toevoegen — "actuele prijzen staan in de webshop"
   — zodat het antwoord klopt zonder intern jargon.
2. **Telefoonnummer fixen:** `FAQ GCG.txt:133` `0324-784000` → `0342 – 784 000`.
3. **Verpakkingstabel toevoegen** die de bigbag-tegenstrijdigheid oplost: per product
   welke bigbag-maten bestaan, en expliciet dat 2 m³ als één 2 m³-bag geleverd wordt
   (of als 2×1 m³ — Wilco beslist, zie §5).
4. **Verzendkostentabel** NL/BE, drempel gratis verzending, pallet vs pakket vs bigbag.
   Nu leidt dit tot drie verschillende antwoorden.
5. **Guard tegen placeholders** — CI-check die faalt als een KB-bestand `INVULLEN`,
   `[datum` of `TODO` bevat. Voorkomt herhaling.
6. **Herindexering forceren.** Verplicht, anders landt niets van bovenstaande in
   productie: `chroma_db/` op het Railway-volume wissen of de bestanden hernoemen
   (bekende valkuil, `CLAUDE.md` §Gotchas). Dit is ook de reden dat de kooiaap-vraag
   fout wordt beantwoord terwijl het juiste antwoord al in de KB staat.

*Verificatie:* `python evaluate_rag.py` vóór én ná (bilt de OpenAI-key — daarom precies
één keer per kant), plus de 5 tegenstrijdige vragen uit P1-4 handmatig stellen.

### Fase 3 — Prompt-hardening (P0-3, P0-4-deel, P0-5, P2-1, P2-4-deel) — ✅ AF

**Opgeleverd 2026-07-30.** Alle 7 punten, in `rag_engine.py`, in beide taalblokken én in
het history-only fallback-blok (dat punt 3 ook voorschreef). 11 regressietests in
`backend/tests/test_fase3_prompt_hardening.py`; die asserten op de systeemprompt die
`get_answer` daadwerkelijk bouwt, met een stub-client, dus zonder OpenAI-calls.

Before/after op 13 echte dialogen tegen productie: [rag/fase3-before-after.md](rag/fase3-before-after.md).
8 bevindingen aantoonbaar opgelost. Drie dingen bleken anders dan gepland:

- **Twee dialogen veranderden niet, en konden dat ook niet.** `sess_1WhsN` en
  `sess_hxOpVpQ` (bestelling wijzigen) gaan nog steeds naar track & trace: de state machine
  in `app.py` vangt het bericht af vóór het LLM, dus het blok "WAT JE NOOIT BEVESTIGT"
  komt er niet aan te pas. Dat is fase 4-werk (`ORDER_ADMIN_RE`) en het is de duidelijkste
  illustratie van de grens van promptwerk.
- **De "geen land afleiden"-regel sloeg eerst door**: geen Belgische tarieven meer, maar
  ook geen Nederlandse. Aangescherpt naar "bij onbekend land uitgaan van Nederland en dat
  benoemen".
- **`sess_HYTQvO` (7 mm-paaltjes) blijft open, maar als KB-gat**: de maatvoering van de
  massieve kunststof paaltjes staat niet in de KB, dus de ja/nee-regel heeft niets om op
  te sturen.

`evaluate_rag.py` is niet gedraaid: fase 3 raakt de prompt, niet de retrieval, en er is
geen lokale index — de vóór/ná-vergelijking is op productie gedaan met echte dialogen.

In `rag_engine.py`, beide taalblokken symmetrisch houden (de EN- en NL-prompt lopen nu
uiteen).

1. **Nieuw blok "WAT JE NOOIT BEVESTIGT".** Expliciete lijst van administratieve
   handelingen die de bot niet kan: noteren, wijzigen, annuleren, inplannen,
   doorgeven aan de chauffeur, nakijken van een order, losplek/tijdstip afspreken.
   Bij zo'n verzoek: geen "ja dat kan", maar handoff. Dekt P0-3 volledig.
2. **Verbod op systeemtaal.** Nooit de woorden "context", "prijslijst is niet ingevuld",
   "aangeleverde informatie", "kennisbank" tegen de klant. Formuleer als klantzin:
   "Die prijs staat in de webshop" i.p.v. "die staat niet in mijn context".
3. **`'Zoals ik eerder noemde'` uit de prompt schrappen**
   ([rag_engine.py:785](../backend/rag_engine.py#L785) en
   [:911](../backend/rag_engine.py#L911)). Vervangen door: bij een vervolgvraag geef je
   het *nieuwe* antwoord; herhaal een eerder antwoord nooit letterlijk; claim alleen iets
   gezegd te hebben als het in de geschiedenis staat; zegt de klant dat je iets niet
   gezegd hebt, betwist dat dan niet.
4. **Ja/nee-regel.** Begin met het woord dat bij de inhoud past; is het antwoord
   "nee, maar…", begin dan niet met "Ja".
5. **Rekenregel.** Volume en dekking mag je altijd uitrekenen — dat is rekenkunde, geen
   kennis. Toon de rekenstap. Vermenigvuldig hoeveelheid × inhoud correct
   (`4 × 39 zakken`). Lost P2-3 deels op; zie ook Fase 5.
6. **Toon:** "zouden wij" niet "zou wij"; geen papegaai-antwoorden ("Ja, die 78 cm
   bedoel je"); "Graag" van de klant is instemming, niet een bedankje.
7. **Geen land afleiden** uit een plaatsnaam; alleen uit expliciete info.

*Verificatie:* de 12 slechtste dialogen uit dit rapport opnieuw naspelen tegen de
aangepaste prompt en de antwoorden vergelijken. Sla de before/after op onder
`improvement-plan/rag/`.

### Fase 4 — Intent-router + escalatiecatalogus (P1-1, P1-2, P2-2) — ✅ AF

**Opgeleverd 2026-07-30.** Alle 6 punten. `classify_intent(message)` in
[app.py](../backend/app.py) neemt nu één routeringsbesluit met vaste prioriteit
(`human_request > order_admin > escalate_topic > pre_purchase > return_payment >
tracking > stock > rag`); de losse regexes in leesvolgorde zijn weg. Het
escalatieblok staat nu vóór track & trace in plaats van erna, wat de kern van P1-1
was. 48 tests in `backend/tests/test_fase4_intent_router.py`, tabelgestuurd met één
rij per bevinding uit P1-1 en P1-2.

**Gevalideerd tegen de echte export, niet alleen tegen de tests.** `classify_intent`
is over alle 803 klantberichten uit `chat-export-2026-07-29.json` gehaald:

| label | aandeel |
|---|---|
| rag | 79,1% |
| order_admin | 5,5% |
| stock (blijft uit tot Shopify) | 4,1% |
| escalate_topic | 3,1% |
| pre_purchase | 3,0% |
| tracking | 2,9% |
| human_request | 1,7% |
| return_payment | 0,6% |

**10,3% gaat naar een mens.** Alle 83 zijn nagelopen; het zijn de gevallen uit P1-1
en P1-2 plus de BS-nummers. Dat laatste is de grootste groep: elke sessie waar de
bot voorheen doodliep op "ik kan niet op bestelnummer zoeken" of een BS-code als
product beschreef.

Twee dingen die deze validatie opleverde en die de tests niet hadden gevonden:

- **De eerste versie van de catalogus miste de meeste échte klantzinnen.** Hij was
  geschreven op de samenvattingen in dit rapport, niet op de transcripten: "er zat
  te weinig aarde in voor wat ik besteld heb" (`sess_HLzFUh`), "Dat staat wel op de
  zak" (`sess_TDOgT58`), "Hij gaat 1x over en daarna wordt het verbroken"
  (`sess_8K0j5`) en "Waarom vragen jullie een andere prijs" (`sess_GiDjnx`) vielen
  allemaal door naar RAG. De patronen werken nu met tekenvensters
  (`[^.?!]{0,40}`) in plaats van woordafstanden, en de testzinnen zijn nu letterlijk
  uit de export overgenomen, inclusief typo's.
- **Eén bewuste niet-escalatie:** "beste prijs" en kortingsvragen blijven bij RAG.
  Daar is bedrijfsbeleid voor ("wij geven geen extra korting"), dus een collega
  ermee lastigvallen kost alleen tijd. `offerte`, `prijsopgave` en `staffel` gaan
  wél door.

Bekende restpunten, klein en bewust: "ik wil weten of ik na bestelling de
bezorgdatum kan doorgeven" (`sess_t9qJlj`) escaleert terwijl het een beleidsvraag is
— een regex ziet het verschil niet tussen "kan dat in het algemeen" en "doe dit voor
mij". En `sess_MI7d` ("Het gaat niet gied op de website") blijft onopgemerkt door de
typo.

De grootste wijziging; daarom na de goedkope winst.

1. **Routing centraliseren.** Eén `classify_intent(message, state)` die vóór de
   state machines één label teruggeeft, met vaste prioriteit:
   `human_request > frustration > order_change > tracking > stock > rag`.
   Geen concurrerende regexes meer in leesvolgorde.
2. **`ORDER_ADMIN_RE`** — wijzigen, annuleren, adres/afleverplek, leverdatum,
   tijdslot, toevoegen aan bestelling, terugbetaling, factuur, aanmaning, BTW.
   Route: **direct handoff**, nooit T&T. Lost `sess_AzJ5`, `sess_rTH9QN`, `sess_t07xU9`,
   `sess_R1ozEf`, `sess_3cqmat` op.
3. **`PRE_PURCHASE_RE` verbreden** — woordafstand `{0,5}` → `{0,10}`, plus
   "nog geen bestelling", "voordat ik bestel", "wil gaan bestellen", "als ik vandaag/
   nu/vanmiddag …". Bij pre-purchase nooit om een zendingnummer vragen.
4. **Escalatiecatalogus** — vertaal de tabel uit P1-2 naar regels die *wel* op eigen
   initiatief mogen escaleren, als afgebakende uitzondering op het huidige absolute
   verbod ([rag_engine.py:838](../backend/rag_engine.py#L838)). Deterministisch waar
   het kan (manco, factuur, offerte, prijsverschil, telefoon onbereikbaar,
   webshop kapot), plus een teller voor "≥2× geen antwoord".
5. **`BS\d{3,6}` als bestelnummer erkennen** — nooit als productcode, nooit
   beschrijven. Route: order-admin → handoff. Lost P2-2 op, inclusief de hallucinatie
   "BS7950 is een van onze boomschorsproducten".
6. **Handoff-state robuust maken:** naam/e-mail bewaren over onderbrekingen heen
   (`sess_SJNuc`), na afronding "al doorgestuurd" onthouden zodat de flow niet
   herstart (`sess_epXnDes`), en een telefoonnummer dat ná de handoff komt meesturen
   (`sess_LHvfGM`).

*Verificatie:* tabelgestuurde tests — één test per rij uit P1-1 en P1-2, met de
originele klantzin uit de export als input.

### Fase 5 — Output-sanitizer + rekenhulp (P1-3, P2-3, P2-4-deel)

1. **Sanitizer op de gegenereerde tekst** vóór verzending:
   - **Vreemde schriften weren.** Bij Devanagari/Armeens/CJK/Cyrillisch in een NL/EN
     antwoord: één keer opnieuw genereren, en anders het antwoord onthouden en loggen.
     Dit is niet met prompting te garanderen — vandaar een harde poort.
   - **Taalcontrole.** Antwoordtaal ≠ gedetecteerde vraagtaal → opnieuw genereren met
     expliciete taalinstructie. Lost `sess_pIDuLB`, `sess_YCFCKgN`, `sess_OW87gm` op.
   - **Lekwoorden-filter** als achtervang op Fase 3 ("in de context", "niet ingevuld").
2. **Deterministische rekenhulp.** Kleine functie voor oppervlak → volume → zakken/
   bigbags, die het LLM aanroept i.p.v. zelf rekent. Lost de 3,84-vs-3,07-fout
   (`sess_O7LCO1`) structureel op; LLM-rekenwerk blijft anders altijd een gok.
3. **Product-URL herkennen.** Slug uit een geplakte boomschors.nl-URL halen en op de
   KB matchen (`sess_xDtNfb`, `sess_k8v1P9`, `sess_goVuk`).
4. **Fallback-teksten variëren** zodat drie keer "geen info" niet drie keer identiek
   klinkt (`sess_LN_B`).

*Verificatie:* unit-tests op sanitizer en rekenhulp (geen API-calls nodig), plus één
end-to-end run van de suite.

---

## 5. Wat ik niet kan beslissen — input van Wilco nodig

Dit is bedrijfsbeleid, geen code. Fase 2 kan starten zonder, maar de KB blijft
onvolledig tot deze antwoorden er zijn.

1. **Prijzen.** Wel of niet in de KB? Nu leidt het ontbreken tot ~40 nutteloze
   antwoorden. Alternatief: nooit prijzen noemen en consequent naar de webshop wijzen
   (dat is eerlijk en onderhoudsvrij). Mijn advies: dat laatste.
2. **Bigbags.** Wordt 2 m³ als één 2 m³-bag of als 2×1 m³ geleverd? Per product?
3. **Verzendkosten.** NL-tarief, BE-tarief, drempel gratis verzending, en of dat per
   pallet/bigbag/pakket verschilt.
4. **Bigbag-hergebruik.** Op de bigbags staat `boomschors.nl/hergebruik`, de KB zegt
   "niet retour". Drie klanten liepen hierop stuk (`sess_epXnDes`, `sess_TDOgT58`,
   `sess_PL0j`) en één zei "volgende keer bestel ik elders". Wat is het beleid?
5. **Certificaten.** SKAL/bio, PFAS, zware metalen, RHP. `sess_Rmc` liep uit op een
   discussie over misleidende marketing — dat is reputatierisico dat de bot niet mag
   voeren.
6. **Uitgefaseerde producten.** Douglas Excellent (HSDE-2), wilgen houtsnippers,
   schapenwol op rol, fracties 40-60 en 45-80: vervangen, uit assortiment, of tijdelijk
   uitverkocht? Klanten vragen er expliciet naar.
7. **Openingstijden feestdagen + telefonische bereikbaarheid** (nu `[INVULLEN]`).

---

## 6. Volgorde en verwachting

| Fase | Raakt | Risico | Levert op |
|---|---|---|---|
| 1 | `app.py` routing | Laag | Geen oneindige loops, geen "GEEN" als bestelnummer |
| 2 | KB + herindex | Laag | Geen prijslijst-lek, consistente antwoorden |
| 3 | prompt | Middel | Geen verzonnen acties, geen valse "zoals ik eerder noemde" |
| 4 | routing + escalatie | Hoog | Juiste flow per vraag, mens waar het moet |
| 5 | post-processing | Laag | Geen taalfouten, kloppend rekenwerk |

Fase 1 en 2 zijn onafhankelijk en kunnen in één deploy. Fase 3 vraagt een
before/after-vergelijking op echte dialogen. Fase 4 is de enige die de architectuur
raakt en gaat als aparte PR met eigen review. Fase 5 kan daarna los.

Na elke fase: `cd backend && python -m pytest` groen, push naar `master`, `/health`
verifiëren. Na Fase 2 en 3 ook `evaluate_rag.py` vóór/ná.

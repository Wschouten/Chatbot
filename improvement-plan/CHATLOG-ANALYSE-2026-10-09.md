# Chatlog-analyse 2026-10-09 — na de rebrand en de code-audit

## Scope en methode

- **Bron:** `chat-export-2026-10-09.json` (242 sessies, 2026-07-14 → 2026-10-09).
- **Focus:** de 63 sessies sinds de rebrand (2026-10-01). Daarvan zijn er **25 eigen replays**
  van de audit-verificatie (herkend aan de testvragen, allemaal 2026-10-09). Er blijven
  **38 echte gesprekken** over, en die zijn alle 38 gelezen.
- **Scanner:** `scan_chatlog.py` over de hele export, met `--since 2026-08-25` (laatste fixronde
  vóór de rebrand) en met `--since 2026-10-01`.
- **LIVE / FIXED:**
  - Een bevinding is **LIVE** als de oorzaak nog in de huidige code (`5eefd79`) zit. Elke LIVE
    bevinding hieronder is tegen die code nagespeeld, niet alleen uit het transcript afgeleid.
  - Een bevinding is **FIXED** als de oorzaak aantoonbaar weg is.
- **Belangrijke beperking:** de echte gesprekken van vandaag zijn van 07:37 UTC. De audit-fixes
  gingen vanaf ~11:00 UTC live, de Railway-startopdracht om ~13:51 UTC. Deze export laat de
  fixes van vandaag dus nog **niet** zien bij echte klanten. Een export over een week wel.

## Wat werkt — niet breken

- **De rebrand is volledig goed.** Vijf varianten van "wie zijn jullie?" en "Ground Cover
  Group?" worden correct beantwoord. De oude naam komt alleen ter sprake als de klant er zelf
  naar vraagt.
- **Telefoon en openingstijden:** na `0dfa43c` krijgt elke telefoonvraag nummer én tijden.
  België krijgt het internationale nummer.
- **Afhalen** gaat sinds `afa817b` naar het afhaalantwoord, niet naar tracking.
- **Advies is sterk.**
  - Looppad: fractie, laagdikte, worteldoek.
  - Worteldoek versus anti-worteldoek.
  - Metergoed uitgelegd.
  - 7 m³ correct opgedeeld in bigbags.
  - Bezorgkosten NL/BE en de kooiaap-toeslag.
  - Kortingscode eerlijk geweigerd.
- **Onzin en Arabisch schrift** (`sess_TVIxba`, 10-03) worden kalm en in het Nederlands
  afgehandeld. De output-poort lekt niets.
- **De dead-end-escalatie werkt in het echt** (`sess_xiw2`, 10-06): na twee mislukte pogingen
  zegt de bot "Dit lukt me zo niet — laat ik een collega ernaar kijken" en volgt een
  geslaagde overdracht.

## Scanner: eerdere fixes houden stand

De scanner draaide over de 116 sessies sinds 2026-08-25 (inclusief de 25 eigen replays).

| Check | Hele export | Sinds 08-25 | Sinds 10-01 |
|---|---|---|---|
| leak (systeemtaal) | 6 | 0 | 0 |
| mock | 0 | 0 | 0 |
| garbage_ref | 3 | 0 | 0 |
| prior_claim | 5 | 0 | 0 |
| no_escalation | 4 | 0 | 0 |
| handoff_unfinished | 16 | 5 | 4 → **0 echt** (alle 4 zijn eigen replays) |
| loop | 6 | 3 | 1 (`sess_aKZjz`, zie B1) |
| lang_flip | 9 | 2 | 1 (`sess_xiw2`, zie C1) |

## Bevindingen (LIVE, op prioriteit)

### B1 — Klant zonder e-mailadres raakt de overdracht kwijt (klasse 12) · LIVE

`sess_aKZjz0ks` (2026-10-05). De klant probeert drie keer een medewerker te bereiken:

> **K:** Kan ik een medewerker spreken · **B:** … Wat is je naam? · **K:** Leonie ·
> **B:** … Wat is je e-mailadres? · **K:** Heb ik niet ·
> **B:** Geen probleem! 👍 Waarmee kan ik je verder helpen?
> …
> **K:** Die heb ik niet ik wil graag een medewerker spreken · **B:** Ik pak dit op met een collega,
> Leonie. Wat is je e-mailadres? · **K:** Heb ik niet · **B:** Geen probleem! 👍 Waarmee kan ik je
> verder helpen?

Pas bij de derde poging verzint ze een e-mailadres.

**Oorzaak:** in `awaiting_email` labelt `detect_ticket_intent` "heb ik niet" als `declining`
([app.py, awaiting_email](../backend/app.py)). Dat wist de overdracht. Sinds vandaag
(`901e34b`) neemt de overdracht wel een telefoonnummer mee, maar de bot **vraagt** er nooit om.
Een klant zonder e-mail heeft dus geen route.

### C1 — Een kort bericht zet een Nederlands gesprek op Engels (klasse 8) · LIVE

`sess_xiw2GqQW` (2026-10-06):

> **K:** order PGBE-12 · **B:** I can't check order PGBE-12 from here. If you mean the payment
> reference, please send it to …

**Oorzaak:** [app.py:2112](../backend/app.py) roept bij elk RAG-bericht
`rag_engine.detect_language(user_message)` aan, een losse LLM-call zonder gesprekscontext. Die
uitkomst overschrijft de taal van de sessie. "order PGBE-12" komt terug als `en`.
`guess_language` geeft hier terecht `None` (onbeslist), maar wordt in dit pad niet gebruikt. De
output-poort ziet geen fout, want antwoord en gedetecteerde taal zijn allebei Engels. Dit is
opruimpunt 3 uit de audit, maar dan als echte bug.

### A1 — "Wanneer komt het weer op voorraad?" krijgt de zendingnummervraag (klasse 3) · LIVE

`sess_SDLBLRHc` (2026-10-04):

> **K:** … zie dat dit niet op voorraad is. Wanneer komt het weer op voorraad? ·
> **B:** Dat kan ik voor je opzoeken! Geef je **zendingnummer** door …
> **K:** Ik heb nog geen bestelling geplaatst · **B:** Geen probleem! Je zendingnummer staat in de
> verzendbevestigingsmail die je hebt ontvangen. …

Hier zitten twee fouten in.

1. **Routering:** `classify_intent` geeft nog steeds `tracking`. Het patroon `wanneer komt` in
   `TRACKING_INTENT_RE` wint van `STOCK_INTENT_RE` ("op voorraad"), dat lager in de volgorde staat.
2. **Binnen de flow:** "Ik heb nog geen bestelling geplaatst" is `pre_purchase`, maar is geen
   escape uit de trackingflow. Het matcht `NO_SHIPMENT_NUMBER_RE`, dus de klant krijgt te horen
   dat het zendingnummer in een mail staat die nooit verstuurd is.

   Dit gat ontstond vandaag. Het oude `NO_ORDER_YET_RE` hoorde alleen bij de verwijderde
   Shopify-flow (`305e303`), en in de trackingflow is "nog niet besteld" nooit afgevangen.

### A2 — "Wil hetzelfde opnieuw bestellen" krijgt de zendingnummervraag (klasse 3) · LIVE

`sess_xiw2GqQW` (2026-10-06):

> **K:** ik heb mijn bestelling gehad, maar wil hetzelfde bestellen · **B:** Dat kan ik voor je
> opzoeken! Geef je **zendingnummer** door …

**Oorzaak:** `mijn bestelling` in `TRACKING_INTENT_RE`. Een nabestelling is een koopvraag. Dit
gesprek eindigde goed via de dead-end-escalatie, maar pas na twee nutteloze beurten.

### F1 — Informatie na de overdracht verdwijnt, en de bot belooft mee te kijken (klasse 1) · LIVE

`sess_xiw2GqQW`, na een geslaagde overdracht:

> **K:** PGBE-12442 · **B:** Dank je, maar met alleen zendingnummer PGBE-12442 kan ik hier de status
> niet direct zien. Als je wilt, stuur ook even je ordernummer of de naam … dan kijk ik met je mee.

Hier zitten twee fouten in.

1. **De referentie verdwijnt.** Alleen een **telefoonnummer** wordt na de overdracht
   doorgestuurd (`_forward_phone_number`). Een betaalreferentie of ordernummer, precies wat de
   collega nodig heeft, gaat nergens heen.
2. **Een verzonnen actie.** "dan kijk ik met je mee" kan de bot niet waarmaken.

### G1 — "Spreek ik nu met AI of een medewerker?" krijgt geen eerlijk antwoord · LIVE, klein

`sess_aKZjz0ks`:

> **K:** Ja en spreek ik nu met ai of een medewerker? · **B:** Je bericht staat al bij een collega —
> die neemt zo snel mogelijk contact met je op via e-mail.

De bot zegt niet dat hij een AI-assistent is. Die vraag hoort een direct antwoord te krijgen.

## Kennisbank-vragen (business, niet raden)

**K1 — Bezorgkosten voor bigbags: twee verschillende antwoorden (klasse 9).**

- `sess_afpX9V` (10-03): "voor een big bag van 1 m³ gelden de gewone bezorgkosten … vanaf € 50
  gratis".
- `sess_kyL057` (10-05): "De standaard bezorgkosten voor Nederland gelden dan niet; voor big bags
  kan er een andere levering van toepassing zijn."

Eén van beide klopt niet, of de KB is vaag.

**K2 — "Klinkt deze aarde in?"** (`sess_TdnOF4`, 10-09): de bot heeft geen informatie over
inklinken. Een terechte klantvraag bij ophogen.

**K3 — PGBE-12442** (`sess_xiw2`): een Belgische klant noemt dit zijn zending- en betaalreferentie.
Is "PGBE-…" een herkenbaar formaat (bijvoorbeeld een Belgische orderreferentie)? Dan kan de bot
het herkennen en doorzetten.

## Grondoorzaken

1. **De router mist twee koop-signalen.** Een voorraadvraag en een nabestelling verliezen van
   brede tracking-woorden (`wanneer komt`, `mijn bestelling`). → A1, A2
2. **De trackingflow kent "ik heb nog niet besteld" niet als uitweg.** → A1 (tweede helft)
3. **De handoff-flow heeft geen telefoonroute.** De bot vraagt nooit om een nummer, en wat de
   klant na de overdracht toevoegt verdwijnt, behalve een telefoonnummer. → B1, F1
4. **De taalkeuze per bericht negeert het gesprek.** → C1

## Fases (oplopend risico)

**Fase 1 — router en trackingflow (deterministisch, `app.py`)**

- `STOCK_INTENT_RE` boven `tracking` voor voorraadvragen zonder bestelwoord. Of: `wanneer komt`
  vereist een bestelwoord, net als `wanneer kunnen/wordt` in `d871f04`.
- Een nabestel-patroon ("hetzelfde (nog eens) bestellen", "opnieuw bestellen", "nabestellen")
  als `pre_purchase`.
- In de trackingflow: `pre_purchase` (waaronder "nog geen bestelling geplaatst") laat de flow
  los en valt door naar de router.
- *Verificatie:* tests `test_sess_sdlblr_…`, `test_sess_xiw2_…`. Eerst alle exportberichten door
  `classify_intent` halen, met een diff voor/na.

**Fase 2 — telefoonroute in de overdracht (`app.py`)**

- "heb ik niet" / "geen e-mail" in `awaiting_email` wist de overdracht niet meer, maar vraagt om
  een telefoonnummer. Het doorsturen bestaat al (`901e34b`).
- Na `handoff_done` wordt een ordernummer of betaalreferentie één keer doorgestuurd, net als
  `_forward_phone_number`, met een eerlijke bevestiging ("Ik heb het aan je collega doorgegeven").
- *Verificatie:* `test_sess_akzjz_…` en `test_sess_xiw2_reference_after_handoff_is_forwarded`,
  plus één echte testescalatie naar klantenservice (vooraf afstemmen met Wilco).

**Fase 3 — taal (`app.py`, raakt retrieval)**

- In het RAG-pad: `guess_language(msg) or state_data['language']`. De LLM-detector alleen voor
  een eerste bericht dat de heuristiek niet beslist. Dit is opruimpunt 3 uit de audit.
- *Verificatie:* `test_sess_xiw2_short_reference_keeps_dutch`, plus `evaluate_rag.py` één keer
  vóór en één keer na. **Dat kost OpenAI-geld.**

**Fase 4 — prompt (`rag_engine.py`)**

- Op "praat ik met een AI?" eerlijk antwoorden.
- Geen "dan kijk ik met je mee" of andere acties die de bot niet kan uitvoeren.
- *Verificatie:* naspelen van `sess_aKZjz` en `sess_xiw2` tegen productie.

**Fase 5 — kennisbank, na antwoorden op K1–K3**

## Open vragen voor Wilco

1. **K1:** wat kost bezorging van een bigbag in Nederland? Gelden de gewone bezorgkosten (gratis
   vanaf € 50), of een apart tarief?
2. **K2:** hoeveel klinkt tuinaarde (bemest/onbemest) in na het ophogen? Een vuistregel volstaat,
   bijvoorbeeld "reken 10–20 % extra".
3. **K3:** wat is een "PGBE-…"-referentie? Komt die uit de Belgische webshop of de betaalprovider?
4. **B1:** mag de bot een klant zonder e-mail om een telefoonnummer vragen en een terugbelverzoek
   doorzetten? Kan de klantenservice terugbellen?

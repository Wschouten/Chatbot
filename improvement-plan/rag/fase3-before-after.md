# Fase 3 — before/after op echte dialogen

Verificatie van de prompt-hardening uit fase 3 ([CHATLOG-ANALYSE-2026-07-29.md](../CHATLOG-ANALYSE-2026-07-29.md)).

**Methode.** De originele klantzinnen uit het rapport opnieuw gesteld tegen de live
`/api/chat` (`chatbot-production-557f.up.railway.app`) na de fase-3 deploy, elk in een
verse sessie. De "voor"-antwoorden komen uit de productie-export van 2026-07-29 zoals
geciteerd in het rapport. Lokaal naspelen kon niet: er is geen lokale `chroma_db`, en een
ingestie kost embeddings-API-calls.

**Uitkomst:** 8 van de 13 bevindingen aantoonbaar opgelost, 2 onveranderd omdat de oorzaak
in fase 4 zit, 1 KB-gat, 2 kwamen na de eerste deploy alsnog boven en zijn direct nagefixt.

---

## Opgelost

| Sessie | Voor | Na |
|---|---|---|
| `sess_zCbDEIy` (P0-3) | "Dank je, 26 mei 2026 heb ik genoteerd als voorkeursdatum" + "je krijgt daar bericht over" | "Ik kan dat niet voor je noteren. Wel kun je bij het bestellen in het opmerkingenveld 26 mei 2026 als gewenste leverdatum invullen." |
| `sess_G5buTzz` (P0-3) | "Ja, dat kan" op "graag aanbellen / naast het huis lossen" | "Ik kan dat niet voor je vastleggen. […] Voor aanbellen of een specifieke losplek kan ik het niet garanderen." |
| `sess_JDhaIfes` (P0-4) | "omdat de actuele prijslijst hier niet is ingevuld" | "De prijs van de 1 m³ bigbag kan ik hier niet zien. Die vind je in de webshop." + productlink |
| `sess_Rmc` (P2-1) | "**Ja**, voor biologische aarde is een SKAL-certificaat niet verplicht… wij kunnen dus geen SKAL-certificaat afgeven" | "**Nee**, die hebben wij niet. Voor particulier gebruik in de eigen tuin is dat ook niet verplicht." |
| `sess_O7LCO1` (P2-3) | "48 m × 0,80 m × 0,08 m = **3,84 m³**" | "48 × 0,8 × 0,08 = **3,072 m³** […] ongeveer 3,1 kuub" |
| `sess_OG881c` (P2-3) | weigerde 5 cm om te rekenen: "in de context staat daar geen exacte richtlijn voor" | "Voor 5 m² met een laag van 5 cm heb je 0,25 m³ nodig. Rekening: 5 × 0,05 = 0,25 m³" |
| `sess_RhG2` (P0-6a) | "graag" → vorige antwoord herhaald met "Zoals ik eerder noemde" | geen herhaling, geen frase; bot borduurt voort op de berekening |
| `sess__7oLpL` (P0-6b) | "Ja graag" op een adviesaanbod → "Ik breng je graag in contact met een collega. Wat is je naam?" | blijft in het advies: fractie-advies 25–40 mm voor borders |

De frase "Zoals ik eerder noemde" komt in geen van de 13 dialogen meer voor, en geen enkel
antwoord bevat nog "context", "kennisbank" of "prijslijst".

## Onveranderd — oorzaak zit in fase 4, niet in de prompt

`sess_1WhsN` ("kunnen jullie BS6794 wijzigen naar…") en `sess_hxOpVpQ` ("bestelling
wijzigen, is een mail voldoende?") gaan nog steeds naar track & trace:

> Dat kan ik voor je opzoeken! Geef je **zendingnummer** door (bijv. **400000001**).

Dat is P1-1 / `ORDER_ADMIN_RE`, en het toont een grens van fase 3: het bericht bereikt het
LLM nooit, want de state machine in `app.py` vangt het eerder af. Het nieuwe blok
"WAT JE NOOIT BEVESTIGT" kan hier per definitie niets doen. **Fase 4-werk.**

## KB-gat, geen promptprobleem

`sess_HYTQvO` — "geschikt voor planken van 7 mm dik?" levert nu geen valse "Ja, tot 5 mm"
meer op, maar met de productnaam erbij antwoordt de bot "Ja, dat kan in principe" en
hedget daarna. De KB bevat de maatvoering van de massieve kunststof paaltjes niet, dus de
ja/nee-regel heeft niets om zich op te baseren. Los dit op in de KB (paaltjes-specificaties),
niet in de prompt.

## Na de eerste deploy alsnog gevonden — direct nagefixt

1. **De "geen land afleiden"-regel was te streng.** `sess_GRAlEgM` gaf geen Belgische
   tarieven meer (het doel), maar ook geen Nederlandse: "Ik heb niet meteen de exacte
   verzendkosten en levertijd voor Breskens bij de hand." Zonder plaatsnaam antwoordt hij
   wél correct ("€ 6,95 voor kleine pakketten, vanaf € 50 gratis"), dus de KB was niet het
   probleem — de regel was het. Regel aangescherpt: geen land afleiden, maar bij een
   onbekend land uitgaan van Nederland en dat benoemen.
2. **Een opmerking over het gesprek werd als kennisvraag behandeld.** `sess_b0KxUL`, tweede
   turn: "Dat heb je niet eerder genoemd." → "Dat kan ik hier niet zien." Geen valse claim
   meer (winst), maar ook geen antwoord. Regel toegevoegd: zo'n opmerking is geen
   kennisvraag — kort reageren en het antwoord opnieuw geven.

Beide zijn afgedekt met een regressietest in
`backend/tests/test_fase3_prompt_hardening.py`.

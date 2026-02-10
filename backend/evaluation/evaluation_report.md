# RAG Evaluation Report

**Date:** 2026-02-06 15:26:36

## Overall Performance

- **Total Questions:** 28
- **Passed:** 28
- **Pass Rate:** 100.0%
- **Average Latency:** 3.02s

## Performance by Category

| Category | Questions | Pass Rate | Avg Latency | Avg Keyword Score | Avg LLM Score |
|----------|-----------|-----------|-------------|-------------------|---------------|
| cross_product | 5 | 100.0% | 4.12s | 0.61 | 4.2/5 |
| english | 3 | 100.0% | 4.00s | 0.27 | 4.7/5 |
| faq_policy | 6 | 100.0% | 2.08s | 0.78 | 4.8/5 |
| hallucination_check | 4 | 100.0% | 1.42s | 1.00 | 5.0/5 |
| product_info | 10 | 100.0% | 3.37s | 0.61 | 4.4/5 |

## Detailed Results


### cross_product

**1. ✓ PASS** - Ik wil onkruid tegengaan in mijn border, wat raden jullie aan?

- **Answer:** Voor onkruid in je border raden wij meestal Houtmulch of Houtsnippers aan, afhankelijk van wat je het belangrijkst vindt.

- Houtmulch: beste onkruidonderdrukking als dichte toplaag, houdt ook mooi vo...
- **Keyword Score:** 0.50
- **LLM Score:** 4/5 - Het antwoord is relevant en praktisch: het noemt geschikte bodembedekking (houtmulch/houtsnippers), geeft laagdikte en levensduur en legt de afweging uit. Het mist wel expliciete vermelding van boomschors en worteldoek, en had kort kunnen ingaan op voorbereiding (onkruid verwijderen) voor maximaal effect.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.71s

**2. ✓ PASS** - Welke borderrand past bij mijn tuin?

- **Answer:** Dat hangt vooral af van de vorm die je wilt maken en hoe “strak” je het wilt hebben. In het kort:

- Wil je vooral rechte lijnen of een stevige vijverrand met een strak resultaat? Dan past Ecolat Bord...
- **Keyword Score:** 0.80
- **LLM Score:** 5/5 - Het antwoord noemt alle verwachte opties (Ecolat, Ekoboard, Recy-Edge) en koppelt ze duidelijk aan gebruikssituaties (strak/recht, bochten, budget/modern). Het is relevant, praktisch en sluit af met een gerichte vervolgvraag om beter te adviseren.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.85s

**3. ✓ PASS** - Wat is beter: boomschors of houtsnippers?

- **Answer:** Dat hangt vooral af van wat je belangrijk vindt: levensduur/uitstraling of snelheid/bodemverbetering.

Boomschors is meestal “beter” als je een langdurige, nette bodembedekking wilt:
- Gaat langer mee...
- **Keyword Score:** 0.83
- **LLM Score:** 4/5 - Het antwoord vergelijkt boomschors en houtsnippers duidelijk op levensduur, verteren/bodemverbetering en uitstraling, en geeft praktische richtlijnen voor laagdikte en onkruidwering. Het is nuttig en grotendeels compleet, maar mist enkele nuances zoals toepassing per plantsoort/zuurgraad, stikstofbinding bij verse snippers en onderhoud/aanvullen.
- **Hallucination Check:** ✓ Pass
- **Latency:** 4.18s

**4. ✓ PASS** - Hoe bescherm ik mijn planten tegen vorst?

- **Answer:** Tegen vorst helpen vooral een goede bodembedekkende laag en zorgen dat de grond niet kaal ligt. Bij ons werken boomschors, houtsnippers of houtmulch daar heel goed voor, omdat ze de bodem isoleren en ...
- **Keyword Score:** 0.50
- **LLM Score:** 4/5 - Het antwoord is relevant en praktisch: het legt uit hoe een isolerende mulchlaag (boomschors/houtsnippers/houtmulch) tegen vorst helpt en geeft concrete laagdiktes. Het mist wel andere veelgebruikte opties zoals schapenwol/vliesdoek en bescherming van bovengrondse delen, waardoor het minder compleet is.
- **Hallucination Check:** ✓ Pass
- **Latency:** 4.78s

**5. ✓ PASS** - Wat heb ik nodig voor een speeltuin in mijn tuin?

- **Answer:** Voor een speeltuin in je tuin heb je vooral een goede valdempende ondergrond nodig onder en rondom de toestellen. Daarvoor gebruiken veel mensen onze Speelmix (Bojardin): die is speciaal gemaakt voor ...
- **Keyword Score:** 0.40
- **LLM Score:** 4/5 - Het antwoord is relevant en behandelt de belangrijkste veiligheidsfactor (valbrekende/valdempende ondergrond) met concrete richtlijnen over laagdikte en valhoogte. Het is wel wat productgericht en noemt niet expliciet gangbare materialen zoals houtsnippers of boomschors, en mist bredere aandachtspunten (ruimte, verankering, onderhoud), waardoor het net geen 5 is.
- **Hallucination Check:** ✓ Pass
- **Latency:** 4.07s


### english

**1. ✓ PASS** - What types of bark mulch do you sell?

- **Answer:** Wij hebben in ons assortiment een paar soorten bodembedekking op basis van schors/hout die hierop aansluiten:

- Franse boomschors
- Dennenschors
- Houtmulch (gemaakt van naaldboomschors, fijne/ongeze...
- **Keyword Score:** 0.00
- **LLM Score:** 4/5 - The answer clearly lists multiple bark mulch types including French bark and pine bark, and mentions a fine/unsieved wood mulch variant, matching the expected keywords. It could be slightly more complete by explicitly distinguishing coarse vs fine grades for the bark products themselves.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.45s

**2. ✓ PASS** - How do I install border edging?

- **Answer:** Voor het plaatsen van een borderrand werken we meestal met dezelfde basis: lijn uitzetten, een sleuf graven, rand plaatsen, vastzetten met paaltjes/pennen en weer aanvullen. De exacte stappen hangen a...
- **Keyword Score:** 0.40
- **LLM Score:** 5/5 - The answer gives clear, step-by-step installation guidance including digging a trench, placing the edging, securing it with stakes/posts at appropriate spacing (e.g., 40–50 cm, 50 cm, 80 cm), and backfilling/compacting. It directly addresses the expected keywords and adds helpful variations for different edging types and curves.
- **Hallucination Check:** ✓ Pass
- **Latency:** 6.13s

**3. ✓ PASS** - What are hydrokorrels used for?

- **Answer:** Hydrokorrels gebruiken wij vooral om de drainage, waterhuishouding en luchtcirculatie in bloempotten en plantenbakken te verbeteren. Ze nemen overtollig water op en geven dat geleidelijk weer af, terw...
- **Keyword Score:** 0.40
- **LLM Score:** 5/5 - Het antwoord legt correct uit dat hydrokorrels (kleikorrels) vooral worden gebruikt voor drainage en betere waterhuishouding/luchtcirculatie in potten, wat de wortels gezond houdt en wortelrot helpt voorkomen. Het is bovendien praktisch met duidelijke toepassingsmogelijkheden en sluit aan bij de verwachte keywords.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.42s


### faq_policy

**1. ✓ PASS** - Hebben jullie kortingscodes?

- **Answer:** Nee, wij werken niet met kortingscodes. Onze producten zijn al scherp geprijsd of staan al in een aanbieding.

Gaat het om één bestelling of meerdere pallets? Dan kan ik meteen aangeven wat er wel en ...
- **Keyword Score:** 0.75
- **LLM Score:** 5/5 - Het antwoord geeft duidelijk aan dat er geen kortingscodes zijn en motiveert dit met scherpe prijzen/aanbiedingen. Daarnaast is het behulpzaam door door te vragen naar de ordergrootte om eventuele korting te bespreken.
- **Hallucination Check:** ✓ Pass
- **Latency:** 1.76s

**2. ✓ PASS** - Wanneer wordt mijn bestelling geleverd?

- **Answer:** In Nederland leveren we de meeste producten binnen 1 tot 3 werkdagen. Voor België en voor zandproducten is dat meestal 1 tot 5 werkdagen.

Gaat het bij jou om levering in Nederland of België, en is he...
- **Keyword Score:** 0.83
- **LLM Score:** 5/5 - Het antwoord geeft duidelijke levertijden (1-3 werkdagen NL, 1-5 werkdagen BE/zandproducten) en noemt expliciet Nederland, België en zandproducten. De vervolgvraag helpt om de juiste levertijd te bepalen, wat het extra behulpzaam maakt.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.07s

**3. ✓ PASS** - Kan ik contant betalen?

- **Answer:** Nee, dat kan helaas niet. Bij ons kun je alleen via de webshop betalen (dus niet contant bij levering).

Wil je betalen met een specifieke methode (bijv. iDEAL of creditcard), of gaat het je vooral om...
- **Keyword Score:** 0.50
- **LLM Score:** 5/5 - Het antwoord geeft duidelijk aan dat contant betalen niet mogelijk is en dat betaling uitsluitend via de webshop kan. Daarnaast is het behulpzaam door door te vragen naar de gewenste betaalmethode of betalen bij aflevering.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.16s

**4. ✓ PASS** - Is jullie tuinaarde PFAS-vrij?

- **Answer:** Nee, we kunnen geen verklaring afgeven dat onze (bemeste) tuinaarde volledig PFAS-vrij is. In de tuinaarde zit compost, en daarbij kunnen we PFAS-verontreiniging niet 100% uitsluiten.

Gaat het om onz...
- **Keyword Score:** 0.83
- **LLM Score:** 5/5 - Het antwoord geeft duidelijk aan dat er geen garantie kan worden gegeven dat de (bemeste) tuinaarde PFAS-vrij is en legt dit logisch uit door de aanwezigheid van compost en mogelijke contaminatie. Het is bovendien behulpzaam door door te vragen naar het specifieke product en een passend alternatief aan te bieden.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.29s

**5. ✓ PASS** - Kan ik mijn bestelling retourneren?

- **Answer:** Ja, dat kan. Als je wilt retourneren, neem even contact op met onze klantenservice; dan plannen we de retour samen in. De retourkosten zijn wel voor eigen rekening.

Wil je alles retourneren, of gaat ...
- **Keyword Score:** 1.00
- **LLM Score:** 4/5 - Het antwoord bevestigt dat retourneren mogelijk is, verwijst naar contact met de klantenservice en noemt dat de retourkosten voor eigen rekening zijn. Het is duidelijk en behulpzaam, maar mist eventuele voorwaarden zoals retourtermijn of procedurestappen.
- **Hallucination Check:** ✓ Pass
- **Latency:** 1.56s

**6. ✓ PASS** - Leveren jullie in het weekend?

- **Answer:** Nee, wij leveren niet in het weekend. Leveringen doen we alleen op werkdagen.

Wil je dat we de levering op een specifieke werkdag plannen? Dan kun je die datum bij je bestelling in het opmerkingenvel...
- **Keyword Score:** 0.75
- **LLM Score:** 5/5 - Het antwoord zegt duidelijk dat er niet in het weekend geleverd wordt en dat leveringen uitsluitend op werkdagen plaatsvinden. Daarnaast biedt het een praktische optie om een specifieke werkdag te plannen, wat extra behulpzaam is.
- **Hallucination Check:** ✓ Pass
- **Latency:** 1.63s


### hallucination_check

**1. ✓ PASS** - Verkopen jullie ook meststoffen?

- **Answer:** __UNKNOWN__
- **Keyword Score:** 1.00
- **LLM Score:** 5/5 - Hallucination check
- **Hallucination Check:** ✓ Pass
- **Latency:** 0.92s

**2. ✓ PASS** - Wat is de prijs van boomschors?

- **Answer:** __UNKNOWN__
- **Keyword Score:** 1.00
- **LLM Score:** 5/5 - Hallucination check
- **Hallucination Check:** ✓ Pass
- **Latency:** 0.91s

**3. ✓ PASS** - Kunnen jullie mijn tuin ontwerpen?

- **Answer:** __UNKNOWN__
- **Keyword Score:** 1.00
- **LLM Score:** 5/5 - Hallucination check
- **Hallucination Check:** ✓ Pass
- **Latency:** 1.28s

**4. ✓ PASS** - Hebben jullie ook plantenbakken?

- **Answer:** __UNKNOWN__
- **Keyword Score:** 1.00
- **LLM Score:** 5/5 - Hallucination check
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.56s


### product_info

**1. ✓ PASS** - Wat is het verschil tussen Franse boomschors en dennenschors?

- **Answer:** Franse boomschors en dennenschors doen in de basis hetzelfde (onkruid remmen, vocht vasthouden en de bodem beschermen), maar ze verschillen vooral in structuur, uitstraling en levensduur:

- Franse bo...
- **Keyword Score:** 0.67
- **LLM Score:** 4/5 - Het antwoord benoemt de kernverschillen (grover vs fijner, uitstraling/prijs en levensduur/duurzaamheid) en sluit aan bij de verwachte keywords. Het is goed, maar mist wat nuance over herkomst/soort (bijv. vaak pijnboomschors) en toepassingsadvies kan iets concreter.
- **Hallucination Check:** ✓ Pass
- **Latency:** 6.14s

**2. ✓ PASS** - Hoe dik moet ik houtsnippers leggen?

- **Answer:** Voor houtsnippers houden wij dit aan:

- Minimaal 5 cm
- Het mooist en het meest effectief tegen onkruid: 8–10 cm

Op klei- of leemgrond is 8 cm vaak al genoeg. Heb je zand- of humusrijke grond, dan r...
- **Keyword Score:** 0.80
- **LLM Score:** 5/5 - Het antwoord noemt duidelijk de minimale laagdikte (5 cm) en de aanbevolen dikte voor beste effect (8–10 cm), precies passend bij de verwachte keywords. Daarnaast geeft het nuttige nuance per bodemtype en bij gebruik van worteldoek en stelt een vervolgvraag voor context.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.69s

**3. ✓ PASS** - Welke kleuren houtsnippers zijn er?

- **Answer:** We hebben houtsnippers in vier kleuren:

- Naturel (lichtbruin)
- Blanco (licht en modern)
- Rood (warm en levendig)
- Bruin (klassiek/natuurlijk)

Waar wil je ze voor gebruiken: vooral decoratief in ...
- **Keyword Score:** 0.50
- **LLM Score:** 4/5 - Het antwoord noemt de belangrijkste kleuren (naturel/lichtbruin, blanco, rood, bruin) en sluit goed aan bij de verwachte keywords. Het is duidelijk en behulpzaam, maar niet heel uitgebreid (bijv. geen vermelding van andere mogelijke gekleurde varianten of nuances per leverancier).
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.16s

**4. ✓ PASS** - Hoeveel boomschors heb ik nodig voor 70 vierkante meter?

- **Answer:** Voor 70 m² hangt het vooral af van welke laagdikte je kiest:

- Minimaal 8 cm: 70 × 0,08 = 5,6 m³ boomschors
- Optimaal (mooier en beter tegen onkruid) 10 cm: 70 × 0,10 = 7,0 m³
- Extra stevig 15 cm: ...
- **Keyword Score:** 0.40
- **LLM Score:** 5/5 - Het antwoord geeft een duidelijke formule (oppervlakte × laagdikte) en rekent dit correct om naar m³ voor meerdere gangbare laagdiktes. Het sluit aan bij de verwachte keywords en biedt nuttige vervolgvraag over toepassing en fractie.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.78s

**5. ✓ PASS** - Is schapenwol goed tegen slakken?

- **Answer:** Ja, schapenwol is daar juist heel geschikt voor. Bij ons Bio Sheep Wool heeft een ruwe structuur, en die schrikt slakken af. Zo helpt het je planten en gewassen te beschermen zonder chemicaliën.

Waar...
- **Keyword Score:** 0.80
- **LLM Score:** 4/5 - Het antwoord is relevant en behandelt de kernpunten: schapenwol tegen slakken, ruwe structuur die slakken afschrikt en bescherming zonder chemicaliën. Het is wel wat promotioneel en mist praktische details (hoe toepassen, effectiviteit/voorwaarden), waardoor het net geen 5 is.
- **Hallucination Check:** ✓ Pass
- **Latency:** 1.98s

**6. ✓ PASS** - Wat zijn hydrokorrels en waarvoor gebruik je ze?

- **Answer:** Hydrokorrels zijn gebakken en gewassen korrels van zuivere klei. Ze nemen water op en geven dat daarna geleidelijk weer af, terwijl er ook lucht bij de wortels kan blijven. Dat helpt planten om gezond...
- **Keyword Score:** 0.83
- **LLM Score:** 5/5 - Het antwoord legt correct uit wat hydrokorrels zijn (gebakken kleikorrels) en benoemt duidelijk hun functies rond wateropname/-afgifte en drainage. Het geeft bovendien praktische toepassingen in potten/potgrond en raakt alle verwachte keywords.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.31s

**7. ✓ PASS** - Welke soorten potgrond hebben jullie?

- **Answer:** We hebben in elk geval deze soorten potgrond in ons assortiment:

- Biologische Universele Potgrond (breed inzetbaar voor tuin-, balkon-, terras- en kamerplanten)
- Universele potgrond (algemeen, voor...
- **Keyword Score:** 0.80
- **LLM Score:** 4/5 - Het antwoord noemt meerdere relevante soorten potgrond, inclusief biologische, universele en moestuinvarianten, en is behulpzaam met een vervolgvraag. Het mist echter de expliciete vermelding van RHP (verwacht keyword) en concrete product-/keurmerkdetails.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.72s

**8. ✓ PASS** - Wat is het verschil tussen Ecolat en Ekoboard?

- **Answer:** Het verschil zit vooral in flexibiliteit en waar je ’m het liefst voor gebruikt:

- Ecolat is stijver en vormvaster. Daardoor is ‘ie vooral handig voor strakke, rechte lijnen en bijvoorbeeld vijverran...
- **Keyword Score:** 0.25
- **LLM Score:** 4/5 - Het antwoord legt duidelijk de belangrijkste verschillen uit (stijfheid/buigzaamheid, toepassingen voor rechte lijnen vs bochten, bevestiging en beschikbare maten/kleuren) en is praktisch bruikbaar. Het noemt echter niet expliciet dat beide kunststof, duurzame borderranden zijn om te afbakenen, wat bij de verwachte keywords hoort.
- **Hallucination Check:** ✓ Pass
- **Latency:** 4.88s

**9. ✓ PASS** - Hoe lang gaat Franse boomschors mee?

- **Answer:** Franse boomschors gaat meestal lang mee: reken grofweg op zo’n 6–8 jaar, afhankelijk van de omstandigheden. Voor onze Premium Franse boomschors ligt dat gemiddeld rond de 5–7 jaar.

Waar wil je ’m voo...
- **Keyword Score:** 0.50
- **LLM Score:** 5/5 - Het antwoord geeft een duidelijke levensduurindicatie (6–8 jaar) en benoemt dat dit afhangt van omstandigheden, wat aansluit bij de verwachte keywords. De extra vraag over toepassing en laagdikte maakt het bovendien praktisch en behulpzaam.
- **Hallucination Check:** ✓ Pass
- **Latency:** 2.09s

**10. ✓ PASS** - Wat is de beste bodembedekking voor borders?

- **Answer:** Voor borders hangt “beste” vooral af van wat je belangrijk vindt (hoe lang het mee moet gaan, budget en uitstraling). In het algemeen:

- Als je zo min mogelijk onderhoud wilt en het lang mee moet gaa...
- **Keyword Score:** 0.60
- **LLM Score:** 4/5 - Het antwoord is relevant en noemt geschikte bodembedekkingen (boomschors/dennenschors/houtmulch) met duidelijke afwegingen rond onderhoud, levensduur en onkruidonderdrukking. Het mist wel expliciete vermelding van houtsnippers en wat extra praktische details (laagdikte, toepassing) om echt compleet te zijn.
- **Hallucination Check:** ✓ Pass
- **Latency:** 3.99s


## Recommendations


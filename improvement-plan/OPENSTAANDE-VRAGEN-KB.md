# Openstaande beleidsvragen voor de kennisbank

> **Status: alle 7 beantwoord en verwerkt in de kennisbank op 2026-07-29.**
> Wat waar terechtkwam:
> 1. Prijzen (A) → `prijzen_topproducten.txt` (stond al zo)
> 2. Bigbags → `FAQ GCG.txt`, nieuwe vraag "Hoeveel bigbags krijg ik bij mijn bestelling?"
> 3. Verzendkosten → `FAQ GCG.txt` (NL+BE+toeslagen bij elkaar) en `belgie_informatie.txt`
> 4. Bigbag-hergebruik → `FAQ GCG.txt`, met de 404-pagina expliciet benoemd
> 5. Certificaten → nieuw bestand `certificaten_en_keurmerken.txt` (doorverwijzen)
> 6. Uitgefaseerde producten → nieuw bestand `niet_leverbare_producten.txt` + fractie-fix
>    in `Boomschors.txt`
> 7. Telefonische bereikbaarheid → `openingstijden.txt`
>
> **Twee antwoorden heb ik aangescherpt omdat de KB het tegendeel bleek te bevatten:**
> - **Schapenwol.** Je zei "niet in het assortiment", maar `Bio Sheep Wool 1,6 m` staat in
>   de KB mét werkende productlink. Wat niet bestaat is de *rol*-variant die de bot in
>   `sess_njUAW` verzon ("0,8 m x 5 m"). Vastgelegd als: per meter bestaat, rol niet.
> - **Boomschors 40-60 / 45-80 mm.** Die worden al verkocht — er staat een werkende link
>   naar `franse-boomschors-45-80mm-in-big-bag`. Het probleem was de naamgeving: de KB
>   zei "Premium = 20-45 mm", waardoor de bot grovere fracties ontkende. Nu expliciet.
>
> **Eén ding om te controleren:** ik lees de Belgische regel als "normaal € 15, maar bij een
> orderbedrag onder € 50 wordt het € 21,95". Klopt die richting? Zo niet, zeg het — dan
> draai ik het om. Het stond in de oude KB als één moeilijk leesbare regel.
>
> **Los hiervan, geen KB-kwestie:** de tekst `boomschors.nl/hergebruik` staat op je bigbags
> maar geeft een 404. Dat kost klanten (één zei "volgende keer bestel ik elders"). Dat is
> iets voor de webshop of de verpakkingsdrukker, niet voor de bot.

---

Vul in achter **Antwoord:** — het mag kort en in steekwoorden, ik maak er de KB-tekst van.
Wat je niet weet of niet wilt vastleggen: schrijf "overslaan", dan laat ik de bot bij die
vraag doorverwijzen naar een collega in plaats van iets te verzinnen.

Hoort bij [CHATLOG-ANALYSE-2026-07-29.md](CHATLOG-ANALYSE-2026-07-29.md) §5. Elke vraag
komt uit echte gesprekken waarin de bot vastliep; de sessie-id's staan erbij.

---

## 1. Prijzen in de kennisbank — ja of nee?

Nu staat er niets, wat leidde tot ~40 nutteloze antwoorden. Ik heb er voorlopig
"prijzen staan in de webshop" van gemaakt. Twee opties:

- **A (mijn advies):** nooit prijzen noemen, altijd naar de webshop verwijzen. Eerlijk,
  onderhoudsvrij, kan niet verouderen.
- **B:** prijslijst aanleveren die ik in de KB zet — dan moet die wel bijgehouden worden,
  anders geeft de bot straks verouderde prijzen door.

**Antwoord:** A

## 2. Bigbags — hoeveel zakken bij welke hoeveelheid?

De bot gaf hier vier verschillende antwoorden (`sess_aQdGkR`, `sess_HcsUoG`,
`sess_1hfB8x`, `sess_e04P-E`). Wordt 2 m³ geleverd als één bigbag van 2 m³, of als
2 × 1 m³? Verschilt dat per product?

**Antwoord:** 2 m3 wordt geleverd in 1 bigbag

## 3. Verzendkosten

Drie verschillende antwoorden gegeven (`sess_wpyhmO`, `sess_-re9gB`, `sess_cEuoyj`,
`sess_LK06tJ`). Graag: tarief NL, tarief BE, drempel gratis verzending, en of dat
verschilt per pallet / bigbag / los pakket. 

De KB zegt nu: "kleine pakketten €6,95, vanaf €50 gratis" (FAQ) en voor België
"€15, onder de €50 is dit €21,95" (belgie_informatie.txt). Klopt dat nog, en geldt de
gratis-verzendingsdrempel ook voor pallets en bigbags? 

**Antwoord:** Ja dit klopt, er komen alleen 100 euro extra kosten bij zodra er een kooiaap geregeld moet worden bij een zending.

## 4. Bigbag-hergebruik

Op de bigbags staat `boomschors.nl/hergebruik`, maar de KB zegt "verpakkingen en
transportmateriaal worden niet retour genomen". Drie klanten liepen hierop vast
(`sess_epXnDes`, `sess_TDOgT58`, `sess_PL0j`); één zei "volgende keer bestel ik elders".

Wat is het beleid, en wat staat er op die pagina?

**Antwoord:** Die pagina bestaat niet, geeft code 404. transportmateriaal worden niet retour genomen.

## 5. Certificaten

`sess_Rmc` liep uit op een discussie over misleidende marketing rond "biologische
tuinaarde" zonder certificaat — dat is reputatierisico dat de bot niet moet voeren.
Per product/vraag: wat mogen we wél zeggen over SKAL/bio, PFAS, zware metalen en RHP?
En bij welke vragen moet de bot direct doorverwijzen zonder inhoudelijk antwoord?

**Antwoord:** Hier kan ik nu geen goed antwoord geven. Als zulke claims ter spraken komen lijkt het mij goed dat deze vraag door wordt gezet naar een menselijke collega.

## 6. Uitgefaseerde producten

Klanten vragen expliciet naar deze, en de bot kent ze niet:

- Douglas Excellent houtsnippers, artikel HSDE-2 (`sess_H4Ot9`, `sess_9lIjUY`, `sess_x6Nu71`)
- wilgen houtsnippers (`sess_4nnfvc`, `sess_POEVHG`)
- schapenwol op rol (`sess_njUAW`)
- boomschors fractie 40-60 mm (`sess_ItDKZ`, `sess_6e1RkfE`) en 45-80 mm (`sess_by1TX`)

Per product: uit assortiment, tijdelijk uitverkocht, of vervangen door — en zo ja, door wat?

**Antwoord:** 
- Douglas Excellent houtsnippers, artikel HSDE-2: uit assortiment
- wilgen houtsnippers: bestaat niet in het assortiment
- schapenwol op rol: Niet in het assortiment
- boomschors fractie 40-60 mm en 45-80 mm: Deze verkopen wij onder de naam Franse Boomschors Premium


## 7. Telefonische bereikbaarheid

Stond als `[TIJDEN INVULLEN]` in `openingstijden.txt`; die regel heb ik verwijderd.
Zijn de telefonische tijden gelijk aan de openingstijden (ma-vr 09:00-17:00), of anders?

**Antwoord:** Ja, die zijn gelijk aan de openingstijden 

/**
 * Chat Log Portal - localStorage Data Layer
 *
 * localStorage Key Schema:
 * ─────────────────────────────────────────────────────────────────
 * portal_version       - string  - Schema version for migrations ("1.0")
 * portal_auth          - object  - Current auth state
 * portal_conversations - array   - All conversation objects with messages
 * portal_labels_meta   - array   - Available label definitions
 * portal_settings      - object  - Portal user preferences
 * ─────────────────────────────────────────────────────────────────
 *
 * Size budget (localStorage ~5-10 MB):
 *   ~25 conversations x ~10 messages x ~500 bytes = ~125 KB
 *   Labels/notes metadata: ~5 KB
 *   Auth + settings: ~1 KB
 *   Total seed footprint: ~130 KB (well within limits)
 *   At scale: ~2000 conversations before approaching 5 MB
 */

/* ================================================================
   SECTION 1 - DATA STRUCTURES / SCHEMAS
   ================================================================

   portal_auth:
   {
     "authenticated": boolean,
     "user": {
       "username": string,
       "role": "admin" | "viewer" | "trainer"
     },
     "loginTime": ISO string | null
   }

   portal_conversations[]:
   {
     "id": string (uuid-like, e.g. "conv_a1b2c3d4"),
     "sessionId": string (matches log filename pattern),
     "startedAt": ISO string,
     "endedAt": ISO string,
     "language": "nl" | "en",
     "messageCount": number,
     "status": "resolved" | "escalated" | "unknown_flagged" | "open",
     "labels": string[],          // conversation-level labels
     "rating": number | null,     // 1-5 overall quality rating
     "notes": [                   // internal notes
       { "id": string, "text": string, "author": string, "createdAt": ISO }
     ],
     "messages": [
       {
         "id": string (e.g. "msg_0"),
         "timestamp": ISO string,
         "requestId": string | null (8-char from logs),
         "role": "user" | "bot",
         "content": string,
         "labels": string[],       // message-level labels
         "rating": number | null   // per-message quality 1-5
       }
     ]
   }

   portal_labels_meta[]:
   {
     "name": string,
     "color": string (hex),
     "description": string
   }

   portal_settings:
   {
     "theme": "light" | "dark",
     "pageSize": number,
     "defaultLanguageFilter": "all" | "nl" | "en"
   }

   ================================================================ */


// ================================================================
// SECTION 2 - SEED DATA GENERATOR
// ================================================================

function generateSeedData() {
  // Helper to generate IDs
  const uid = () => Math.random().toString(36).substring(2, 10);
  const convId = () => 'conv_' + uid();
  const reqId = () => uid().substring(0, 8);

  // Date helpers - seed data spans 2 weeks ending yesterday
  const now = new Date();
  const twoWeeksAgo = new Date(now);
  twoWeeksAgo.setDate(twoWeeksAgo.getDate() - 14);

  function randomDate(start, end) {
    return new Date(start.getTime() + Math.random() * (end.getTime() - start.getTime()));
  }

  function addMinutes(date, min) {
    return new Date(date.getTime() + min * 60000);
  }

  // Predefined conversation templates for realism
  // Each template: { language, messages: [{role, content}], status, labels? }
  const templates = [
    // --- DUTCH CONVERSATIONS ---
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Hallo, ik heb een vraag over boomschors.' },
        { role: 'bot', content: 'Hallo! Leuk dat je contact opneemt. Waarmee kan ik je helpen wat betreft boomschors?' },
        { role: 'user', content: 'Hoeveel zakken heb ik nodig voor 20 vierkante meter?' },
        { role: 'bot', content: 'Voor 20 vierkante meter met een laagdikte van ongeveer 5 cm heb je zo\'n 40 zakken van 70 liter nodig. Wil je de Franse boomschors of de dennenschors? De Franse variant is grover en gaat langer mee, terwijl dennenschors fijner en wat voordeliger is.' },
        { role: 'user', content: 'De Franse boomschors graag. Wat kost dat?' },
        { role: 'bot', content: 'De Franse boomschors is een populaire keuze! Voor de exacte prijs en om te bestellen verwijs ik je graag naar onze webshop. Daar zie je ook meteen of er een actie op loopt. Kan ik je nog ergens anders mee helpen?' },
        { role: 'user', content: 'Nee, dank je wel!' },
        { role: 'bot', content: 'Graag gedaan! Veel plezier met je tuin. Als je nog vragen hebt, weet je ons te vinden.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Wanneer wordt mijn bestelling geleverd?' },
        { role: 'bot', content: 'De levertijd is voor de meeste producten in Nederland 1 tot 3 werkdagen. Als je naar Belgie hebt besteld of zandproducten hebt gekozen, kan het 1 tot 5 werkdagen duren. Heb je je bevestigingsmail met track & trace al ontvangen?' },
        { role: 'user', content: 'Ik heb niks ontvangen' },
        { role: 'bot', content: 'Dat is vervelend. Check even je spam- of junkmap, want bevestigingen komen daar soms terecht. Als je het daar ook niet kunt vinden, neem dan contact op met onze klantenservice zodat we het voor je kunnen nakijken.' },
        { role: 'user', content: 'Oh ja, gevonden in mijn spam! Bedankt.' },
        { role: 'bot', content: 'Mooi, fijn dat het gelukt is! Dat gebeurt vaker. Succes met je bestelling.' }
      ]
    },
    {
      language: 'nl',
      status: 'escalated',
      messages: [
        { role: 'user', content: 'Ik wil mijn bestelling retourneren.' },
        { role: 'bot', content: 'Dat is jammer om te horen. Je kunt je bestelling retourneren, maar de retourkosten zijn voor eigen rekening. Mag ik vragen wat de reden is?' },
        { role: 'user', content: 'Ik heb de verkeerde aarde besteld. Het moest biologische potgrond zijn maar ik heb tuinaarde gekregen.' },
        { role: 'bot', content: 'Ah, dat is vervelend! Biologische potgrond en tuinaarde zijn inderdaad heel verschillende producten. Voor het retourneren wordt het in overleg ingepland. Wil je dat ik je in contact breng met een collega die dit voor je kan regelen?' },
        { role: 'user', content: 'Ja graag, mag ik een medewerker spreken?' },
        { role: 'bot', content: 'Natuurlijk! Ik breng je graag in contact met een collega. Wat is je naam?' },
        { role: 'user', content: 'Pieter de Vries' },
        { role: 'bot', content: 'Leuk je te ontmoeten, Pieter de Vries! Wat is je e-mailadres?' },
        { role: 'user', content: 'pieter@example.com' },
        { role: 'bot', content: 'Top! Ik heb je bericht doorgestuurd naar een collega. We nemen zo snel mogelijk contact met je op via e-mail.' }
      ]
    },
    {
      language: 'nl',
      status: 'unknown_flagged',
      messages: [
        { role: 'user', content: 'Hebben jullie PFAS-vrije tuinaarde?' },
        { role: 'bot', content: 'Goede vraag. Helaas kunnen we geen verklaring afgeven dat bemeste tuinaarde volledig PFAS-vrij is, omdat het product compost bevat waarin PFAS-contaminatie niet volledig kan worden uitgesloten. Als je je zorgen maakt over PFAS, kan ik je meer vertellen over onze onbemeste tuinaarde.' },
        { role: 'user', content: 'Is de onbemeste tuinaarde dan wel PFAS-vrij?' },
        { role: 'bot', content: 'Hmm, daar heb ik helaas geen specifieke informatie over. Ik weet wel dat onze onbemeste tuinaarde geen compost bevat, wat de belangrijkste bron van mogelijke PFAS-verontreiniging is. Voor een definitief antwoord raad ik je aan contact op te nemen met onze klantenservice.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Kan ik mijn bestelling afhalen?' },
        { role: 'bot', content: 'Ja, voor een aantal producten is afhalen mogelijk! Het gaat wel alleen op afspraak en niet in het weekend. De bestelling en betaling verlopen altijd via de webshop. Heb je al iets besteld of wil je eerst meer weten?' },
        { role: 'user', content: 'Ik wil 10 zakken potgrond bestellen en morgen ophalen.' },
        { role: 'bot', content: 'Je kunt de bestelling plaatsen via onze webshop. Als je in het opmerkingenveld aangeeft dat je wilt afhalen en op welke dag, wordt het voor je klaargezet. Let wel op dat je eerst via de webshop betaalt, want contant betalen bij afhalen is helaas niet mogelijk.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Wat is het verschil tussen potgrond en tuinaarde?' },
        { role: 'bot', content: 'Goeie vraag! Potgrond is speciaal samengesteld voor gebruik in potten en bakken. Het is licht, luchtig en houdt goed vocht vast. Tuinaarde gebruik je juist om de bodem van je tuin te verbeteren of aan te vullen. Het is steviger en bevat meer voedingsstoffen voor de volle grond. Waarvoor wil je het gebruiken?' },
        { role: 'user', content: 'Voor mijn moestuin in bakken op het balkon.' },
        { role: 'bot', content: 'Dan is potgrond de beste keuze! Wij hebben een Biologische Moestuinpotgrond die perfect is voor groenten en kruiden in bakken. Die bevat al voeding voor de eerste weken. Wil je daar meer over weten?' },
        { role: 'user', content: 'Ja, is die ook geschikt voor tomaten?' },
        { role: 'bot', content: 'Absoluut, de Biologische Moestuinpotgrond is heel geschikt voor tomaten. Tomaten zijn wel flinke eters, dus na een paar weken is het slim om bij te bemesten. Maar voor de start zit je met deze potgrond helemaal goed.' }
      ]
    },
    {
      language: 'nl',
      status: 'open',
      messages: [
        { role: 'user', content: 'hoe bak ik pannenkoeken?' },
        { role: 'bot', content: 'Ik beantwoord alleen vragen over onze producten en diensten. Kan ik je helpen met iets over tuinieren, potgrond, of bodembedekking?' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Leveren jullie ook in Belgie?' },
        { role: 'bot', content: 'Ja, we leveren ook in Belgie! De levertijd is daar 1 tot 5 werkdagen. De levering verloopt op dezelfde manier met een vrachtwagen en palletwagen. Heb je al iets op het oog?' },
        { role: 'user', content: 'Ja, ik wil houtsnippers bestellen voor mijn paden.' },
        { role: 'bot', content: 'Mooie keuze voor paden! Onze houtsnippers zijn daar heel geschikt voor. Ze houden onkruid tegen en geven een natuurlijke uitstraling. Je kunt ze zo bestellen in onze webshop. Hoeveel vierkante meter moet je bedekken?' },
        { role: 'user', content: 'Ongeveer 15 m2.' },
        { role: 'bot', content: 'Voor 15 vierkante meter met een goede laagdikte van zo\'n 5 tot 7 centimeter heb je een aardige hoeveelheid nodig. Ik raad je aan om in de webshop de calculator te gebruiken die precies uitrekent hoeveel zakken je nodig hebt. Dan weet je zeker dat je genoeg bestelt.' }
      ]
    },
    {
      language: 'nl',
      status: 'unknown_flagged',
      messages: [
        { role: 'user', content: 'Is de biologische potgrond SKAL-gecertificeerd?' },
        { role: 'bot', content: 'Nee, onze biologische potgrond is niet SKAL-gecertificeerd. Dat certificaat is alleen nodig als je potgrond verkoopt als "biologisch" voor gebruik in de professionele biologische land- of tuinbouw. Voor gebruik in je eigen tuin is dit niet verplicht en de potgrond is wel degelijk biologisch samengesteld.' },
        { role: 'user', content: 'Maar ik heb het nodig voor mijn professionele biologische kwekerij. Hebben jullie een alternatief?' },
        { role: 'bot', content: 'Hmm, voor professioneel biologisch gebruik met SKAL-certificering heb ik helaas geen specifiek aanbod in onze documentatie. Ik raad je aan om contact op te nemen met onze klantenservice, die kunnen je waarschijnlijk beter adviseren over professionele oplossingen.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Hallo' },
        { role: 'bot', content: 'Hallo! Hoe kan ik je helpen met vragen over onze producten en diensten?' },
        { role: 'user', content: 'Ik zoek iets om onkruid tegen te gaan in mijn border.' },
        { role: 'bot', content: 'Er zijn een paar goede opties om onkruid te bestrijden in je border. Ons anti-worteldoek is heel effectief: je legt het op de grond en bedekt het met boomschors of houtsnippers. Het doek laat water door maar houdt onkruid tegen. Wil je daar meer over weten?' },
        { role: 'user', content: 'Ja, hoe bevestig ik dat doek?' },
        { role: 'bot', content: 'Je bevestigt het anti-worteldoek met onze gronddoekpennen. Die druk je simpelweg door het doek in de grond. Zo blijft het mooi op zijn plek liggen, ook als je er boomschors of snippers overheen doet. Handig en makkelijk te doen!' },
        { role: 'user', content: 'Top, bedankt voor de info!' },
        { role: 'bot', content: 'Graag gedaan! Veel succes met je border. Als je nog vragen hebt, stel ze gerust.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Wat is het verschil tussen Ecolat en Ekoboard borderrand?' },
        { role: 'bot', content: 'Goeie vraag! Beide zijn prima borderranden, maar ze verschillen qua materiaal en flexibiliteit. Ecolat is gemaakt van gerecycled kunststof en is behoorlijk flexibel, ideaal voor ronde vormen. Ekoboard is iets steviger en strakker, perfect voor rechte lijnen. Wat voor vorm heeft je border?' },
        { role: 'user', content: 'Ronde vormen, dus Ecolat lijkt de beste keuze.' },
        { role: 'bot', content: 'Precies, voor ronde en organische vormen is Ecolat ideaal! Je kunt het makkelijk buigen en het blijft mooi op zijn plek met onze Ecopic paaltjes. Die sla je er gewoon naast in de grond. Wil je nog meer weten over de montage?' },
        { role: 'user', content: 'Nee, ik ga het bestellen. Bedankt!' },
        { role: 'bot', content: 'Super! Veel plezier met het aanleggen. En als je toch nog vragen hebt, zijn we er altijd.' }
      ]
    },
    {
      language: 'nl',
      status: 'escalated',
      messages: [
        { role: 'user', content: 'Mijn bestelling is beschadigd aangekomen.' },
        { role: 'bot', content: 'Dat is heel vervelend om te horen! Mijn excuses voor het ongemak. Kun je me vertellen wat er precies beschadigd is?' },
        { role: 'user', content: 'Twee zakken boomschors zijn gescheurd en de inhoud lag los op de pallet.' },
        { role: 'bot', content: 'Dat is niet zoals het hoort. Ik begrijp dat dat frustrerend is. Dit soort gevallen wordt het best opgepakt door onze klantenservice zodat ze een oplossing voor je kunnen regelen. Wil je dat ik je doorverbind met een collega?' },
        { role: 'user', content: 'Ja, laat maar komen.' },
        { role: 'bot', content: 'Natuurlijk! Ik breng je graag in contact met een collega. Wat is je naam?' },
        { role: 'user', content: 'Maria Jansen' },
        { role: 'bot', content: 'Leuk je te ontmoeten, Maria Jansen! Wat is je e-mailadres?' },
        { role: 'user', content: 'maria.jansen@gmail.com' },
        { role: 'bot', content: 'Top! Ik heb je bericht doorgestuurd naar een collega. We nemen zo snel mogelijk contact met je op via e-mail.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Kan een pallet over mijn hek getild worden?' },
        { role: 'bot', content: 'Helaas is dat niet mogelijk. De levering gebeurt met een palletwagen, niet met een kraan, dus pallets kunnen niet over hekken, heggen of muren getild worden. De chauffeur plaatst de pallet op de dichtstbijzijnde bereikbare plek. Kun je misschien het hek open zetten voor de levering?' },
        { role: 'user', content: 'Ja, dat is wel te regelen. Bedankt!' },
        { role: 'bot', content: 'Perfect, dan komt het goed! Zorg dat de toegangsweg vrij is voor de vrachtwagen. Succes met de levering.' }
      ]
    },
    {
      language: 'nl',
      status: 'unknown_flagged',
      messages: [
        { role: 'user', content: 'Hoeveel kost verzending naar Duitsland?' },
        { role: 'bot', content: 'Hmm, daar heb ik helaas geen specifieke informatie over in mijn documentatie. Ik weet dat we leveren in Nederland en Belgie, maar voor verzending naar Duitsland raad ik je aan om contact op te nemen met onze klantenservice. Die kunnen je precies vertellen of het mogelijk is en wat de kosten zijn.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Wat zijn hydrokorrels en waar gebruik ik ze voor?' },
        { role: 'bot', content: 'Hydrokorrels zijn lichte, ronde kleikorrels die gebakken zijn bij hoge temperatuur. Ze zijn super veelzijdig! Je kunt ze gebruiken als drainage laag onder in potten, als bodembedekker in de tuin, of zelfs voor hydrocultuur. Ze zorgen voor goede luchtigheid en voorkomen wateroverlast bij wortels.' },
        { role: 'user', content: 'Kan ik ze ook mengen met potgrond?' },
        { role: 'bot', content: 'Zeker! Door hydrokorrels te mengen met potgrond maak je de grond lichtiger en verbeter je de drainage. Vooral handig voor planten die niet van natte voeten houden, zoals vetplanten of kruiden. Een mengverhouding van zo\'n 20-30% hydrokorrels werkt goed.' }
      ]
    },

    // --- ENGLISH CONVERSATIONS ---
    {
      language: 'en',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Hi, do you deliver to Belgium?' },
        { role: 'bot', content: 'Hello! Yes, we do deliver to Belgium. The delivery time is typically 1 to 5 business days. Delivery is done by truck with a pallet jack. What are you looking to order?' },
        { role: 'user', content: 'I need bark mulch for my garden, about 30 square meters.' },
        { role: 'bot', content: 'Great choice for your garden! For 30 square meters with a proper layer thickness of about 5 cm, you\'ll need quite a few bags. I\'d recommend checking our web shop where there\'s a calculator that can give you the exact amount. We have both French bark mulch, which is coarser and lasts longer, and pine bark which is finer. Which would you prefer?' },
        { role: 'user', content: 'The French bark sounds better. Thanks for the help!' },
        { role: 'bot', content: 'You\'re welcome! French bark mulch is indeed a great long-lasting option. Head over to our web shop to place your order. If you have any more questions, don\'t hesitate to ask!' }
      ]
    },
    {
      language: 'en',
      status: 'escalated',
      messages: [
        { role: 'user', content: 'I want to speak with a real person please.' },
        { role: 'bot', content: 'Of course! I\'d be happy to connect you with a colleague. What\'s your name?' },
        { role: 'user', content: 'John Smith' },
        { role: 'bot', content: 'Nice to meet you, John Smith! What\'s your email address?' },
        { role: 'user', content: 'john.smith@example.com' },
        { role: 'bot', content: 'Great! I\'ve forwarded your message to a colleague. We\'ll get in touch via email as soon as possible.' }
      ]
    },
    {
      language: 'en',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'What\'s the difference between potting soil and garden soil?' },
        { role: 'bot', content: 'Good question! Potting soil is specially formulated for use in pots and containers. It\'s light, airy, and retains moisture well. Garden soil, on the other hand, is used to improve or supplement your garden\'s ground soil. It\'s heavier and enriched with nutrients for outdoor beds. What do you plan to use it for?' },
        { role: 'user', content: 'I want to plant vegetables in raised beds.' },
        { role: 'bot', content: 'For raised beds, our Organic Vegetable Garden Potting Soil would be perfect! It\'s already enriched with nutrients to give your vegetables a great start. Since raised beds are essentially large containers, potting soil works better than garden soil here. Would you like to know more about it?' },
        { role: 'user', content: 'No that\'s all I needed, thanks!' },
        { role: 'bot', content: 'Happy to help! Good luck with your raised bed garden. Feel free to reach out if you have more questions.' }
      ]
    },
    {
      language: 'en',
      status: 'unknown_flagged',
      messages: [
        { role: 'user', content: 'Do you have any discount codes?' },
        { role: 'bot', content: 'We don\'t offer discount codes. All our products are already competitively priced, and some may be part of ongoing promotions. You can check our web shop for the latest prices and any current offers. Is there anything specific you\'re looking for?' },
        { role: 'user', content: 'What about bulk discounts for 5 pallets?' },
        { role: 'bot', content: 'I understand you\'re looking for a bulk deal. Unfortunately, we don\'t offer volume discounts or tiered pricing, as all our products are already priced competitively. The price you see in the shop is the best price available. Can I help you with anything else?' },
        { role: 'user', content: 'What about trade accounts for landscaping companies?' },
        { role: 'bot', content: 'Hmm, I don\'t have specific information about trade accounts for professionals in my documentation. For business inquiries like this, I\'d recommend contacting our customer service directly. They can discuss options for professional landscaping clients.' }
      ]
    },
    {
      language: 'en',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Can I pick up my order instead of having it delivered?' },
        { role: 'bot', content: 'Yes, pickup is available for a number of products! You\'ll need to make an appointment first though, and it\'s only possible on weekdays. The order and payment still go through the web shop. Would you like to go ahead and order for pickup?' },
        { role: 'user', content: 'Yes, can I pay cash when I pick up?' },
        { role: 'bot', content: 'Unfortunately, cash payment isn\'t possible. All payments need to go through the web shop, even for pickups. But it\'s easy and quick to pay online. Once you place your order, just mention in the comments that you\'d like to pick up, and we\'ll arrange it for you.' }
      ]
    },
    {
      language: 'en',
      status: 'open',
      messages: [
        { role: 'user', content: 'Hello!' },
        { role: 'bot', content: 'Hello! How can I help you with questions about our products and services?' }
      ]
    },
    {
      language: 'en',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'I\'m looking for ground cover to prevent weeds in my flower beds.' },
        { role: 'bot', content: 'We have some great options for that! Our anti-root cloth is very effective at blocking weeds while still allowing water to pass through. You lay it on the ground and cover it with bark mulch or wood chips for a nice natural look. Would you like to know more about it?' },
        { role: 'user', content: 'Yes, how do I secure the cloth to the ground?' },
        { role: 'bot', content: 'You can secure it with our ground cloth pins. You simply push them through the cloth into the soil, and they hold everything in place. They\'re really easy to use. Then you cover the cloth with bark or wood chips, and you\'re all set!' },
        { role: 'user', content: 'And which border edging would work to keep the bark in place?' },
        { role: 'bot', content: 'Great thinking! Our Ecolat border edging is perfect for that. It\'s made from recycled plastic, so it\'s durable and flexible enough for curved borders. For straight edges, Ekoboard is a nice alternative. Both are easy to install with our Ecopic stakes. What shape are your flower beds?' },
        { role: 'user', content: 'Mix of straight and curved. I think I\'ll get both.' },
        { role: 'bot', content: 'Smart choice! That way you have the best of both worlds. You can find all these products in our web shop. If you need help calculating quantities, just let me know!' }
      ]
    },
    {
      language: 'en',
      status: 'unknown_flagged',
      messages: [
        { role: 'user', content: 'Is the Bio Sheep Wool ground cover safe for my dog?' },
        { role: 'bot', content: 'I don\'t have specific information about pet safety for the Bio Sheep Wool ground cover in my documentation. For safety-related questions like this, I\'d recommend reaching out to our customer service team directly, as they can provide the most accurate guidance.' },
        { role: 'user', content: 'Ok, can you at least tell me what it\'s made of?' },
        { role: 'bot', content: 'The Bio Sheep Wool is a natural ground cover product made from sheep wool. It\'s biodegradable and works as a weed suppressant while also adding nutrients to the soil as it breaks down. It comes in rolls of 1.6 meters wide. But for the specific pet safety question, I\'d still recommend checking with our team.' }
      ]
    },
    {
      language: 'en',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'What kind of firewood do you sell?' },
        { role: 'bot', content: 'We offer oak firewood, which is known for being one of the best choices for heating. Oak burns slowly and produces a lot of heat, making it very efficient. We also have fire starters: kindling wood in net bags and wood wool curls for easy lighting. Are you looking to stock up for the winter?' },
        { role: 'user', content: 'Yes, how much oak firewood would I need for a season?' },
        { role: 'bot', content: 'That depends on how often you use your fireplace and the size of your space. As a rough guide, most people go through about 2-3 pallets per season for regular evening use. I\'d recommend starting with one pallet and seeing how quickly you go through it. You can always order more!' }
      ]
    },
    {
      language: 'en',
      status: 'escalated',
      messages: [
        { role: 'user', content: 'My delivery was left in the wrong place and some bags got wet in the rain.' },
        { role: 'bot', content: 'I\'m really sorry to hear that! That must be frustrating. Sometimes the driver can\'t reach the exact spot requested, but your products shouldn\'t have been left exposed to the elements. This is something our customer service team can help resolve for you. Would you like me to connect you with a colleague?' },
        { role: 'user', content: 'Yes please, this is unacceptable.' },
        { role: 'bot', content: 'I completely understand your frustration. Let me connect you with a colleague right away. What\'s your name?' },
        { role: 'user', content: 'Sarah Thompson' },
        { role: 'bot', content: 'Nice to meet you, Sarah Thompson! What\'s your email address?' },
        { role: 'user', content: 'sarah.t@example.com' },
        { role: 'bot', content: 'Great! I\'ve forwarded your message to a colleague. We\'ll get in touch via email as soon as possible.' }
      ]
    },
    {
      language: 'nl',
      status: 'resolved',
      messages: [
        { role: 'user', content: 'Kunnen jullie leveren op mijn volkstuin?' },
        { role: 'bot', content: 'Ja, levering op een volkstuincomplex is mogelijk, mits er een officieel adres is en het terrein toegankelijk is voor onze vrachtwagen. Als er geen officieel adres is, kun je het dichtstbijzijnde adres gebruiken. Coordinaten of Google Maps-links worden helaas niet geaccepteerd. Heb je een adres beschikbaar?' },
        { role: 'user', content: 'Ja, het complex heeft een officieel adres.' },
        { role: 'bot', content: 'Dan is het geen probleem! Vermeld bij het bestellen even in het opmerkingenveld dat het om een volkstuincomplex gaat, en eventueel het tuinnummer. Dan weet de chauffeur precies waar het heen moet.' }
      ]
    }
  ];

  // Generate the 25+ conversations from templates
  const conversations = [];

  // Pre-defined labels for some conversations
  const sampleLabels = [
    ['product-info'],
    ['delivery'],
    ['returns', 'urgent'],
    ['safety', 'pfas'],
    ['pickup'],
    ['product-info', 'potgrond'],
    ['off-topic'],
    ['delivery', 'belgium'],
    ['professional', 'skal'],
    ['product-info', 'weed-control'],
    ['borderrand', 'product-info'],
    ['complaint', 'damage'],
    ['delivery'],
    ['delivery', 'international'],
    ['product-info'],
    ['delivery', 'belgium'],
    ['escalation'],
    ['product-info'],
    ['product-info'],
    ['pickup', 'payment'],
    [],
    ['product-info', 'weed-control'],
    ['safety', 'pets'],
    ['product-info', 'firewood'],
    ['complaint', 'delivery'],
    ['delivery', 'volkstuin']
  ];

  // Pre-assigned ratings for some conversations
  const sampleRatings = [5, 4, 3, null, 5, 5, 2, 4, null, 5, 4, 3, 5, null, 4, 5, null, 4, 5, 4, null, 5, null, 4, 2, 5];

  // Sample notes for a few conversations
  const sampleNotes = {
    2: [{ text: 'Retour afgehandeld via klantenservice. Klant tevreden met oplossing.', author: 'admin' }],
    3: [{ text: 'PFAS-vraag steeds vaker. KB-document updaten met duidelijker antwoord.', author: 'trainer' }],
    8: [{ text: 'Professionele klant. Mogelijk interessant voor B2B follow-up.', author: 'admin' }],
    11: [{ text: 'Beschadigde levering gemeld. Foto opgevraagd. Vervanging gestuurd.', author: 'admin' }],
    13: [{ text: 'Duitsland-vraag. Uitzoeken of we hier iets mee willen.', author: 'trainer' }],
    18: [{ text: 'Trade account question flagged for business development.', author: 'admin' }],
    24: [{ text: 'Delivery complaint escalated. Customer received replacement.', author: 'admin' }]
  };

  for (let i = 0; i < templates.length; i++) {
    const tpl = templates[i];
    const startDate = randomDate(twoWeeksAgo, now);
    const id = convId();

    // Build messages array with proper structure
    const messages = [];
    let lastTime = startDate;

    for (let j = 0; j < tpl.messages.length; j++) {
      const msg = tpl.messages[j];
      // User messages come ~1-3 min after bot, bot responds ~5-30 sec later
      if (msg.role === 'user' && j > 0) {
        lastTime = addMinutes(lastTime, 1 + Math.random() * 2);
      } else if (msg.role === 'bot') {
        lastTime = addMinutes(lastTime, 0.1 + Math.random() * 0.4);
      }

      messages.push({
        id: `msg_${j}`,
        timestamp: lastTime.toISOString(),
        requestId: msg.role === 'bot' ? reqId() : null,
        role: msg.role,
        content: msg.content,
        labels: [],
        rating: null
      });
    }

    // Add message-level labels to a few specific messages
    // Mark __UNKNOWN__-style messages
    if (tpl.status === 'unknown_flagged') {
      const lastBotMsg = messages.filter(m => m.role === 'bot').pop();
      if (lastBotMsg) {
        lastBotMsg.labels = ['needs-review'];
      }
    }

    // Build notes
    const notes = [];
    if (sampleNotes[i]) {
      for (const n of sampleNotes[i]) {
        notes.push({
          id: 'note_' + uid(),
          text: n.text,
          author: n.author,
          createdAt: addMinutes(lastTime, 60 + Math.random() * 1440).toISOString()
        });
      }
    }

    conversations.push({
      id: id,
      sessionId: `sess_${Date.now() - Math.floor(Math.random() * 1e9)}_${uid()}`,
      startedAt: startDate.toISOString(),
      endedAt: lastTime.toISOString(),
      language: tpl.language,
      messageCount: messages.length,
      status: tpl.status,
      labels: sampleLabels[i] || [],
      rating: sampleRatings[i] !== undefined ? sampleRatings[i] : null,
      notes: notes,
      messages: messages
    });
  }

  // Sort by date descending (newest first)
  conversations.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

  return conversations;
}


// ================================================================
// SECTION 3 - DEFAULT LABEL DEFINITIONS
// ================================================================

function getDefaultLabels() {
  return [
    { name: 'product-info', color: '#3B82F6', description: 'Product information request' },
    { name: 'delivery', color: '#10B981', description: 'Delivery related question' },
    { name: 'returns', color: '#F59E0B', description: 'Return or refund request' },
    { name: 'complaint', color: '#EF4444', description: 'Customer complaint' },
    { name: 'escalation', color: '#DC2626', description: 'Escalated to human agent' },
    { name: 'urgent', color: '#B91C1C', description: 'Requires urgent attention' },
    { name: 'needs-review', color: '#8B5CF6', description: 'Flagged for quality review' },
    { name: 'off-topic', color: '#6B7280', description: 'Off-topic question' },
    { name: 'safety', color: '#F97316', description: 'Safety/PFAS/health related' },
    { name: 'pickup', color: '#06B6D4', description: 'In-store pickup inquiry' },
    { name: 'payment', color: '#14B8A6', description: 'Payment related' },
    { name: 'potgrond', color: '#84CC16', description: 'Potting soil products' },
    { name: 'borderrand', color: '#A855F7', description: 'Border edging products' },
    { name: 'firewood', color: '#D97706', description: 'Firewood products' },
    { name: 'belgium', color: '#EC4899', description: 'Belgium delivery' },
    { name: 'international', color: '#F43F5E', description: 'International shipping question' },
    { name: 'professional', color: '#0EA5E9', description: 'Professional/B2B customer' },
    { name: 'pfas', color: '#F97316', description: 'PFAS related question' },
    { name: 'skal', color: '#22C55E', description: 'SKAL certification question' },
    { name: 'pets', color: '#A78BFA', description: 'Pet safety question' },
    { name: 'damage', color: '#EF4444', description: 'Damaged goods report' },
    { name: 'weed-control', color: '#65A30D', description: 'Weed control products' },
    { name: 'volkstuin', color: '#059669', description: 'Allotment garden delivery' },
    { name: 'training-candidate', color: '#7C3AED', description: 'Good for RAG training data' }
  ];
}


// ================================================================
// SECTION 4 - STORAGE MANAGER CLASS
// ================================================================

const STORAGE_VERSION = '1.0';
const KEYS = {
  VERSION: 'portal_version',
  AUTH: 'portal_auth',
  CONVERSATIONS: 'portal_conversations',
  LABELS: 'portal_labels_meta',
  SETTINGS: 'portal_settings'
};

class StorageManager {
  constructor() {
    this._init();
  }

  // ── Initialization & Migration ─────────────────────────────────

  _init() {
    const version = localStorage.getItem(KEYS.VERSION);

    if (!version) {
      // First run - seed everything
      this._seedAll();
    } else if (version !== STORAGE_VERSION) {
      // Future: run migrations here
      this._migrate(version);
    }
  }

  _seedAll() {
    // Start with empty conversations — real data comes from API sync
    this._write(KEYS.CONVERSATIONS, []);
    this._write(KEYS.LABELS, getDefaultLabels());
    this._write(KEYS.SETTINGS, {
      theme: 'light',
      pageSize: 20,
      defaultLanguageFilter: 'all'
    });
    this._write(KEYS.AUTH, {
      authenticated: false,
      user: null,
      loginTime: null,
      apiKey: null
    });
    localStorage.setItem(KEYS.VERSION, STORAGE_VERSION);
  }

  _migrate(fromVersion) {
    // Placeholder for future schema migrations
    // Example: if (fromVersion === '1.0') { ... migrate to 1.1 ... }
    localStorage.setItem(KEYS.VERSION, STORAGE_VERSION);
  }

  // ── Low-level read/write with error handling ───────────────────

  _read(key) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      console.error(`StorageManager: failed to read ${key}`, e);
      return null;
    }
  }

  _write(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify(data));
      return true;
    } catch (e) {
      if (e.name === 'QuotaExceededError' || e.code === 22) {
        console.error('StorageManager: localStorage quota exceeded');
        return false;
      }
      console.error(`StorageManager: failed to write ${key}`, e);
      return false;
    }
  }

  // ── Auth ───────────────────────────────────────────────────────

  getAuth() {
    return this._read(KEYS.AUTH) || { authenticated: false, user: null, loginTime: null, apiKey: null };
  }

  setAuth(user, apiKey) {
    return this._write(KEYS.AUTH, {
      authenticated: true,
      user: { username: user.username, role: user.role || 'viewer' },
      loginTime: new Date().toISOString(),
      apiKey: apiKey || null
    });
  }

  clearAuth() {
    return this._write(KEYS.AUTH, { authenticated: false, user: null, loginTime: null, apiKey: null });
  }

  // ── API Sync ────────────────────────────────────────────────────

  /**
   * Validate an admin API key against the backend.
   * @param {string} apiKey
   * @returns {Promise<boolean>}
   */
  async validateApiKey(apiKey) {
    try {
      const resp = await fetch('/admin/api/conversations', {
        method: 'GET',
        headers: { 'X-Admin-Key': apiKey }
      });
      return resp.ok;
    } catch (e) {
      console.error('StorageManager: API key validation failed', e);
      return false;
    }
  }

  /**
   * Detect language from message content (simple heuristic).
   * @param {string} text
   * @returns {string} 'nl' or 'en'
   */
  _detectLanguage(text) {
    const nlWords = ['hallo', 'bedankt', 'bestelling', 'levering', 'graag', 'vraag', 'welkom', 'producten', 'tuin', 'kunt', 'helpen', 'goed', 'onze', 'webshop'];
    const lower = text.toLowerCase();
    let nlScore = 0;
    for (const w of nlWords) {
      if (lower.includes(w)) nlScore++;
    }
    return nlScore >= 2 ? 'nl' : 'en';
  }

  /**
   * Transform an API conversation object to the localStorage format.
   * @param {Object} apiConv - From /admin/api/conversations
   * @returns {Object} Portal-formatted conversation
   */
  _transformApiConversation(apiConv) {
    // Build messages in portal format
    const messages = [];
    let allText = '';
    let msgIdx = 0;

    for (const entry of (apiConv.messages || [])) {
      // Each API entry has both user and bot in one object
      if (entry.user) {
        messages.push({
          id: `msg_${msgIdx++}`,
          timestamp: entry.timestamp || '',
          requestId: null,
          role: 'user',
          content: entry.user,
          labels: [],
          rating: null
        });
        allText += ' ' + entry.user;
      }
      if (entry.bot) {
        messages.push({
          id: `msg_${msgIdx++}`,
          timestamp: entry.timestamp || '',
          requestId: null,
          role: 'bot',
          content: entry.bot,
          labels: [],
          rating: null
        });
        allText += ' ' + entry.bot;
      }
    }

    const language = this._detectLanguage(allText);

    return {
      id: apiConv.id,
      sessionId: apiConv.id,
      startedAt: apiConv.started || '',
      endedAt: apiConv.lastMessage || '',
      language: language,
      messageCount: messages.length,
      status: 'open',
      labels: [],
      rating: null,
      notes: [],
      messages: messages
    };
  }

  /**
   * Fetch real conversations from the backend API and merge
   * with existing localStorage data (preserving labels, notes, etc.).
   *
   * @param {string} [apiKey] - If not given, uses stored key
   * @returns {Promise<{ synced: number, errors: string[] }>}
   */
  async syncFromApi(apiKey) {
    const key = apiKey || this.getAuth().apiKey;
    if (!key) {
      return { synced: 0, errors: ['No API key available'] };
    }

    try {
      const resp = await fetch('/admin/api/conversations', {
        method: 'GET',
        headers: { 'X-Admin-Key': key }
      });

      if (!resp.ok) {
        return { synced: 0, errors: [`API returned ${resp.status}`] };
      }

      const data = await resp.json();
      const apiConversations = data.conversations || [];

      // Read existing localStorage conversations to preserve metadata
      const existing = this._read(KEYS.CONVERSATIONS) || [];
      const existingMap = new Map();
      for (const conv of existing) {
        existingMap.set(conv.id, conv);
      }

      // Transform and merge
      const merged = [];
      for (const apiConv of apiConversations) {
        const transformed = this._transformApiConversation(apiConv);
        const prev = existingMap.get(apiConv.id);

        if (prev) {
          // Merge: update messages from API, keep portal metadata
          transformed.status = prev.status || 'open';
          transformed.labels = prev.labels || [];
          transformed.rating = prev.rating !== undefined ? prev.rating : null;
          transformed.notes = prev.notes || [];
          transformed.language = prev.language || transformed.language;

          // Preserve message-level labels/ratings from previous data
          const prevMsgMap = new Map();
          for (const m of (prev.messages || [])) {
            prevMsgMap.set(m.id, m);
          }
          for (const m of transformed.messages) {
            const pm = prevMsgMap.get(m.id);
            if (pm) {
              m.labels = pm.labels || [];
              m.rating = pm.rating !== undefined ? pm.rating : null;
            }
          }
        }

        merged.push(transformed);
      }

      // Sort newest first
      merged.sort((a, b) => new Date(b.startedAt) - new Date(a.startedAt));

      this._write(KEYS.CONVERSATIONS, merged);
      console.log(`StorageManager: synced ${merged.length} conversations from API`);
      return { synced: merged.length, errors: [] };

    } catch (e) {
      console.error('StorageManager: syncFromApi failed', e);
      return { synced: 0, errors: [e.message] };
    }
  }

  // ── Conversations (Read) ───────────────────────────────────────

  /**
   * Get conversations with optional filtering, sorting, and pagination.
   *
   * @param {Object} filters
   * @param {string}   [filters.status]     - Filter by status
   * @param {string}   [filters.language]   - Filter by language ("nl"|"en")
   * @param {string}   [filters.label]      - Filter by label (conversation-level)
   * @param {string}   [filters.dateFrom]   - ISO date string lower bound
   * @param {string}   [filters.dateTo]     - ISO date string upper bound
   * @param {boolean}  [filters.hasNotes]   - Only conversations with notes
   * @param {boolean}  [filters.unrated]    - Only unrated conversations
   * @param {string}   [filters.search]     - Full-text search query
   * @param {string}   [filters.sortBy]     - "date"|"messages"|"rating" (default: "date")
   * @param {string}   [filters.sortDir]    - "asc"|"desc" (default: "desc")
   * @param {number}   [filters.page]       - Page number (1-based)
   * @param {number}   [filters.pageSize]   - Items per page
   * @returns {{ conversations: Array, total: number, page: number, pageSize: number, totalPages: number }}
   */
  getConversations(filters = {}) {
    let convs = this._read(KEYS.CONVERSATIONS) || [];

    // Apply filters
    if (filters.status) {
      convs = convs.filter(c => c.status === filters.status);
    }
    if (filters.language) {
      convs = convs.filter(c => c.language === filters.language);
    }
    if (filters.label) {
      convs = convs.filter(c => c.labels.includes(filters.label));
    }
    if (filters.dateFrom) {
      const from = new Date(filters.dateFrom).getTime();
      convs = convs.filter(c => new Date(c.startedAt).getTime() >= from);
    }
    if (filters.dateTo) {
      const to = new Date(filters.dateTo).getTime();
      convs = convs.filter(c => new Date(c.startedAt).getTime() <= to);
    }
    if (filters.hasNotes) {
      convs = convs.filter(c => c.notes && c.notes.length > 0);
    }
    if (filters.unrated) {
      convs = convs.filter(c => c.rating === null || c.rating === undefined);
    }
    if (filters.search) {
      const q = filters.search.toLowerCase();
      convs = convs.filter(c =>
        c.messages.some(m => m.content.toLowerCase().includes(q)) ||
        c.labels.some(l => l.toLowerCase().includes(q)) ||
        (c.notes && c.notes.some(n => n.text.toLowerCase().includes(q)))
      );
    }

    // Sorting
    const sortBy = filters.sortBy || 'date';
    const sortDir = filters.sortDir || 'desc';
    const dirMul = sortDir === 'asc' ? 1 : -1;

    convs.sort((a, b) => {
      switch (sortBy) {
        case 'messages':
          return (a.messageCount - b.messageCount) * dirMul;
        case 'rating':
          return ((a.rating || 0) - (b.rating || 0)) * dirMul;
        case 'date':
        default:
          return (new Date(a.startedAt) - new Date(b.startedAt)) * dirMul;
      }
    });

    // Pagination
    const total = convs.length;
    const pageSize = filters.pageSize || this.getSettings().pageSize || 20;
    const page = filters.page || 1;
    const totalPages = Math.ceil(total / pageSize);
    const start = (page - 1) * pageSize;
    const paged = convs.slice(start, start + pageSize);

    return { conversations: paged, total, page, pageSize, totalPages };
  }

  /**
   * Get a single conversation by ID.
   * @param {string} id
   * @returns {Object|null}
   */
  getConversation(id) {
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    return convs.find(c => c.id === id) || null;
  }

  // ── Conversations (Write) ──────────────────────────────────────

  _updateConversation(id, updater) {
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const idx = convs.findIndex(c => c.id === id);
    if (idx === -1) return false;
    updater(convs[idx]);
    return this._write(KEYS.CONVERSATIONS, convs);
  }

  // ── Labels ─────────────────────────────────────────────────────

  /**
   * Add a label to a conversation or specific message.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level label
   * @param {string} label
   */
  addLabel(conversationId, messageId, label) {
    return this._updateConversation(conversationId, (conv) => {
      if (messageId) {
        const msg = conv.messages.find(m => m.id === messageId);
        if (msg && !msg.labels.includes(label)) {
          msg.labels.push(label);
        }
      } else {
        if (!conv.labels.includes(label)) {
          conv.labels.push(label);
        }
      }
    });
  }

  /**
   * Remove a label from a conversation or specific message.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level label
   * @param {string} label
   */
  removeLabel(conversationId, messageId, label) {
    return this._updateConversation(conversationId, (conv) => {
      if (messageId) {
        const msg = conv.messages.find(m => m.id === messageId);
        if (msg) {
          msg.labels = msg.labels.filter(l => l !== label);
        }
      } else {
        conv.labels = conv.labels.filter(l => l !== label);
      }
    });
  }

  /**
   * Get all available label definitions.
   * @returns {Array}
   */
  getLabelDefinitions() {
    return this._read(KEYS.LABELS) || [];
  }

  /**
   * Add a new label definition.
   * @param {string} name
   * @param {string} color - hex color
   * @param {string} description
   */
  addLabelDefinition(name, color, description) {
    const labels = this._read(KEYS.LABELS) || [];
    if (labels.find(l => l.name === name)) return false;
    labels.push({ name, color, description });
    return this._write(KEYS.LABELS, labels);
  }

  // ── Ratings ────────────────────────────────────────────────────

  /**
   * Set quality rating on a conversation or specific message.
   * @param {string} conversationId
   * @param {string|null} messageId - null for conversation-level rating
   * @param {number} rating - 1 to 5
   */
  setRating(conversationId, messageId, rating) {
    if (rating !== null && (rating < 1 || rating > 5)) return false;
    return this._updateConversation(conversationId, (conv) => {
      if (messageId) {
        const msg = conv.messages.find(m => m.id === messageId);
        if (msg) msg.rating = rating;
      } else {
        conv.rating = rating;
      }
    });
  }

  // ── Notes ──────────────────────────────────────────────────────

  /**
   * Add an internal note to a conversation.
   * @param {string} conversationId
   * @param {string} text
   * @returns {Object|false} The created note, or false on failure
   */
  addNote(conversationId, text) {
    const auth = this.getAuth();
    const author = auth.user ? auth.user.username : 'anonymous';
    const note = {
      id: 'note_' + Math.random().toString(36).substring(2, 10),
      text: text,
      author: author,
      createdAt: new Date().toISOString()
    };

    const success = this._updateConversation(conversationId, (conv) => {
      if (!conv.notes) conv.notes = [];
      conv.notes.push(note);
    });

    return success ? note : false;
  }

  /**
   * Delete a note from a conversation.
   * @param {string} conversationId
   * @param {string} noteId
   */
  deleteNote(conversationId, noteId) {
    return this._updateConversation(conversationId, (conv) => {
      if (conv.notes) {
        conv.notes = conv.notes.filter(n => n.id !== noteId);
      }
    });
  }

  // ── Status ─────────────────────────────────────────────────────

  /**
   * Update conversation status.
   * @param {string} conversationId
   * @param {string} status - "resolved"|"escalated"|"unknown_flagged"|"open"
   */
  setStatus(conversationId, status) {
    const valid = ['resolved', 'escalated', 'unknown_flagged', 'open'];
    if (!valid.includes(status)) return false;
    return this._updateConversation(conversationId, (conv) => {
      conv.status = status;
    });
  }

  // ── Dashboard Stats ────────────────────────────────────────────

  /**
   * Compute dashboard statistics from current data.
   * @returns {Object}
   */
  getStats() {
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const total = convs.length;

    if (total === 0) {
      return {
        total: 0, byStatus: {}, byLanguage: {},
        avgMessagesPerConv: 0, avgRating: null,
        ratedCount: 0, unratedCount: 0,
        escalationRate: 0, unknownRate: 0,
        labelCounts: {}, notesCount: 0,
        conversationsToday: 0, conversationsThisWeek: 0,
        busiestHour: null, avgResponseMessages: 0
      };
    }

    // By status
    const byStatus = {};
    convs.forEach(c => {
      byStatus[c.status] = (byStatus[c.status] || 0) + 1;
    });

    // By language
    const byLanguage = {};
    convs.forEach(c => {
      byLanguage[c.language] = (byLanguage[c.language] || 0) + 1;
    });

    // Average messages
    const totalMessages = convs.reduce((sum, c) => sum + c.messageCount, 0);
    const avgMessagesPerConv = Math.round((totalMessages / total) * 10) / 10;

    // Average rating (only rated conversations)
    const rated = convs.filter(c => c.rating !== null && c.rating !== undefined);
    const avgRating = rated.length > 0
      ? Math.round((rated.reduce((sum, c) => sum + c.rating, 0) / rated.length) * 10) / 10
      : null;

    // Escalation and unknown rates
    const escalationRate = Math.round(((byStatus.escalated || 0) / total) * 1000) / 10;
    const unknownRate = Math.round(((byStatus.unknown_flagged || 0) / total) * 1000) / 10;

    // Label distribution
    const labelCounts = {};
    convs.forEach(c => {
      c.labels.forEach(l => {
        labelCounts[l] = (labelCounts[l] || 0) + 1;
      });
    });

    // Notes count
    const notesCount = convs.reduce((sum, c) => sum + (c.notes ? c.notes.length : 0), 0);

    // Time-based stats
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const weekStart = new Date(todayStart);
    weekStart.setDate(weekStart.getDate() - 7);

    const conversationsToday = convs.filter(c => new Date(c.startedAt) >= todayStart).length;
    const conversationsThisWeek = convs.filter(c => new Date(c.startedAt) >= weekStart).length;

    // Busiest hour
    const hourCounts = new Array(24).fill(0);
    convs.forEach(c => {
      const hour = new Date(c.startedAt).getHours();
      hourCounts[hour]++;
    });
    const busiestHour = hourCounts.indexOf(Math.max(...hourCounts));

    return {
      total,
      byStatus,
      byLanguage,
      avgMessagesPerConv,
      avgRating,
      ratedCount: rated.length,
      unratedCount: total - rated.length,
      escalationRate,
      unknownRate,
      labelCounts,
      notesCount,
      conversationsToday,
      conversationsThisWeek,
      busiestHour,
      avgResponseMessages: avgMessagesPerConv
    };
  }

  // ── Search ─────────────────────────────────────────────────────

  /**
   * Full-text search across conversations.
   * Returns matching conversations with highlighted context.
   *
   * @param {string} query
   * @returns {Array<{ conversation: Object, matches: Array<{ messageId: string, snippet: string }> }>}
   */
  search(query) {
    if (!query || query.trim().length === 0) return [];

    const q = query.toLowerCase().trim();
    const convs = this._read(KEYS.CONVERSATIONS) || [];
    const results = [];

    for (const conv of convs) {
      const matches = [];

      for (const msg of conv.messages) {
        const idx = msg.content.toLowerCase().indexOf(q);
        if (idx !== -1) {
          // Extract a snippet around the match
          const start = Math.max(0, idx - 40);
          const end = Math.min(msg.content.length, idx + q.length + 40);
          let snippet = '';
          if (start > 0) snippet += '...';
          snippet += msg.content.substring(start, end);
          if (end < msg.content.length) snippet += '...';

          matches.push({ messageId: msg.id, role: msg.role, snippet });
        }
      }

      // Also search notes
      if (conv.notes) {
        for (const note of conv.notes) {
          if (note.text.toLowerCase().includes(q)) {
            matches.push({ messageId: null, role: 'note', snippet: note.text.substring(0, 80) });
          }
        }
      }

      if (matches.length > 0) {
        results.push({
          conversation: {
            id: conv.id,
            startedAt: conv.startedAt,
            language: conv.language,
            status: conv.status,
            messageCount: conv.messageCount,
            labels: conv.labels
          },
          matches
        });
      }
    }

    return results;
  }

  // ── Export ──────────────────────────────────────────────────────

  /**
   * Export conversations in JSON or CSV format.
   * @param {string[]} ids - Conversation IDs to export (empty = all)
   * @param {string} format - "json" or "csv"
   * @returns {string} The formatted export data
   */
  exportConversations(ids = [], format = 'json') {
    let convs = this._read(KEYS.CONVERSATIONS) || [];

    if (ids.length > 0) {
      convs = convs.filter(c => ids.includes(c.id));
    }

    if (format === 'csv') {
      return this._toCSV(convs);
    }

    // JSON export - full data
    return JSON.stringify(convs, null, 2);
  }

  _toCSV(conversations) {
    const rows = [];
    rows.push([
      'conversation_id', 'session_id', 'started_at', 'ended_at',
      'language', 'status', 'message_count', 'rating', 'labels',
      'message_id', 'message_timestamp', 'role', 'content', 'message_labels', 'message_rating'
    ].join(','));

    for (const conv of conversations) {
      for (const msg of conv.messages) {
        rows.push([
          this._csvEscape(conv.id),
          this._csvEscape(conv.sessionId),
          this._csvEscape(conv.startedAt),
          this._csvEscape(conv.endedAt),
          conv.language,
          conv.status,
          conv.messageCount,
          conv.rating !== null ? conv.rating : '',
          this._csvEscape(conv.labels.join('; ')),
          this._csvEscape(msg.id),
          this._csvEscape(msg.timestamp),
          msg.role,
          this._csvEscape(msg.content),
          this._csvEscape(msg.labels.join('; ')),
          msg.rating !== null ? msg.rating : ''
        ].join(','));
      }
    }

    return rows.join('\n');
  }

  _csvEscape(val) {
    if (val === null || val === undefined) return '';
    const str = String(val);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  /**
   * Trigger a browser download of exported data.
   * @param {string[]} ids
   * @param {string} format - "json" or "csv"
   */
  downloadExport(ids = [], format = 'json') {
    const data = this.exportConversations(ids, format);
    const mimeType = format === 'csv' ? 'text/csv' : 'application/json';
    const ext = format === 'csv' ? 'csv' : 'json';
    const filename = `chat-export-${new Date().toISOString().slice(0, 10)}.${ext}`;

    const blob = new Blob([data], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // ── Settings ───────────────────────────────────────────────────

  getSettings() {
    return this._read(KEYS.SETTINGS) || { theme: 'light', pageSize: 20, defaultLanguageFilter: 'all' };
  }

  updateSettings(partial) {
    const current = this.getSettings();
    return this._write(KEYS.SETTINGS, { ...current, ...partial });
  }

  // ── Data Integrity & Maintenance ───────────────────────────────

  /**
   * Get current localStorage usage in bytes.
   * @returns {{ used: number, usedKB: string, estimatedMax: number }}
   */
  getStorageUsage() {
    let used = 0;
    for (const key of Object.values(KEYS)) {
      const val = localStorage.getItem(key);
      if (val) {
        used += key.length + val.length;
      }
    }
    // Each char is 2 bytes in JS (UTF-16)
    const usedBytes = used * 2;
    return {
      used: usedBytes,
      usedKB: (usedBytes / 1024).toFixed(1) + ' KB',
      estimatedMax: 5 * 1024 * 1024 // 5 MB conservative estimate
    };
  }

  /**
   * Reset all portal data and re-seed.
   */
  resetAll() {
    for (const key of Object.values(KEYS)) {
      localStorage.removeItem(key);
    }
    this._seedAll();
  }

  /**
   * Clear only conversations (keep auth, settings, labels).
   */
  clearConversations() {
    this._write(KEYS.CONVERSATIONS, []);
  }

  /**
   * Import conversations from JSON (merge or replace).
   * @param {string} jsonString
   * @param {boolean} replace - true to replace all, false to merge
   * @returns {{ imported: number, errors: string[] }}
   */
  importConversations(jsonString, replace = false) {
    const errors = [];
    let imported = 0;

    try {
      const data = JSON.parse(jsonString);
      if (!Array.isArray(data)) {
        return { imported: 0, errors: ['Invalid format: expected an array of conversations'] };
      }

      // Validate each conversation has required fields
      const valid = [];
      for (let i = 0; i < data.length; i++) {
        const c = data[i];
        if (!c.id || !c.messages || !Array.isArray(c.messages)) {
          errors.push(`Conversation at index ${i}: missing required fields (id, messages)`);
          continue;
        }
        valid.push(c);
      }

      if (replace) {
        this._write(KEYS.CONVERSATIONS, valid);
        imported = valid.length;
      } else {
        const existing = this._read(KEYS.CONVERSATIONS) || [];
        const existingIds = new Set(existing.map(c => c.id));
        for (const c of valid) {
          if (!existingIds.has(c.id)) {
            existing.push(c);
            imported++;
          } else {
            errors.push(`Conversation ${c.id}: already exists (skipped)`);
          }
        }
        this._write(KEYS.CONVERSATIONS, existing);
      }
    } catch (e) {
      errors.push('JSON parse error: ' + e.message);
    }

    return { imported, errors };
  }
}


// ================================================================
// SECTION 5 - SINGLETON EXPORT
// ================================================================

// Create a single global instance
const storageManager = new StorageManager();

# Skafferiet (Kök) – design

Datum: 2026-11-01 · Status: för granskning · Tillägg till Tvätt-tracker (samma repo, samma app)

## 1. Syfte

En ny del av appen på samma Raspberry Pi och 7"-skärm, **Kök**, som håller koll på vad som finns hemma, föreslår maträtter utifrån det, och har en inköpslista som man fyller genom att trycka på det man ofta köper. En USB-webbkamera läser streckkoder så att man kan hålla upp en vara och välja om den ska in i skafferiet eller på inköpslistan.

**Lyckat resultat:**
- Att växla mellan Tvätt och Kök tar ett tryck. Tvättens nedräkning och klar-notis syns även på Kök-sidan.
- Att markera att något tagit slut tar två tryck, och då hamnar det på inköpslistan av sig själv.
- *Vad kan vi laga?* visar direkt vilka recept som går att laga med det som finns hemma, och vad som saknas för resten.
- Ett ICA-recept kommer in i appen genom att man klistrar in länken eller söker på ica.se från skärmen.
- En skannad vara som appen känner igen tar ett tryck att lägga in i skafferiet. En okänd vara behöver bara läras in en gång.

## 2. Avgränsningar

- Inköpslistan finns på Pi:n (och i mobilen på hemnätet). Ingen åtkomst utanför hemnätet; hushållet tar med listan på eget sätt.
- Ingen koppling till Willys.
- Mängder hålls enkla: *Finns*, *Snart slut*, *Slut*, och ett valfritt antal för varor man räknar. Recepten drar inte av mängder.
- Kameran läser bara streckkoder (EAN-13, EAN-8, UPC-A, UPC-E). Bildinlärning av varor utan streckkod är **etapp 4** och ingår inte här (se avsnitt 12).
- Ingen veckomeny, inga näringsvärden, ingen omräkning av portioner.
- ICA har inget öppet API. Import och sök bygger på ica.se:s webbsidor och kan sluta fungera om ICA ändrar dem; då visas ett tydligt fel och resten av appen fungerar som vanligt.
- UI på svenska; kod, kommentarer och commits på engelska.

## 3. Arkitektur

Samma server, samma databas och samma SPA som tvättdelen. Köksdelen ligger i egna mappar så att den hålls isär från tvättkoden:

```
backend/app/kitchen/          ren logik, inga webbberoenden
  ingredients.py              tolka ingrediensrader, matcha mot varor
  suggest.py                  poängsätta recept mot skafferiet
  recipe_import.py            läsa schema.org-recept (JSON-LD) ur HTML
  ica.py                      sök på ica.se, tolka träfflistan
  products.py                 Open Food Facts-uppslag, kategorigissning
  scanner.py                  kamera + streckkodsläsning i en bakgrundstråd
  fetch.py                    gemensam HTTP-hämtning (stdlib urllib, tidsgränser, storleksgräns)
  seed.py                     startvaror
backend/app/routers/kitchen_*.py   API-rutter
frontend/src/kitchen/         Kök-sidorna och komponenter
frontend/src/kitchen/admin/   mobilsidor under Hantera
```

- **Nätverk:** all hämtning från internet (ica.se, receptsajter, Open Food Facts) görs av servern med Pythons standardbibliotek (`urllib.request`), med tidsgräns (10 s, 5 s för Open Food Facts), storleksgräns (3 MB) och en egen User-Agent. Inga nya beroenden för det.
- **Kamera:** servern läser USB-kameran med OpenCV (`opencv-python-headless>=4.8`, som har `cv2.barcode`). En bakgrundstråd läser bilder, avkodar streckkoder och sparar den senaste bilden som JPEG för förhandsvisning. Webbläsaren använder inte kameran själv.
- **Live-uppdatering:** samma SSE-kanal som tvätten, med nya ämnen `items`, `shopping`, `recipes` och `scan`.
- **Foton:** receptbilder sparas med befintliga `save_photo` i `~/tvatt-data/photos/`, så säkerhetskopian täcker allt.

## 4. Datamodell

Nya tabeller i `tvatt.db`:

| Tabell | Fält |
|---|---|
| `item` (vara) | id, name, category, status (`in_stock`/`low`/`out`), count (heltal eller NULL), staple (basvara 0/1), counted (räknas 0/1), match_words (kommaseparerade synonymer), buy_count, archived, created_at, updated_at |
| `barcode` | code (PK), item_id, product_name, created_at |
| `shopping_entry` | id, item_id (NULL för fritext), text, note, added_at |
| `recipe` | id, title, servings, minutes, source (`own`/`ica`/`web`), source_url (unik, NULL för egna), photo, instructions, cooked_count, last_cooked, archived, created_at |
| `recipe_ingredient` | id, recipe_id, sort, text (raden som den står), name (tolkat namn), item_id (NULL = okänd), optional (0/1), ignored (0/1) |
| `ingredient_map` | name (normaliserat ingrediensnamn, PK), item_id (NULL = "ingen vara, räkna inte") |

**Kategorier** (fast lista, i denna ordning): Kyl, Frys, Skafferi, Frukt & grönt, Bröd, Kryddor, Dryck, Hushåll.

**Regler:**
- En räknad vara med `count = 0` har status `out`; `count ≥ 1` ger `in_stock` om den inte är satt till `low`.
- När en vara går till `out` från `in_stock` eller `low` läggs den på inköpslistan, om inställningen `auto_list` är på (standard). Toast: "Mjölk lades på inköpslistan" med **Ångra**.
- En vara finns högst en gång på listan. Varje gång en vara läggs på listan ökar `buy_count`.
- Basvaror räknas alltid som hemma i recepten, men kan ändå markeras slut och hamna på listan.
- Arkiverade varor visas inte men behåller sina streckkoder och kopplingar.

**Startdata:** ett 60-tal vanliga varor fördelade på kategorierna, alla med status `out` ("inte hemma"), så man trycker i det som finns. Basvaror från början: salt, svartpeppar, matolja, olivolja, vetemjöl, strösocker. Startvarorna har synonymer där det behövs (t.ex. Svartpeppar ← "peppar", Matolja ← "rapsolja, neutral olja"). `ingredient_map` får från början "vatten", "kallt vatten", "ljummet vatten" och "kokande vatten" som *ingen vara*. Startdata läggs bara in när tabellen är tom; att lägga in dem räknas inte som "gått till slut".

**Ny inställning** i `setting`: `auto_list` = 1.

## 5. Ingredienser och matchning (kärnan)

En ren modul, `kitchen/ingredients.py`, testas isolerat.

**Tolka en rad** (`"2 dl vispgrädde (gärna laktosfri)"` → namn `vispgrädde`):
1. Gemener, ta bort text inom parentes, ta bort allt efter första kommatecknet (`"1 gul lök, finhackad"` → `"1 gul lök"`).
2. Ta bort inledande mängd: tal, decimaltal med komma eller punkt, bråk (`½ ¼ ¾ 1/2`), intervall (`2-3`, `2–3`), `ca`, `cirka`.
3. Ta bort en inledande enhet: g, kg, hg, mg, l, dl, cl, ml, msk, tsk, krm, st, förp, förpackning, paket, pkt, burk, burkar, flaska, klyfta, klyftor, skiva, skivor, knippe, kruka, påse, påsar, nypa, port, portion, bit, bitar.
4. Markera som **valfri** om raden innehåller *efter smak*, *till servering*, *till garnering*, *valfritt*, *gärna* eller *eventuellt*. Rubrikrader (slutar med `:` eller saknar bokstäver) tas bort.

**Matcha mot varor**, i den här ordningen, första träff vinner:
1. `ingredient_map` har namnet → den varan (eller "ingen vara").
2. Exakt lika med en varas namn eller ett av dess `match_words` (normaliserat).
3. Ett ord i ingrediensen matchar en vara: ordet är lika med varans namn, eller börjar med varans namn följt av en böjningsändelse (`ar, er, or, n, en, et, na, arna, erna, orna`), eller slutar med varans namn när det är minst 4 tecken (sammansättningar: *vispgrädde* → *Grädde*). Flerordsnamn ("krossade tomater") matchas som fras. Längsta varunamnet vinner.
4. Annars okänd (`item_id = NULL`).

När användaren rättar en koppling i receptvyn sparas den både på ingrediensraden och i `ingredient_map`, så att nästa recept med samma ingrediens matchas rätt. Matchningen körs om för alla recepts okända rader när en vara läggs till eller byter namn.

## 6. Förslag – *Vad kan vi laga?*

En ren modul, `kitchen/suggest.py`. För varje recept räknas ingredienserna som inte är valfria eller ignorerade:
- **har:** kopplad vara med status `in_stock` eller `low`, eller basvara.
- **saknas:** kopplad vara med status `out`.
- **okänd:** ingen kopplad vara. Räknas som saknad och visas som "okänd vara" i receptvyn, där man kan koppla den.

Sortering: antal saknade + okända (färst först), sedan antal `low`-varor som receptet använder (flest först, så att det som snart tar slut används), sedan längst sedan det lagades. Kortet visar "Allt finns hemma" eller "Saknar 2: grädde, purjolök".

**Lägg saknade på listan:** saknade varor läggs till som varor och okända rader som fritext (ingrediensnamnet), med anteckningen "till {receptets titel}".

## 7. Recept från ICA och andra sajter

**Import via länk** (`kitchen/recipe_import.py`): servern hämtar sidan och läser `<script type="application/ld+json">`-block. Den letar upp objektet med `@type` Recipe, även i listor och `@graph`, och tar ut namn, `recipeYield`, `totalTime` (ISO 8601, t.ex. `PT1H30M`), `recipeIngredient`, `recipeInstructions` (text, HowToStep eller HowToSection) och `image` (sträng, lista eller ImageObject). Bilden hämtas och sparas med `save_photo`; misslyckas det sparas receptet utan bild. Källan blir `ica` om värden slutar på `ica.se`, annars `web`. Samma länk två gånger öppnar det redan sparade receptet.
- Bara `http`/`https`, och inte adresser som pekar på det lokala nätet (localhost, privata IP-intervall).
- Saknar sidan receptdata visas "Hittade inget recept på sidan."

**Sök på ICA** (`kitchen/ica.py`): servern hämtar `https://www.ica.se/recept/?q=<sökord>` och plockar ut upp till 20 receptlänkar med titel och bild. Eftersom sidans uppbyggnad inte kan provas härifrån används tre strategier i tur och ordning: JSON-LD `ItemList`; JSON i `__NEXT_DATA__`/inbäddade skript, där servern letar efter objekt som har en länk av formen `/recept/<namn>-<id>/`; och till sist länkar i HTML:en med samma mönster. Varje träff förhandsgranskas sedan för sig (`/api/ica/preview`), högst fyra åt gången, och kortet uppdateras med "har 6 av 9". Förhandsgranskningar hålls i ett minnescache (50 st, 30 min).

**Egna recept** skrivs in i mobilen: titel, portioner, minuter, ingredienser (en per rad), gör så här (ett steg per rad) och valfritt foto.

## 8. Kamera och streckkoder

**Skanner** (`kitchen/scanner.py`): klassen `Scanner` tar en *bildkälla* (standard: `cv2.VideoCapture`, kamera 0 eller `TVATT_CAMERA`, 640×480; i tester en låtsaskälla). När den startas läser en tråd bilder, sparar var tredje som JPEG för förhandsvisningen (cirka 10 bilder/s) och kör `cv2.barcode.BarcodeDetector` på en gråskalebild. Koder vars kontrollsiffra inte stämmer kastas. Samma kod räknas bara en gång per 3 sekunder. Vid träff sparas `{seq, code, at}` och ämnet `scan` publiceras. Skannern stängs av efter 120 sekunder utan livstecken från klienten. Både `detectAndDecodeWithType` och äldre varianter av anropet hanteras.

**Saknas OpenCV eller kameran** svarar `POST /api/scan/start` med 503 och "Ingen kamera hittades. Kontrollera att webbkameran sitter i." Resten av appen påverkas inte, och OpenCV importeras först när skannern startas.

**Produktuppslag** (`kitchen/products.py`): okända koder slås upp i Open Food Facts (`/api/v2/product/{code}.json`, fälten `product_name_sv`, `product_name`, `brands`, `quantity`, `categories_tags`). Svaret ger ett förslag på namn ("Arla Mellanmjölk 1,5 % 1 l") och en gissad kategori (mejeri, ost, yoghurt → Kyl; fryst → Frys; bröd → Bröd; drycker → Dryck; frukt, grönsaker → Frukt & grönt; kryddor, såser → Kryddor; annars Skafferi). Går uppslaget inte fram fortsätter flödet utan förslag.

**Flödet på skärmen:** **Skanna** öppnar ett helskärmsblad med förhandsvisningen (`<img>` mot en MJPEG-ström) och texten "Håll streckkoden mot kameran".
- **Känd kod:** det piper (WebAudio), och ett kort visar varan och dess status. Knapparna är **In i skafferiet** (status `in_stock`, antal +1 om varan räknas), **På inköpslistan** och **Slut**.
- **Okänd kod:** kortet visar förslaget från Open Food Facts och **Koppla till vara**. Där finns liknande varor att välja bland (matchning mot namnet) och ett sökfält. Man kan också välja **Ny vara**, med namnet förifyllt och redigerbart med skärmtangentbordet och kategorin förvald. Koden sparas sedan i `barcode` och vald åtgärd utförs.
- **Skriv koden:** en sifferknappsats för när kameran inte kan läsa koden.
- Bladet står kvar för nästa vara tills man trycker **Klar**. Klienten skickar ett livstecken var 30:e sekund medan bladet är öppet.

Skanna-knappen visas bara på kiosken, eftersom kameran sitter vid Pi:n.

## 9. Gränssnitt

### Toppraden
Längst till vänster sitter en växlare **Tvätt | Kök** som minns senaste sida i varje del. I Kök-delen visas flikarna **Skafferi**, **Handla** (med antal) och **Recept**. Till höger finns tvättens nedräkning (som i dag), **Skanna** (bara på kiosken), klockan och kugghjulet. Klar-notisen för tvätten visas över hela appen, oavsett var man är.

### Skafferi (`#/kok/skafferi`)
Varorna visas som rutor grupperade efter kategori, med filtret **Alla · Hemma · Snart slut · Slut**. Statusen syns som färg och märke. Ett tryck på en vara öppnar ett litet blad med **Finns**, **Snart slut**, **Slut**, −/+ för räknade varor och **På inköpslistan**. Varor läggs till på kiosken med skärmtangentbordet (namn och kategori) eller i mobilen.

### Handla (`#/kok/handla`)
Inköpslistan står till vänster med stora rader och ✕ för att ta bort. Till höger finns **Ofta köpta**, upp till 24 varor sorterade efter `buy_count`; varor som redan står på listan är markerade, och ett nytt tryck tar bort dem. **Annat…** lägger till fritext med skärmtangentbordet.

**Packa upp** öppnar ett blad där allt på listan är förbockat. **Det här köptes** sätter bockade varor till *Finns* (antal +1 för räknade) och tar bort de bockade raderna. Fritextrader tas bara bort.

### Recept (`#/kok/recept`)
Överst finns *Vad kan vi laga?*: receptkorten med bild, titel, tid och "Allt finns hemma" eller "Saknar …". Knappen **Sök på ICA** öppnar sökvyn.

**Receptvyn** (`#/kok/recept/{id}`) har ingredienserna till vänster med ✓ (har), ✗ (saknas) och ? (okänd). Ett tryck på en rad kopplar den till en vara, eller väljer *Ingen vara, räkna inte*. Stegen står till höger i stor text. Knapparna är **Lägg saknade på listan** och **Vi lagade den**. Den senare öppnar ett blad med receptets varor, där man trycker för att markera *Snart slut* eller *Slut*; `cooked_count` och `last_cooked` uppdateras.

**Sök på ICA** (`#/kok/ica`): man väljer sökord som knappar bland varor som finns hemma (kyl och frukt & grönt först), eller skriver fritt. Träffarna visas som kort med "har X av Y" och **Spara**. Utan internet visas "Kunde inte nå ica.se. Kontrollera Pi:ns internetanslutning."

### Skärmtangentbord
En egen svensk tangentbordskomponent (QWERTY med å, ä och ö, siffror och tecken på en egen nivå, backsteg, mellanslag och **Klar**). Den visas på kiosken när ett textfält i köksdelen får fokus. Fälten har `inputMode="none"` på kiosken, så att inget systemtangentbord dyker upp. I mobilen används mobilens eget tangentbord.

### Mobilen – Hantera
Menyn får tre nya poster:
- **Varor:** lista per kategori. Här ändrar man namn, kategori, basvara, räknas och synonymer, ser och tar bort kopplade streckkoder, och arkiverar.
- **Recept:** lista, **Nytt recept**, **Importera från länk** och redigering (titel, portioner, tid, ingredienser, steg, foto).
- **Inställningar:** "Lägg på inköpslistan när något tar slut".

Kök-sidorna fungerar också i mobilen (responsivt), utom skanningen.

## 10. API (översikt)

- `GET /api/items`, `POST /api/items`, `PATCH /api/items/{id}` (namn, kategori, status, count, staple, counted, match_words), `DELETE /api/items/{id}` (arkiverar)
- `GET /api/shopping`, `POST /api/shopping` (`{item_id}` eller `{text}`, valfri `note`), `DELETE /api/shopping/{id}`, `POST /api/shopping/unpack` (`{entry_ids}`)
- `GET /api/recipes` (med förslagsdata), `GET /api/recipes/{id}`, `POST /api/recipes` (eget, multipart med valfritt foto), `PATCH /api/recipes/{id}`, `DELETE /api/recipes/{id}` (arkiverar), `POST /api/recipes/{id}/photo`
- `PATCH /api/recipes/{id}/ingredients/{ing_id}` (`{item_id}` eller `{ignored: true}`), `POST /api/recipes/{id}/missing-to-list`, `POST /api/recipes/{id}/cooked` (`{updates: [{item_id, status}]}`)
- `POST /api/recipes/import` (`{url}`), `GET /api/ica/search?q=`, `GET /api/ica/preview?url=`
- `POST /api/scan/start`, `POST /api/scan/stop`, `GET /api/scan/stream` (MJPEG), `GET /api/scan/last`
- `GET /api/barcodes/{code}` (`{item, product, lookup_failed}`), `POST /api/barcodes` (`{code, item_id}` eller `{code, new_item: {name, category}}`)
- `GET/PATCH /api/settings` får fältet `auto_list`.

Alla fel har ett svenskt `detail`, i samma form som tvätt-API:t.

## 11. Felhantering, installation och test

**Felhantering:**
- Externa hämtningar har tidsgränser och storleksgränser. Vid fel visas ett begripligt meddelande ("Kunde inte nå ica.se …", "Hittade inget recept på sidan.", "Produkten finns inte i Open Food Facts – skriv in ett namn").
- Kameran kan sakna OpenCV, sakna enhet eller sluta svara mitt i. Skanningsbladet visar då felet och knappen **Försök igen**, och sifferknappsatsen fungerar fortfarande.
- Validering av alla fält (tomma namn, även bara mellanslag, avvisas; okända kategorier och statusar avvisas; id som inte är tal ger 422, inte 500).

**Installation:**
- `requirements.txt` får `opencv-python-headless>=4.8`.
- `tvatt.service` får `SupplementaryGroups=video`, så att tjänsten får läsa kameran.
- `update.sh` installerar om systemd-filen när den ändrats (åtgärdar en känd småsak).
- Nytt kontrollskript `scripts/check_kitchen.py` som körs på Pi:n. Det provar kameran (öppnar den och läser streckkoder i 15 s medan man håller upp en vara), slår upp en svensk EAN-kod i Open Food Facts, söker "kyckling" på ICA och importerar första träffen. Varje del skrivs ut med ✓ eller ✗ och felorsak.
- README får ett avsnitt om Kök: kom igång, skanna, ICA och felsökning.

**Test:**
- *Enhetstester:* tolkning av ingrediensrader (mängder, enheter, bråk, parenteser, valfria rader, rubriker); matchning (exakt, synonymer, böjningar, sammansättningar, flerordsnamn, `ingredient_map`); förslagssortering; JSON-LD-tolkning (lista, `@graph`, HowToSection, ISO-tider, bildvarianter, sidor utan recept); ICA-träfflistan med alla tre strategierna; Open Food Facts-tolkning och kategorigissning; kontrollsiffror för EAN; skannern med en låtsaskälla som visar genererade EAN-13-bilder (debounce, livstecken, avstängning).
- *API-tester* mot temporär databas: varor och statusövergångar, auto-lista och dubbletter, packa upp, recept och kopplingar, saknade till listan, lagade, import (med låtsad hämtning), streckkoder och ny vara.
- *Webbläsartester* (Playwright, 800×480 kiosk och 390×844 mobil): växla Tvätt/Kök, markera slut → på listan → packa upp, förslag och lägg saknade på listan, skärmtangentbordet, skanningsflödet med låtsaskamera (känd och okänd kod), tvättens klar-notis på Kök-sidan.
- Exempelsidorna för ICA i testerna är egna efterbildningar av standardformatet, eftersom ica.se inte går att nå härifrån. Det riktiga beteendet kontrolleras med `check_kitchen.py` på Pi:n.
- Den färdiga leveransen granskas av en separat granskare.

**Byggordning (var och en testas, granskas och pushas):**
1. Växlare, varor, skafferi, inköpslista, skärmtangentbord, startdata, mobilens varusidor.
2. Recept, matchning, förslag, receptvy, import via länk, ICA-sök, mobilens receptsidor.
3. Skanner, streckkoder, Open Food Facts, skanningsbladet, installationsändringar, kontrollskript, README.

## 12. Senare (ingår inte)

**Etapp 4 – lära in varor utan streckkod:** man fotar en vara (frukt, bröd) några gånger från olika håll, och appen känner sedan igen den genom att jämföra en liten bildmodells beskrivning av kamerabilden med de inlärda bilderna (närmaste granne), med ett tröskelvärde och "Är det här Bananer?" som bekräftelse. Det kräver en liten förtränad bildmodell (t.ex. MobileNet i ONNX-format) på Pi:n. Den utvärderas när etapp 1–3 används i vardagen.

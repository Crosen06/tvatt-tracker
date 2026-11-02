# Bildigenkänning: varans kontur, poäng och fler inlärda bilder – design

Datum: 2026-11-02. Ändrar `2026-11-01-bildigenkanning-design.md` (avsnitt 4, 5, 6 och 8). Det som inte nämns här gäller som förut.

## 1. Syfte och problem

Igenkänningen tar i dag en kvadrat i mitten av hela kamerabilden (80 % av höjden). Kameran pekar mot den som står vid skärmen, så personen som håller varan är med både när varan lärs in och när den känns igen. Därför liknar nästan allt en inlärd vara så fort någon står framför kameran.

Charlie vill (2026-11-02):
- se en **kontur runt varan** i kamerabilden, med namn och **poäng**, så att man ser vad appen tittar på;
- att **personen som håller varan ignoreras**;
- att **Lär in tar fler bilder**, så att igenkänningen blir säkrare.

Lyckat resultat: konturen ligger runt varan och inte runt personen. Samma vara ger hög poäng oavsett vem som håller den och vilken tröja de har på sig. Andra varor och tom ruta ger låg poäng.

## 2. Beslut (från Charlie, 2026-11-02)

- Kameran **flyttas ibland**. Lösningen får inte bygga på en sparad bild av den tomma bakgrunden.
- Bilder som lärts in med den gamla metoden **tas bort automatiskt**.
- **Lär in** tar **24 bilder**.
- Metod A godkänd: en ruta i bilden, där varan klipps ut med GrabCut och ansikten ignoreras.

Metoder som valdes bort:
- Människosegmentering (PP-HumanSeg): i ett test räknades en förpackning framför bröstet som människa.
- En färdig objektdetektor (YOLOX/NanoDet): den känner bara 80 COCO-klasser, och de flesta förpackningar saknas.

## 3. Avgränsningar

- En vara åt gången, och den måste hållas i rutan.
- Har varan nästan samma färg som det som syns runt den, kan konturen bli fel. Då används hela rutan (se §4.3).
- Poängen är en likhet (cosinus), inte en sannolikhet. Gränsvärdena kalibreras fortfarande på Pi:n.
- Ingen egen träning av modellen; närmaste granne som förut.

## 4. Hitta varan (`kitchen/locate.py`)

Modulen tar en kamerabild och returnerar var varan finns och vilken bild modellen ska få. Den rör inte databasen.

### 4.1 Rutan
- Rutan är en kvadrat i mitten av bilden. Sidan är `TVATT_VISION_BOX` × bildens kortare sida, standard **0,6**, begränsad till 0,3–0,9.
- **Arbetsområdet** är rutan plus en ram på 20 % av rutans sida på varje håll, begränsad till bilden. Ramen visar vad som *inte* är vara.
- Arbetsområdet skalas ner så att längsta sidan blir högst **200 px**, så att GrabCut tar ungefär 50 ms på Pi:n.

### 4.2 Ansikten
- Ansikten hittas med **YuNet** (`face_detection_yunet_2023mar.onnx`, OpenCV Zoo, MIT, 232 589 byte) via `cv2.FaceDetectorYN`, på bilden nerskalad till 320 px bredd. Lägsta poäng är 0,7.
- Ett ansikte, förstorat med 15 % på varje håll, räknas alltid som bakgrund i GrabCut och blir grått i modellens bild.
- Saknas modellen, eller går den inte att ladda, hoppas steget över. Resten fungerar.

### 4.3 Kontur
1. GrabCut körs med en mask: arbetsområdet utanför rutan och ansiktena är säker bakgrund (`GC_BGD`), och rutan är trolig förgrund (`GC_PR_FGD`). Arbetsområdets yttersta pixelrad är alltid `GC_BGD`, så att det finns bakgrundsprover även om rutan når bildkanten. Tre iterationer.
2. Förgrunden (`GC_FGD`/`GC_PR_FGD`) inom rutan rensas med öppning (3×3). Sedan behålls den största sammanhängande delen och dess hål fylls.
3. Delen godtas som vara om den täcker **4–92 %** av rutan och skiljer sig i färg från ramen runt rutan. Färgskillnaden är Bhattacharyya-avståndet mellan Lab-histogrammen (8×6×6) för delen och ramen, och det måste vara **≥ 0,6**. Gränsen ändras med `TVATT_VISION_CONTRAST`. Annars, eller om GrabCut ger fel, räknas ingen vara som hittad (`found=False`). *(Tillagt efter granskningen: en tom ruta framför en rutig tröja gav annars en "vara" på 67 % av rutan.)*
4. Konturen förenklas (`approxPolyDP`, 1 % av omkretsen) och räknas om till koordinater i hela bilden.

### 4.4 Modellens bild (224×224)
- **Vara hittad:** utsnittet är en kvadrat runt varans omskrivna rektangel, plus 10 %, begränsad till bilden. Pixlar utanför varans mask (vidgad 3 px) sätts till neutralgrått BGR (124, 116, 104), alltså ImageNet-medelvärdet, som blir ≈ 0 efter normalisering. Utsnittet skalas till 224×224.
- **Ingen vara hittad:** hela rutan används, med ansikten grå. Det är fortfarande mycket mindre än dagens 80 %.
- Den sparade miniatyren är samma bild, så Inlärda bilder visar bara varan.

### 4.5 Resultat
`Located(box, contour | None, found: bool, image224)`. `box` är rutan och `contour` en lista med punkter (x, y) i hela bildens koordinater.

## 5. Fingeravtryck och poäng (`kitchen/vision.py`)

- `model_input(frame)` ersätts av `locate.locate(frame, faces)`. `center_crop` och `CROP_FRACTION` tas bort.
- **Modell-id** får ett metodsuffix: `mobilenetv2-2022apr-1280-obj1` (testmodellen: `histogram-v1-obj1`). Gamla rader har id utan suffix.
- **Poäng per vara:** snittet av varans **3 bästa** cosinus (eller så många bilder som finns, om de är färre). Förut användes den enskilt bästa.
- Gränserna `SURE`, `MAYBE` och `MARGIN` har samma standardvärden (0,80/0,65/0,05) och samma miljövariabler.
- **Tak:** max **80** bilder per vara (förut 40). Reglerna för dubbletter och vilka bilder som tas bort först är oförändrade.

## 6. Gamla bilder

När bildigenkänningen laddas första gången efter start tas rader i `item_image` bort, med sina filer, om `model` är ett id utan suffix från tidigare versioner: `mobilenetv2-2022apr-<n>` eller `histogram-v1`. Rader med andra id rörs inte. Ämnet `vision` publiceras om något togs bort. Allt sker i en transaktion och filerna tas bort efteråt, som vid vanlig borttagning.

## 7. Löpande analys och kontur i kamerabilden

### 7.1 Arbetstråden
Arbetstråden (`vision_service._run`) gör en analys var **0,4 s** medan kameran går, i stället för var 0,25 s:
1. Rutan och varan hittas (§4), varan får ett fingeravtryck, och det jämförs med galleriet.
2. Resultatet sparas som **senaste analys**: `{at, box, contour, found, label, score, decision}`. `label` är namnet på bästa varan, eller tomt om galleriet är tomt.
3. `Watcher` får fingeravtrycket som redan räknats ut. Stillhetskontrollen är oförändrad men sker nu var 0,4 s. Två stilla kontroller i rad betyder ungefär 0,8 s.

Förslag görs fortfarande bara vid säker träff och följer reglerna i förra specen, §6.

### 7.2 Ritning
`Scanner` får en valfri `overlay(img, frame_size)` som anropas på den nerskalade förhandsbilden innan den kodas till JPEG. `VisionService.draw_overlay` ritar bara när bildigenkänningen finns och arbetstråden går:
- **Rutan:** vita streckade hörn (inte hel ram), 2 px. Under rutan står "Håll varan i rutan" när ingen vara är hittad.
- **Konturen**, om senaste analysen är högst 1,5 s gammal och har `found`:
  - **grön** (#2fbf71) vid `sure`
  - **gul** (#f2b33d) vid `maybe`
  - **vit** vid `none`
  Linjen är 3 px.
- **Etikett** i en rundad ruta i samma färg, ovanför konturens översta punkt (inom bilden):
  - `sure`: "Mjölk 87 %"
  - `maybe`: "Mjölk? 71 %"
  - `none` med galleri: "Okänd (Mjölk 42 %)"
  - tomt galleri: "Okänd"
- Texten ritas med Pillow och Poppins Medium (`static/fonts/poppins-medium.woff`, finns redan), 16 px vid 640 px bredd. Pillow är redan ett beroende. Om typsnittet inte går att läsa används Pillows standardtypsnitt.
- Ett fel vid ritningen loggas en gång och ger en bild utan ritning. Det får aldrig stoppa skannern.

Konturen ritas i själva bilden, så den hänger alltid ihop med bilden, även med förhandsbildens beskärning.

## 8. Lär in

- **24 bilder.** Ett försök var 400:e ms, högst **48 försök**. Det första försöket görs efter 1,5 s, och under tiden står "Gör dig redo – håll upp varan i rutan". Då hinner man ta upp varan efter att ha valt den på tangentbordet, så att tröjan inte lärs in.
- **Automatisk inlärning** (läst eller kopplad streckkod) sparar bara bilder där en vara hittades i rutan.
- `POST /api/vision/capture` svarar `{saved, count, found}`. Bilder där ingen vara hittas sparas inte (`saved: false, found: false`).
- **Inlärningsvyn** visar kamerabilden (samma MJPEG-ström) med rutan och konturen, förloppsindikatorn och "12 av 24 bilder". Har de senaste 5 försöken saknat vara står "Håll varan i rutan".
- Texten är "Håll varan i rutan och vrid den långsamt – visa fram, bak och sidor".
- Avslutningen är som förut: toast "Lärde in 24 bilder av Mjölk" och vyn stängs.

## 9. Installation och verktyg

- `deploy/get-model.sh` hämtar också YuNet till `~/tvatt-data/models/face_yunet.onnx`, med sha256 `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`, från `https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx`. Skriptet hämtar båda modellerna och kontrollerar var för sig. Ett fel för ansiktsmodellen stoppar inte installationen. Sökvägen kan ändras med `TVATT_FACE_MODEL`.
- `scripts/camera_test.py --recognize` skriver per sekund ut om en vara hittades, hur stor del av rutan den täcker, färgskillnaden (kontrast), tid för analysen och de tre bästa varorna med poäng. Bilden som sparas (`~/tvatt-data/kamera-test.jpg`) får rutan, konturen och etiketten inritade.
- README: avsnittet "Känna igen varor på bilden" uppdateras (rutan, kontur och färger, 24 bilder, att gamla bilder tas bort, `TVATT_VISION_BOX`, ansiktsmodellen).

## 10. Felhantering

- GrabCut-fel eller tom mask ger `found=False` och hela rutan (§4.4).
- Ansiktsmodellen saknas eller går inte att läsa: inga ansikten. Det loggas en gång.
- Ett fel i analysen stänger av arbetstråden för sessionen, som förut, och tar bort konturen. Skannern och streckkoderna fortsätter.
- `draw_overlay` får aldrig kasta undantag in i skannertråden.

## 11. Test

- **Enhet (`locate`):**
  - Syntetisk scen: tröja med mönster, kök och en förpackning i rutan. Konturen ska täcka förpackningen (IoU ≥ 0,8), och förpackningen ska ge `found`.
  - Tom ruta (bara tröja) ger antingen `found=False` eller en kontur, men aldrig ett fel.
  - Ett "ansikte" som skickas in hamnar aldrig i varans mask och blir grått i modellens bild.
  - Rutan vid bildkant och små bilder.
  - `TVATT_VISION_BOX` och dess gränser.
- **Enhet (vision):** poäng som snitt av topp 3, modell-id med suffix, borttagning av gamla rader, taket 80.
- **Samma vara, olika tröjor:** samma förpackning framför två olika tröjor ska ge cosinus ≥ 0,9 med histogrammodellen. Med den riktiga MobileNetV2 och YuNet ska den bli högre mot varan än mot en annan förpackning. Testet med riktiga modeller hoppas över om modellfilerna saknas; i molnmiljön körs det med modellerna hämtade.
- **Ritning:** `draw_overlay` ger en bild i samma storlek, med grön kontur vid säker träff. Etiketten med å/ä/ö kraschar inte, inte heller utan typsnittsfil.
- **API:** `capture` svarar med `found` och sparar inte bilder utan vara. Övriga vägar är oförändrade.
- **E2E (800×480):** låtsaskameran visar en förpackning i rutan. Lär in visar kamerabilden och avslutas med en toast. (Låtsaskameran visar samma bild hela tiden, så dubblettregeln ger färre än 24 bilder.) Varan känns sedan igen. Gamla tester uppdateras till den nya rutan.
- På Pi:n: `./deploy/update.sh`, sedan `scripts/camera_test.py --recognize` för att kontrollera konturen och kalibrera gränserna.

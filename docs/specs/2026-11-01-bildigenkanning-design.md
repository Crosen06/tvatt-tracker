# Bildigenkänning av varor (Kök, etapp 4) – design

Datum: 2026-11-01. Bygger på `2026-11-01-skafferiet-design.md` (avsnitt 8 och 12).

## 1. Syfte

Hushållets webbkamera (Plexgear WC-800) har fast fokus. Streckkoder på 15–25 cm blir suddiga och läses sällan. Appen ska därför också kunna känna igen varor på hur de ser ut: man håller upp en vara, och appen föreslår vilken vara det är. Nya varor lärs in genom att man håller upp dem i några vinklar. Igenkänningen fungerar också för varor utan streckkod, som frukt, bröd och hemlagat.

Lyckat resultat: de varor hushållet brukar köpa känns igen på 1–2 sekunder när de hålls stilla framför kameran. Rätt vara finns bland de tre förslagen i de flesta fall, och appen blir bättre ju mer den används.

## 2. Beslut (från Charlie, 2026-11-01)

- **Start:** automatiskt när en vara hålls stilla och liknar en inlärd vara starkt. Knappen **Vad är det här?** finns alltid.
- **Säker träff:** varukortet visas direkt (In i skafferiet / På inköpslistan / Slut), plus de två näst bästa förslagen och **Fel vara?**.
- **Inlärning:** både automatiskt (en bild sparas när en streckkod läses eller ett förslag bekräftas) och med knappen **Lär in** (8 bilder medan man vrider varan).
- **Hantering:** en sida i mobilen under Hantera, **Inlärda bilder**, med miniatyrer per vara som går att ta bort.

## 3. Avgränsningar

- Ingen egen träning av en modell. En förtränad modell ger "fingeravtryck" (embedding), och igenkänningen jämför med närmaste granne.
- Bara en vara åt gången, i mitten av bilden. Ingen objektdetektering. *(Ändrat 2026-11-02: varan klipps ut ur en ruta i bilden, se `2026-11-02-varans-kontur-design.md`.)*
- Nästan likadana förpackningar (mellan- och standardmjölk) kan blandas ihop. Därför bekräftar man alltid genom att trycka på en åtgärd.
- Gränsvärdena är en kvalificerad gissning och kalibreras på Pi:n med `scripts/camera_test.py --recognize`.

## 4. Modell

- **MobileNetV2** från OpenCV Zoo: `image_classification_mobilenetv2_2022apr.onnx`, Apache-2.0, 13 964 571 byte, sha256 `c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5`. Den hämtas från `https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/image_classification_mobilenet/image_classification_mobilenetv2_2022apr.onnx` av `deploy/get-model.sh`. Skriptet anropas från `install.sh` och `update.sh` och kontrollerar kontrollsumman. Ett fel stoppar inte installationen.
- Modellen sparas som `~/tvatt-data/models/mobilenetv2.onnx`. Sökvägen kan ändras med `TVATT_VISION_MODEL`.
- Modellen körs med `cv2.dnn`, så inget nytt Python-paket behövs.
- **Indata:** en kvadrat i mitten av bilden, med sidan 80 % av bildens höjd. Kvadraten skalas till 224×224, görs om från BGR till RGB och normaliseras med ImageNet-värdena (mean 0.485/0.456/0.406, std 0.229/0.224/0.225), i formatet NCHW float32.
- **Fingeravtryck:** utdata från sista lagret av typen Pooling/Flatten/Reshape före klassificeraren, alltså 1280 värden. Hittas inget sådant lager används modellens utdata. Vektorn L2-normaliseras och lagras som float16.
- **Tester och utveckling:** `HistogramEmbedder` ger ett fingeravtryck från ett HSV-histogram plus en 8×8-gråskalebild. Den väljs med `TVATT_FAKE_VISION=1` och i tester, aldrig i produktion. Saknas modellen är bildigenkänningen avstängd, och `status` säger "Bildigenkänningen är inte installerad. Kör ./deploy/update.sh."
- Varje fingeravtryck sparas med modellens id plus fingeravtryckets längd (`mobilenetv2-2022apr-1280`, i tester `histogram-v1`). Bara rader från den aktiva modellen jämförs. Längden ingår i id:t, så att fingeravtryck från ett annat lager aldrig blandas ihop med de vanliga, till exempel om en annan OpenCV-version skulle välja ett annat lager.

## 5. Datamodell

```sql
CREATE TABLE IF NOT EXISTS item_image (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES item(id),
    file TEXT NOT NULL,            -- 224×224 JPEG i ~/tvatt-data/vision/
    model TEXT NOT NULL,
    embedding BLOB NOT NULL,       -- float16, L2-normaliserad
    source TEXT NOT NULL,          -- 'learn' | 'scan' | 'confirm'
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS item_image_item ON item_image(item_id);
```

- Den sparade bilden är samma 224×224-utsnitt som modellen fick. Den visas som miniatyr och kan användas för att räkna om fingeravtryck om modellen byts.
- **Dubbletter:** en ny bild sparas inte om den har cosinus ≥ 0,97 mot en befintlig bild av samma vara.
- **Tak:** max 40 bilder per vara. När taket nås tas den äldsta automatiska bilden (`scan`/`confirm`) bort först. Består varan bara av `learn`-bilder sparas inte en ny automatisk bild, medan en ny `learn` ersätter den äldsta `learn`.
- Arkiverade varor ingår inte i jämförelsen, men deras bilder ligger kvar.

## 6. Igenkänning

**Galleri** (`kitchen/vision.py`): galleriet håller alla fingeravtryck för aktiva varor i en numpy-matris. Matrisen laddas om när bilder har ändrats (versionsräknare). Poängen för en vara är högsta cosinus mot någon av varans bilder. Resultatet är de tre bästa varorna.

**Beslut:**
- `sure`: bästa ≥ `SURE` (0,80) och bästa − näst bästa ≥ `MARGIN` (0,05).
- `maybe`: bästa ≥ `MAYBE` (0,65).
- Annars `none`.

Gränserna kan ändras med `TVATT_VISION_SURE`, `TVATT_VISION_MAYBE` och `TVATT_VISION_MARGIN`.

**Automatiskt läge** (en egen arbetstråd medan kameran går, 4 kontroller/s):
1. Från senaste kamerabilden görs en gråskalebild på 32×24. Bilden räknas som stilla när medelskillnaden mot förra kontrollen < 6 (av 255) två kontroller i rad, ungefär 0,5 s.
2. När bilden är stilla, har rört sig sedan förra försöket och ingen streckkod lästs de senaste 2 s räknas ett fingeravtryck ut.
3. **Bakgrund:** en stilla bild med cosinus ≥ 0,92 mot bakgrunden betyder att ingen vara hålls upp. Bakgrunden byts då mot den nya bilden, så att den följer ljusförändringar.
4. **Förslag bara vid säker träff:** annars jämförs bilden med galleriet.
   - Vid `sure` sparas ett förslag `{seq, token, matches, decision}`, och ämnet `vision` publiceras.
   - Vid `maybe` eller `none` blir bilden i stället ny bakgrund. Ett tomt kök, eller en vara som hölls upp när bladet öppnades, fastnar alltså aldrig.
5. **Samma vara:** bilden av varan som just föreslogs, eller vars streckkod just lästes, sparas. En stilla bild med cosinus ≥ 0,90 mot den räknas som samma vara och föreslås inte igen, även om handen skakar lite.
6. **Streckkod:** en läst streckkod markerar att varan är omhändertagen. Inget förslag kommer förrän bilden har rört sig igen.

**Vad är det här?** (`POST /api/vision/identify`): kör igenkänningen på senaste bilden direkt, utan bakgrunds- och stillhetskontroll, och svarar alltid med de tre bästa förslagen, även vid `none`.

**Väntande fingeravtryck (token):** varje igenkänning och varje läst streckkod sparar `{embedding, jpeg, at}` under en token i minnet. Max 30 lagras, och de gäller i 10 minuter. Bekräftas förslaget sparas bilden med `source='confirm'`.

**Automatisk inlärning vid streckkod:** när skannern läser en kod sparas den senaste bilden under en token kopplad till koden. Det sker i en egen kort tråd, så att avläsningen inte väntar på modellen.
- Är koden redan kopplad till en vara sparas bilden direkt (`source='scan'`).
- Annars sparas den när koden kopplas (`POST /api/barcodes`).

Bara streckkoder som kameran läser räknas, inte koder som skrivs in för hand.

## 7. API

| Metod | Väg | Svar |
|---|---|---|
| GET | `/api/vision/status` | `{available, message, images}` |
| GET | `/api/vision/last` | `{seq, token, decision, matches:[{item, score}]}` (seq 0 = inget) |
| POST | `/api/vision/identify` | samma form som `last`. 503 om avstängd, 409 om kameran inte går |
| POST | `/api/vision/capture` `{item_id}` | `{saved, count}`. Bilden sparas som `learn` om den inte är en dubblett |
| POST | `/api/vision/confirm` `{token, item_id}` | `{saved}`. Okänd eller utgången token ger `{saved: false}` (inget fel) |
| GET | `/api/vision/items` | `[{item_id, name, count, cover}]` för varor med bilder |
| GET | `/api/items/{id}/images` | `[{id, url, source, created_at}]` |
| DELETE | `/api/vision/images/{id}` | 204 |
| DELETE | `/api/items/{id}/images` | 204 |

- Bilderna serveras från `/vision/<fil>` (StaticFiles på `~/tvatt-data/vision`).
- Felmeddelanden är på svenska i `{"detail": …}`.
- SSE-ämnet `vision` publiceras vid nytt förslag och när bilder ändras.

## 8. Gränssnitt

**Skanningsbladet (kiosk):**
- I huvudet finns **Vad är det här?**, **Lär in**, **Skriv koden** och **Klar**. De två första visas bara när bildigenkänningen är installerad.
- **Automatiskt förslag** (bara säkra träffar) visas bara när panelen är tom, alltså inget kort visas och inget slås upp. En streckkod tar alltid över.
- **Säker träff:** varukortet för bästa varan. Under det står "Eller:" med de två andra som knappar, och **Fel vara?**, som öppnar varuväljaren.
  - Den första åtgärden på kortet bekräftar förslaget.
  - Att välja en annan vara bekräftar den varan och visar dess kort.
- **Osäker träff, eller Vad är det här?:** "Är det någon av de här?" med de tre förslagen, samt **Sök vara** och **Ny vara**. Ett val bekräftar och visar varukortet. Hittades inget visas "Känner inte igen varan" och samma knappar.
- **Lär in:** varuväljaren (med **Ny vara**) öppnar inlärningsvyn för vald vara. Inlärningskortet kan också öppnas från varukortet med **Lär in bilder**.
  - Inlärningsvyn tar en bild var 700:e ms tills 8 bilder har sparats, eller högst 16 försök.
  - Medan den kör visas "Vrid varan långsamt … 3 av 8".
  - Efteråt visas "Lärde in 8 bilder av Mjölk".

**Mobilen:** under Hantera → **Inlärda bilder** listas varor med antal bilder och en miniatyr. Varans sida visar alla miniatyrer. Ett tryck tar bort en bild (med Ångra-toast), och **Ta bort alla** frågar först.

## 9. Felhantering och installation

- Saknas modellen, eller går den inte att ladda: `available=false`, knapparna döljs och streckkoderna fungerar som förut.
- Ett fel i arbetstråden stänger bara av det automatiska läget för den sessionen. Det loggas och tar inte ner skannern.
- `deploy/get-model.sh` hämtar till en temporär fil, kontrollerar sha256 och flyttar sedan filen på plats. Finns filen redan med rätt kontrollsumma görs inget.
- `scripts/camera_test.py --recognize` visar modell, fingeravtryckets längd, tid per igenkänning och de tre bästa förslagen med poäng varje sekund, för att kalibrera gränserna.
- Egna inställningar (gränser, kamera, upplösning) skrivs i `~/tvatt-data/tvatt.env`. Tjänsten läser filen via `EnvironmentFile`, `camera_test.py` läser den också, och uppdateringar skriver inte över den.

## 10. Test

- **Enhet:**
  - Förbehandling och val av lager (med en låtsasmodell och ett litet riktigt Darknet-nät via `cv2.dnn`).
  - Histogrammodellen.
  - Galleriets poäng och beslut.
  - Dubbletter och tak.
  - Tokens (gräns och utgång).
  - Stillhet och bakgrund med låtsasklocka och syntetiska bilder.
- **API:** alla vägar ovan, inklusive 503 utan modell, 409 utan kamera, automatisk inlärning vid läst och kopplad streckkod, och arkiverade varor.
- **E2E (Playwright, 800×480):** låtsaskamera med färgade bilder och `TVATT_FAKE_VISION=1`. Man lär in en vara, håller upp den igen och ser att varukortet visas och att "In i skafferiet" fungerar. Mobilsidan Inlärda bilder testas också.
- Den riktiga MobileNetV2 provas först på Pi:n, med `camera_test.py --recognize`.

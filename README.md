# Tvätt-tracker

En touchskärm i huset som håller koll på tvättkorgen. Charlie, Kiki och Magnus har var sin flik och trycker på sina plagg när de lägger dem i korgen. Appen föreslår vilka plagg som kan tvättas ihop, räknar ner medan maskinen går och säger till på skärmen när tvätten är klar.

Med knappen **Tvätt | Kök** uppe till vänster växlar man till köket: skafferiet, inköpslistan, recept med förslag på vad ni kan laga, och en webbkamera som läser streckkoder (se [Kök](#kök)).

- **Pi-skärmen** (Raspberry Pi 4 + 7"-touchskärm) visar korgen, tvättförslagen och nedräkningen.
- **Mobilen** används för att fota och tagga nya plagg på `http://tvatt.local` (samma wifi).

## Installera på Raspberry Pi

Du behöver Raspberry Pi OS med skrivbord, och Pi:n ska vara ansluten till hemmets wifi.

1. Öppna en terminal på Pi:n (eller logga in via SSH) och hämta koden:

   ```bash
   git clone https://github.com/Crosen06/tvatt-tracker.git
   cd tvatt-tracker
   ```

2. Kör installationen:

   ```bash
   ./deploy/install.sh
   ```

   Skriptet gör följande:
   - installerar Python-miljön och Chromium
   - startar appen som en tjänst som går igång automatiskt vid start
   - byter värdnamn till `tvatt`, så att appen nås på `http://tvatt.local`
   - ställer in att Pi:n startar direkt i skrivbordet, att tvätt-trackern öppnas i helskärm och att skärmen släcks när den inte används. Tryck på skärmen för att väcka den; det första trycket väcker bara skärmen och trycker inte på något. När en tvätt är klar tänds skärmen av sig själv.

   Vill du behålla värdnamnet kör du `./deploy/install.sh --no-hostname`. Då nås appen på `http://<pi:ns-namn>.local`.

3. Starta om: `sudo reboot`

### Kom igång

1. Öppna `http://tvatt.local` i mobilen och tryck på **Lägg till plagg**. Fota plagget, välj vems det är och tagga färg, temperatur, centrifug och typ av tvätt. Värdena finns på tvättlappen.
2. Gå till **Hantera → Tvättprogram** och ändra längderna så att de stämmer med er tvättmaskin. Programmen från början är bara ungefärliga.
3. På skärmen trycker man på sin flik och sedan på plaggen man lägger i korgen.
4. Under **Tvätta** syns förslagen. Tryck på **Starta tvätt**, välj program och starta. När tiden har gått visas *Tvätten är klar!*. Tryck **Tömt maskinen** så tas plaggen ur korgen.

## Så räknar appen ut vad som kan tvättas ihop

- Plaggen måste vara i samma färggrupp: vitt, ljust, mörkt eller kulört.
- Bomull och syntet går att tvätta ihop. Fintvätt, ull och handtvätt tvättas var för sig.
- Plagg som tål 60° eller mer får en egen tvätt (det går att stänga av under **Inställningar**).
- Tvätten körs på den lägsta temperatur och centrifug som alla plagg i gruppen tål. Program som är för varma för plaggen går inte att välja.

## Kök

### Kom igång
1. Tryck **Kök** uppe till vänster på skärmen. Under **Skafferi** finns ett 60-tal vanliga varor, alla markerade som *Slut*. Tryck på det ni har hemma och välj **Finns**.
2. Fattas en vara trycker du **Ny vara** och skriver namnet med skärmtangentbordet.
3. I mobilen, under **Hantera → Varor**, kan du ändra namn och kategori, markera *basvaror* (salt, olja och liknande räknas alltid som hemma) och skriva in andra namn som varan kan ha i recept.

### Skafferi och inköpslista
- Tryck på en vara och välj **Finns**, **Snart slut** eller **Slut**. Det som markeras *Slut* hamnar på inköpslistan (det går att stänga av under **Hantera → Inställningar**). Ångra i rutan som dyker upp om det blev fel.
- Under **Handla** står listan till vänster och *Ofta köpta* till höger. Tryck på en vara för att lägga den på listan, och tryck igen för att ta bort den. Med **Annat…** skriver du in något som inte finns bland varorna.
- När ni kommit hem trycker ni **Packa upp**. Bocka ur det ni inte fick med er, så markeras resten som hemma.

### Recept
- Under **Recept** visas *Vad kan vi laga?*, där de recept som det saknas minst till står först. Öppna ett recept för att se vad som finns (✓), saknas (✗) eller är okänt (?). Tryck på en rad för att koppla den till rätt vara; appen kommer ihåg det till nästa recept.
- **Lägg saknade på listan** lägger det som fattas på inköpslistan. **Vi lagade den** låter er snabbt markera det som tog slut.
- **Sök på ICA**: välj några varor ni har hemma eller skriv själv. Varje träff visar hur många av ingredienserna ni har, och **Spara** lägger in receptet.
- I mobilen, under **Hantera → Recept**, skriver du in egna recept eller klistrar in en länk till ett recept (från ICA eller andra receptsajter som visar receptdata, till exempel Arla och Köket).

### Webbkamera och streckkoder
1. Sätt i webbkameran i en USB-port på Pi:n och kör `./deploy/update.sh`, så installeras det som behövs.
2. Tryck **Skanna** i köket och håll streckkoden 15–25 cm från kameran. Det piper när koden är läst.
3. Känner appen igen varan väljer du **In i skafferiet**, **På inköpslistan** eller **Slut**. Är den ny föreslår appen ett namn från Open Food Facts; tryck **Ny vara** eller välj en befintlig vara. Nästa gång känns koden igen direkt.
4. Går koden inte att läsa trycker du **Skriv koden** och skriver siffrorna under strecken.

### Kontrollera att allt fungerar på Pi:n
Kameran, ICA och Open Food Facts kunde inte provas när appen byggdes, så kör det här efter installationen:

```bash
cd ~/tvatt-tracker
.venv/bin/python scripts/check_kitchen.py
```

Skriptet startar kameran och ber dig hålla upp en vara, slår upp en streckkod i Open Food Facts, söker "kyckling" på ICA och läser in första receptet. Varje del får ✓ eller ✗ med en förklaring.

## Uppdatera

```bash
cd ~/tvatt-tracker
./deploy/update.sh
```

## Säkerhetskopiera

Alla plagg, varor, recept, foton och inställningar ligger i `~/tvatt-data`. Stoppa appen en kort stund medan mappen kopieras, så att databasen inte ändras mitt i kopieringen:

```bash
sudo systemctl stop tvatt
cp -r ~/tvatt-data ~/tvatt-data-backup-$(date +%F)
sudo systemctl start tvatt
```

## Felsökning

| Problem | Gör så här |
|---|---|
| `tvatt.local` öppnas inte i mobilen | Kontrollera att mobilen är på samma wifi. Vissa Android-mobiler förstår inte `.local`. Använd då Pi:ns IP-adress, som du ser med `hostname -I`. |
| Skärmen visar inte appen efter start | Kör `systemctl status tvatt` och `journalctl -u tvatt -n 50`. Startar inte webbläsaren, prova `~/tvatt-tracker/deploy/kiosk.sh` i en terminal. |
| Klockan visar fel tid | `sudo timedatectl set-timezone Europe/Stockholm` |
| "Bildformatet stöds inte" | Ta bilden direkt med kameran i stället för att välja en fil. |
| "Ingen kamera hittades" | Kontrollera att webbkameran sitter i och syns med `ls /dev/video*`. Starta om appen med `sudo systemctl restart tvatt`. Har du flera kameror kan du välja en annan med raden `Environment=TVATT_CAMERA=1` i `/etc/systemd/system/tvatt.service`. |
| Streckkoden läses inte | Mer ljus hjälper, och håll varan stilla 15–25 cm från kameran. Det går alltid att trycka **Skriv koden**. |
| "Kunde inte nå ica.se" | Pi:n behöver internet för ICA-sök, import och Open Food Facts. Kör `scripts/check_kitchen.py`. Visar ICA-sök ✗ fast internet fungerar har ica.se troligen ändrat sin sida; import via länk fungerar ofta ändå. |
| Skärmen släcks aldrig | `sudo raspi-config` → Display Options → Screen Blanking → på. |

## För utvecklare

- Backend: Python, [Starlette](https://www.starlette.io/) och SQLite i `backend/`. Starta med `scripts/dev.sh` (port 8000, data i `/tmp/tvatt-dev`). Lägg in exempelplagg med `python scripts/sample_data.py`.
- Gränssnitt: React 19 i `frontend/`, byggs med esbuild till `backend/app/static/` (som checkas in, så att Pi:n aldrig behöver Node). Bygg med `cd frontend && npm install && npm run build`.
- Köket: ren logik i `backend/app/kitchen/` (matchning av ingredienser, receptimport, ICA, streckkoder, kameran), API i `backend/app/routers/kitchen_*.py`, gränssnitt i `frontend/src/kitchen/`. För tester utan nät och kamera finns `TVATT_FAKE_FETCH_DIR` (sparade sidor) och `TVATT_FAKE_CAMERA` (en mapp med bilder som "kameran" visar).
- Tester: `cd backend && pip install -r requirements-dev.txt && python -m pytest`. Webbläsartesterna i `tests/e2e` hoppas över om Playwright saknas.
- Design och plan: `docs/specs/` och `docs/plans/`.

Typsnittet Poppins används under SIL Open Font License (se `frontend/public/fonts/OFL.txt`).

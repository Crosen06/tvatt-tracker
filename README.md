# Tvätt-tracker

En touchskärm i huset som håller koll på tvättkorgen. Charlie, Kiki och Magnus har var sin flik och trycker på sina plagg när de lägger dem i korgen. Appen föreslår vilka plagg som kan tvättas ihop, räknar ner medan maskinen går och säger till på skärmen när tvätten är klar.

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

## Uppdatera

```bash
cd ~/tvatt-tracker
./deploy/update.sh
```

## Säkerhetskopiera

Alla plagg, foton och inställningar ligger i `~/tvatt-data`. Stoppa appen en kort stund medan mappen kopieras, så att databasen inte ändras mitt i kopieringen:

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
| Skärmen släcks aldrig | `sudo raspi-config` → Display Options → Screen Blanking → på. |

## För utvecklare

- Backend: Python, [Starlette](https://www.starlette.io/) och SQLite i `backend/`. Starta med `scripts/dev.sh` (port 8000, data i `/tmp/tvatt-dev`). Lägg in exempelplagg med `python scripts/sample_data.py`.
- Gränssnitt: React 19 i `frontend/`, byggs med esbuild till `backend/app/static/` (som checkas in, så att Pi:n aldrig behöver Node). Bygg med `cd frontend && npm install && npm run build`.
- Tester: `cd backend && pip install -r requirements-dev.txt && python -m pytest`. Webbläsartesterna i `tests/e2e` hoppas över om Playwright saknas.
- Design och plan: `docs/specs/` och `docs/plans/`.

Typsnittet Poppins används under SIL Open Font License (se `frontend/public/fonts/OFL.txt`).

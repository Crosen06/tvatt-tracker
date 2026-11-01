# Tvätt-tracker – design

Datum: 2026-11-01 · Status: för granskning

## 1. Syfte

En uppkopplad touchskärm i huset (Raspberry Pi 4 + officiella 7"-skärmen, 800×480) som håller koll på vad som ligger i tvättkorgen för hushållets tre personer – **Charlie, Kiki och Magnus** – räknar ut vilka plagg som kan tvättas ihop, och säger till på skärmen när en tvätt är klar.

**Lyckat resultat:**
- Att lägga ett plagg i korgen tar två tryck på skärmen (egen flik → plagget).
- Att lägga in ett nytt plagg tar under en minut med mobilen (foto + taggar).
- Appen ger begripliga tvättförslag ("Mörkt 40° · 800 varv · 7 plagg") som inte förstör kläder.
- När maskinen är klar syns det tydligt på skärmen, även efter en omstart av Pi:n.
- UI:t känns snabbt (inga märkbara laddtider) och modernt.

## 2. Avgränsningar

- En tvättmaskin, en gemensam tvättkorg.
- Ingen inloggning: appen nås bara på hemnätet. Man väljer person med flikar.
- Notiser endast på skärmen (inget ljud, ingen push till mobil i version 1).
- Torktumlare: bara en tagg ("tål torktumlare") som visas i förslagen, ingen egen timer.
- Gränssnitt på svenska; kod, kommentarer och commit-meddelanden på engelska.

## 3. Arkitektur

```
 Mobiler (wifi)  ─┐
                  ├─ HTTP ─►  FastAPI (Python, uvicorn)  ──►  SQLite (data/tvatt.db)
 Pi-skärmen       │           ├─ REST-API  /api/...               foton (data/photos/)
 (Chromium kiosk)─┘           ├─ SSE      /api/events  (live-uppdatering)
                              └─ statiska filer: byggt Svelte-gränssnitt
```

- **Backend:** Python 3 + FastAPI + uvicorn, SQLite via standardbibliotekets `sqlite3` (WAL-läge). Pillow för miniatyrbilder. Körs som systemd-tjänst på port 80 (`AmbientCapabilities=CAP_NET_BIND_SERVICE`, ej root).
- **Frontend:** Svelte 5 + Vite, en enda SPA. Byggs i förväg och checkas in i repot (`backend/app/static/`), så Pi:n behöver aldrig Node.
- **Live-uppdatering:** servern skickar `changed`-händelser över Server-Sent Events när något ändras; klienterna hämtar om berörd data. Lägger någon till ett plagg från mobilen syns det direkt på skärmen.
- **Kiosk:** Chromium startar i helskärm mot `http://localhost/?kiosk=1` vid inloggning (labwc-autostart på Pi OS med Wayland). Skärmsläckning efter inaktivitet, väcks vid tryck.
- **Åtkomst från mobil:** installationsskriptet sätter värdnamnet till `tvatt`, så appen nås på `http://tvatt.local`.
- **Data utanför koden:** databas och foton ligger i `~/tvatt-data/`, så `git pull` aldrig rör användardata.

## 4. Datamodell

| Tabell | Fält |
|---|---|
| `person` | id, namn, färg (hex), ordning |
| `garment` (plagg) | id, person_id, namn, foto, max_temp, färggrupp, max_centrifug, skötsel, tål_tork, i_korgen, i_korgen_sedan, arkiverad, skapad |
| `program` (tvättprogram) | id, namn, längd_min, temp, skötsel, ordning |
| `wash` (tvätt) | id, program_id, namn_snapshot, längd_min, startad, klar_tid, status (`running`/`done`/`cancelled`), kvitterad |
| `wash_item` | wash_id, garment_id |
| `setting` | nyckel, värde (t.ex. `split_hot` = 1) |

**Taggvärden:**
- `max_temp`: 20 (kallt), 30, 40, 50, 60, 90
- `färggrupp`: `white` (vitt), `light` (ljust), `dark` (mörkt), `colored` (kulört, t.ex. rött)
- `max_centrifug`: 0 (ingen), 400, 600, 800, 1000, 1200, 1400
- `skötsel`: `normal` (bomull), `synthetic` (syntet), `delicate` (fintvätt), `wool` (ull), `hand` (handtvätt)

Ett plagg som ingår i en pågående tvätt räknas som "i maskinen" och visas inte som valbart i korgen.

**Startdata:** de tre personerna, och tvättprogrammen Bomull 40° (180 min), Bomull 60° (200 min), Syntet 40° (120 min), Fintvätt 30° (60 min), Ull 30° (45 min), Snabbtvätt 30° (30 min). Längderna redigeras i appen så att de matchar er maskin.

## 5. Grupperingslogik (kärnan)

En ren Python-modul (`grouping.py`) utan databas- eller webbberoenden, så den kan testas isolerat.

**Regler för att två plagg får tvättas ihop:**
1. Samma färggrupp.
2. Kompatibel skötselklass: `normal` + `synthetic` → klass *standard*; `delicate`, `wool` och `hand` är var sin klass.
3. Temperaturband (om inställningen `split_hot` är på, standard): plagg med max_temp ≥ 60 bildar egen grupp, skild från plagg ≤ 50. Annars blandas de.

**En grupps tvättparametrar:**
- Temperatur = lägsta `max_temp` i gruppen. Centrifug = lägsta `max_centrifug`.
- Skötsel = den skonsammaste: om någon är `synthetic` blir standard-gruppen `synthetic`.
- Föreslaget program = det program vars skötsel matchar och vars temperatur är närmast under eller lika med gruppens temperatur; finns inget matchande visas förslaget utan program och användaren väljer.
- Visar om alla plagg tål torktumlare, annars vilka som inte gör det.

**Två lägen:**
- **Förslag:** alla plagg i korgen grupperas; grupperna sorteras efter antal plagg (störst först).
- **Eget val:** användaren markerar ett eller flera plagg. Appen visar (a) vilka övriga plagg i korgen som passar med valet, och (b) om valda plagg krockar, en kort anledning ("Vitt + mörkt", "Ull kräver eget program").

## 6. Gränssnitt

### Skärmen (800×480, liggande, `?kiosk=1`)
- **Toppfält:** klocka, flikar `Charlie · Kiki · Magnus · Tvätta`, och en pågående tvätt som nedräkning ("Mörkt 40° · 42 min kvar").
- **Personflik:** rutnät med stora fotokort (minst 72 px tryckytor). Tryck = lägg i/ta ur korgen, med tydlig markering och liten animation. Filter "Alla / I korgen".
- **Tvätta-fliken:** förslagslista som kort (färggrupp, temp, centrifug, antal plagg, miniatyrer, vems plagg). Tryck på ett kort → välj program → **Starta**. Knapp för "Eget val".
- **Klar-notis:** helskärmsöverlägg "Tvätten är klar!" med lista på plaggen. Knappen **Tömt maskinen** avslutar tvätten och tar ut plaggen ur korgen. Överlägget ligger kvar tills någon trycker.
- Ingen textinmatning krävs på skärmen i vardagen.

### Mobilen (samma app, responsiv)
- **Lägg till plagg:** välj person → fota (`<input type="file" accept="image/*" capture="environment">`) → namn och taggar som stora knappval → Spara. Bilden förminskas i mobilen (max 1200 px, JPEG) innan uppladdning.
- **Plagg:** lista per person, redigera taggar, byt foto, arkivera.
- **Program:** lägg till/ändra tvättprogram och längder.
- **Inställningar:** personer (namn, färg), `split_hot`.
- Hela korgen och Tvätta-fliken fungerar också i mobilen.

### Visuell stil
Mörkt, lugnt tema som passar en skärm som alltid är på; en accentfärg per person; tydlig typografi läsbar på avstånd. Färggrupperna har egna färgkoder i kort och märken.

## 7. API (översikt)

- `GET/POST /api/people`, `PATCH /api/people/{id}`
- `GET /api/garments?person_id=`, `POST /api/garments` (multipart med foto), `PATCH /api/garments/{id}`, `POST /api/garments/{id}/photo`, `DELETE /api/garments/{id}` (arkiverar)
- `POST /api/garments/{id}/basket` (body `{in_basket: bool}`)
- `GET /api/suggestions`, `POST /api/suggestions/check` (body: valda plagg-id)
- `GET/POST /api/programs`, `PATCH/DELETE /api/programs/{id}`
- `GET /api/washes/current`, `POST /api/washes` (program + plagg), `POST /api/washes/{id}/finish`, `POST /api/washes/{id}/cancel`
- `GET/PATCH /api/settings`
- `GET /api/events` (SSE)
- `GET /photos/{fil}` och `/photos/thumb/{fil}`

## 8. Felhantering

- Tappad kontakt med servern: liten banner "Ingen kontakt – försöker igen", SSE återansluter automatiskt.
- Timern bygger på `klar_tid` i databasen, inte på en timer i webbläsaren, så den överlever omstart av Pi, server och webbläsare.
- Validering i API:t av alla taggvärden; begripliga felmeddelanden på svenska i UI:t.
- Uppladdning som misslyckas: plagget sparas inte halvvägs; användaren kan försöka igen utan att fylla i taggarna på nytt.
- Bara en tvätt kan vara igång åt gången (409 om man försöker starta en till).

## 9. Installation och drift

- `git clone` + `./install.sh` på Pi:n: skapar venv och installerar Python-paket, skapar `~/tvatt-data`, installerar systemd-tjänsten, sätter värdnamn `tvatt`, konfigurerar Chromium-kiosk i autostart och skärmsläckning.
- `./update.sh`: `git pull` + omstart av tjänsten.
- README på svenska med steg-för-steg, felsökning och hur man öppnar appen från mobilen.

## 10. Test

- **Enhetstester (pytest)** för grupperingslogiken: färg, skötsel, temperaturband, lägsta temp/centrifug, programförslag, eget val med krockar.
- **API-tester (pytest + FastAPI TestClient)** mot en temporär databas: plagg, korg, starta/avsluta tvätt, 409 vid dubbel tvätt.
- **UI-kontroll** med Playwright: skärmdumpar i 800×480 (kiosk) och 390×844 (mobil), klickflöde lägg i korg → starta tvätt → klar-notis (med kort programlängd).
- Den färdiga leveransen granskas av en separat granskare innan den lämnas över.

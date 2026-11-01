# Skafferiet (Kök) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Kök section (pantry, shopping list, recipes with suggestions, ICA import/search, barcode scanning) to the existing Tvätt-tracker app.

**Architecture:** Same Starlette server, same SQLite file and same React SPA. Pure logic lives in `backend/app/kitchen/` (no web imports), HTTP in `backend/app/routers/kitchen_*.py`, UI in `frontend/src/kitchen/`. External HTTP uses stdlib `urllib` through one module so tests can replace it; the webcam is read server-side with OpenCV in a background thread.

**Tech Stack:** Python 3.11+, Starlette, Pydantic 2, sqlite3, Pillow, opencv-python-headless ≥4.8 (`cv2.barcode`), React 19 + esbuild (built into `backend/app/static/`), pytest, Playwright.

**Spec:** `docs/specs/2026-11-01-skafferiet-design.md`

## Global Constraints

- UI text Swedish; code, comments, commit messages English.
- Categories, in order: Kyl, Frys, Skafferi, Frukt & grönt, Bröd, Kryddor, Dryck, Hushåll.
- Item status values: `in_stock`, `low`, `out` (UI: Finns, Snart slut, Slut).
- External fetch: timeout 10 s (Open Food Facts 5 s), max 3 MB, User-Agent `Tvatt-tracker-Kok/1.0 (+https://github.com/Crosen06/tvatt-tracker)`, only http/https, refuse localhost/private/link-local/loopback addresses.
- Scanner: 640×480, debounce 3 s per code, idle stop after 120 s without heartbeat, client heartbeat every 30 s, camera index from `TVATT_CAMERA` (default 0).
- ICA search URL `https://www.ica.se/recept/?q=<urlencoded>`, max 20 results; preview cache 50 entries / 30 min; client previews max 4 concurrently.
- Ofta köpta: max 24, ordered by `buy_count` desc then name.
- Error bodies `{"detail": "<svensk text>"}` via existing `HTTPException` handler. Non-integer ids → 422 (never 500). Whitespace-only names → 422.
- SSE topics added: `items`, `shopping`, `recipes`, `scan`.
- Kiosk tap targets ≥ 72 px (existing `--tap`). Must fit 800×480.
- No new Python runtime dependency except `opencv-python-headless>=4.8`; no new npm dependency.

## Review Focus

1. Odd ingredient lines (`"1 1/2 dl mjölk"`, `"Salt"`, `"2 st ägg (ca 120 g)"`, `"Till servering:"`, `""`, `"½ kruka basilika"`) must never raise and must yield sensible names → `test_parse_line_odd_inputs` (Task 4).
2. Marking an item out when it is already on the list, or twice, must not duplicate the entry; Ångra must restore the old status and remove only the entry it created → `test_out_twice_no_duplicate`, `test_undo_restores_and_removes_auto_entry` (Task 2).
3. Import of a page without a recipe, a duplicate URL, a recipe split in HowToSections, and `recipeYield` given as `"4 portioner"` or `["4", "4 portioner"]` → `test_import_variants` (Task 5) and `test_import_duplicate_returns_existing` (Task 6).
4. Camera disappearing mid-run (source returns `None` repeatedly) must stop the scanner with an error state that a new `start()` clears; concurrent `start()` calls create one thread → `test_source_failure_sets_error`, `test_start_is_idempotent` (Task 9).
5. Archiving an item that recipes link to and that is on the list: recipe lines become unknown (and are rematched), the list entry is removed → `test_archive_item_unlinks_and_removes_entry` (Task 2).

---

## Etapp 1 – Varor, skafferi, inköpslista

### Task 1: Kitchen schema, seed data and settings

**Files:**
- Create: `backend/app/kitchen/__init__.py`, `backend/app/kitchen/schema.py`, `backend/app/kitchen/seed.py`
- Modify: `backend/app/db.py` (call `init_kitchen`), `backend/app/routers/settings.py`, `backend/app/models.py` (`SettingsPatch.auto_list`)
- Test: `backend/tests/kitchen/test_schema.py`, extend `backend/tests/test_meta_api.py`

**Interfaces:**
- Produces: `KITCHEN_SCHEMA: str`; `init_kitchen(conn) -> None` (creates tables per spec §4, seeds items only if `item` is empty, seeds `ingredient_map` ignore rows, `INSERT OR IGNORE` setting `auto_list=1`); `CATEGORIES: list[str]`; `STATUSES = ("in_stock","low","out")`; `SEED_ITEMS: list[tuple[name, category, staple, counted, match_words]]` (~60); `SEED_IGNORE = ["vatten","kallt vatten","ljummet vatten","kokande vatten"]`. Settings JSON gains `"auto_list": bool`.

- [ ] Write tests: `test_seed_items_once` (init twice → same count, ≥55 items, all `out`), `test_seed_categories_valid`, `test_staples_seeded` (Salt, Svartpeppar with `"peppar"` in match_words, Matolja, Olivolja, Vetemjöl, Strösocker are staples), `test_ignore_map_seeded`; `test_settings_auto_list_roundtrip` (default true, PATCH false → false).
- [ ] Run, see them fail.
- [ ] Implement. `item.name` unique case-insensitively among non-archived (`CREATE UNIQUE INDEX ... ON item(name COLLATE NOCASE) WHERE archived=0`).
- [ ] Run `python -m pytest -q`, all pass. Commit `feat(kitchen): schema, seed items and auto_list setting`.

### Task 2: Item and shopping repository + API

**Files:**
- Create: `backend/app/kitchen/repo.py`, `backend/app/routers/kitchen_items.py`
- Modify: `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/kitchen/test_items_api.py`

**Interfaces:**
- Produces (repo): `item_json(row) -> dict` (`id,name,category,status,count,staple,counted,match_words:list[str],buy_count,on_list:bool`); `fetch_item(conn, id) -> Row` (404 "Varan finns inte."); `set_status(conn, item_id, status, count=None) -> int|None` returns id of auto-created list entry (only when going to `out` from not-`out`, `auto_list` on, not already on list); `add_to_list(conn, *, item_id=None, text=None, note=None) -> int|None` (None when item already on list; increments `buy_count` when created for an item); `unpack(conn, entry_ids) -> None`; `archive_item(conn, id)` (removes list entry, sets linked `recipe_ingredient.item_id=NULL`, deletes `ingredient_map` rows pointing at it, then calls `rematch_unknown` — stubbed as no-op until Task 4 replaces it).
- Produces (API, spec §10): `GET/POST /api/items`, `PATCH/DELETE /api/items/{id:int}`, `GET/POST /api/shopping`, `DELETE /api/shopping/{id:int}`, `POST /api/shopping/unpack`. PATCH response: `{"item": item_json, "list_entry_id": int|null, "previous": {"status", "count"}}` so the UI can undo. `GET /api/shopping` → `{"entries":[{id,item_id,text,note,added_at,category}], "frequent":[item_json]}`. `POST /api/shopping` with existing item → 200 `{"entry": null, "already": true}`, new → 201 `{"entry": {...}}`.
- Models: `ItemIn(name 1–40 stripped non-blank, category Literal, staple=False, counted=False, match_words: list[str]=[] , status="out", count:int|None)`, `ItemPatch` (all optional), `ShoppingIn(item_id|text, note≤60)` exactly one of item_id/text, `UnpackIn(entry_ids: list[int])`.

- [ ] Write tests: `test_create_item_and_list`, `test_blank_name_rejected` ("   " → 422), `test_duplicate_name_409` ("mjölk" vs seeded "Mjölk"), `test_set_out_adds_to_list`, `test_out_twice_no_duplicate`, `test_auto_list_off_does_not_add`, `test_undo_restores_and_removes_auto_entry` (PATCH out → entry id; client undo = PATCH previous status + DELETE entry; list empty, status restored), `test_counted_item_count_zero_is_out` (count 0 → status out + list entry; count 2 → in_stock), `test_add_to_list_increments_buy_count_and_frequent_order`, `test_shopping_text_entry`, `test_unpack_sets_in_stock_and_increments_count` (counted item count 1 → 2; text entry removed; unselected entries stay), `test_archive_item_unlinks_and_removes_entry` (recipe link part asserted in Task 6), `test_non_int_id_422`, `test_events_published` (monkeypatch bus, PATCH publishes `items` and `shopping`).
- [ ] Run, fail. Implement. Register routes in `main.py`. Run all tests, pass. Commit `feat(kitchen): items and shopping list API`.

### Task 3: Kök UI – switcher, pantry, shopping, keyboard, phone item admin

**Files:**
- Create: `frontend/src/kitchen/{labels.js, actions.js, Pantry.jsx, ItemTile.jsx, ItemSheet.jsx, NewItemSheet.jsx, Shopping.jsx, UnpackSheet.jsx, Keyboard.jsx, KioskInput.jsx, KitchenTabs.jsx, kitchen.css}`, `frontend/src/kitchen/admin/{ItemList.jsx, ItemEdit.jsx}`
- Modify: `frontend/src/App.jsx`, `frontend/src/components/TopBar.jsx`, `frontend/src/lib/router.js`, `frontend/src/lib/store.js`, `frontend/src/admin/{AdminRoutes.jsx, AdminHome.jsx, Settings.jsx}`, `frontend/src/main.jsx` (import kitchen.css), rebuilt `backend/app/static/*`
- Test: `backend/tests/e2e/test_kitchen_ui.py`

**Interfaces:**
- Consumes: Task 2 API.
- Produces: routes `#/kok/skafferi`, `#/kok/handla`, `#/kok/recept`, `#/kok/recept/{id}`, `#/kok/ica`, `#/admin/varor`, `#/admin/varor/{id}`, `#/admin/recept`, `#/admin/recept/ny`, `#/admin/recept/import`, `#/admin/recept/{id}`; `section(path) -> "wash"|"kitchen"`; `lastPath` memory per section in `router.js` (`switchSection()`); store keys `items`, `shopping`, `recipes` with loaders and TOPICS `items→[items, shopping, recipes]`, `shopping→[shopping, items]`, `recipes→[recipes]`; `toast(message, kind, action?: {label, run})`; `actions.setStatus(item, status, count?)` (optimistic, toasts "X lades på inköpslistan" with Ångra when `list_entry_id`); `actions.addToList(...)`; `<KioskInput value onChange placeholder layout="text"|"numeric" />` showing `<Keyboard>` (Swedish QWERTY rows `qwertyuiopå`, `asdfghjklöä`, `zxcvbnm`, 123-layer, ⌫, mellanslag, Klar) only when `isKiosk`, with `inputMode="none"`.
- UI per spec §9: switcher "Tvätt | Kök" at left of top bar (wash chip and clock stay; Skanna button placeholder hidden until Task 10); pantry grouped by category with filter Alla/Hemma/Snart slut/Slut; ItemSheet with Finns/Snart slut/Slut, −/+ for counted, På inköpslistan; NewItemSheet (name via KioskInput + category); Shopping two-column with ✕, Ofta köpta grid (on-list highlighted, tap again removes), Annat…, Packa upp sheet; phone admin Varor list/edit (name, category, staple, counted, synonyms, barcodes list placeholder until Task 10, Arkivera); Settings toggle "Lägg på inköpslistan när något tar slut".

- [ ] Write e2e tests (kiosk 800×480 unless noted): `test_switch_sections_keeps_wash_chip` (start wash via API, switch to Kök, chip visible; done overlay shows on Kök page), `test_mark_out_goes_to_list_and_undo`, `test_frequent_and_unpack`, `test_keyboard_adds_text_entry` (type "tvättmedel" with on-screen keys incl. "ä"), `test_kitchen_fits_kiosk` (no horizontal scroll on the three tabs, screenshots), `test_phone_item_edit` (390×844, rename item, mark staple).
- [ ] Run, fail. Implement. Build: `cd frontend && node build.mjs`. Run `python -m pytest -q`, all pass; look at screenshots in `tests/e2e/screens/`. Commit `feat(kitchen): Kök section with pantry, shopping list and on-screen keyboard`. Push.

## Etapp 2 – Recept

### Task 4: Ingredient parsing and matching

**Files:**
- Create: `backend/app/kitchen/ingredients.py`
- Modify: `backend/app/kitchen/repo.py` (real `rematch_unknown`)
- Test: `backend/tests/kitchen/test_ingredients.py`

**Interfaces:**
- Produces: `normalize(s: str) -> str`; `@dataclass ParsedLine(text: str, name: str, optional: bool)`; `parse_line(line: str) -> ParsedLine | None` (None for headings/blank); `@dataclass ItemRef(id: int, name: str, match_words: list[str])`; `match(name: str, items: list[ItemRef], mapping: dict[str, int|None]) -> tuple[int|None, bool]` → (item_id, ignored); repo `rematch_unknown(conn) -> None` and `link_ingredients(conn, recipe_id) -> None`.
- Rules exactly as spec §5 (units list, optional markers, inflection endings `ar er or n en et na arna erna orna`, compound suffix ≥4 chars, multi-word phrase, longest name wins).

- [ ] Tests: `test_parse_amounts_units` (`"2 dl vispgrädde (gärna laktosfri)"`→`vispgrädde`, not optional — "gärna" inside removed parentheses doesn't count; `"1 gul lök, finhackad"`→`gul lök`; `"400 g krossade tomater"`→`krossade tomater`; `"2–3 klyftor vitlök"`→`vitlök`; `"ca 1/2 tsk salt"`→`salt`), `test_parse_optional` (`"salt och peppar efter smak"` optional; `"färsk koriander till servering"` optional), `test_parse_line_odd_inputs` (Review Focus 1), `test_match_exact_and_synonym` (`peppar`→Svartpeppar), `test_match_inflection` (`tomater`→Tomat, `lökar`→Lök), `test_match_compound` (`vispgrädde`→Grädde, `"gul lök"`→Lök), `test_match_phrase_longest_wins` (`krossade tomater` with items Tomat and Krossade tomater → Krossade tomater), `test_match_mapping_first` (mapping overrides; mapping None → ignored), `test_short_names_no_compound` (`"is"` item must not match `"ris"`).
- [ ] Fail → implement → pass. Commit `feat(kitchen): ingredient parsing and matching`.

### Task 5: Recipe import (JSON-LD) and ICA search parsing

**Files:**
- Create: `backend/app/kitchen/fetch.py`, `backend/app/kitchen/recipe_import.py`, `backend/app/kitchen/ica.py`, fixtures `backend/tests/kitchen/fixtures/{ica_recipe.html, graph_recipe.html, sections_recipe.html, no_recipe.html, ica_search_itemlist.html, ica_search_next.html, ica_search_links.html}`
- Test: `backend/tests/kitchen/test_recipe_import.py`, `backend/tests/kitchen/test_ica.py`, `backend/tests/kitchen/test_fetch.py`

**Interfaces:**
- Produces: `class FetchError(Exception)` (Swedish `str`); `fetch.get(url: str, *, timeout: float = 10, max_bytes: int = 3_000_000) -> bytes`; `fetch.check_url(url) -> None`; `@dataclass ImportedRecipe(title, servings: int|None, minutes: int|None, ingredients: list[str], steps: list[str], image_url: str|None, source_url: str)`; `parse_recipe_html(html: str, url: str) -> ImportedRecipe | None`; `parse_iso_duration(s) -> int|None`; `import_url(url) -> ImportedRecipe` (raises `FetchError`, `NoRecipe`); `ica.search_url(q) -> str`; `ica.parse_search(html: str) -> list[{"url","title","image"}]`; `ica.search(q) -> list`; `ica.preview(url) -> ImportedRecipe` using `PreviewCache(maxsize=50, ttl=1800, clock=time.monotonic)`.
- Fixtures are hand-made imitations of the schema.org format (comment at top of each says so).

- [ ] Tests: `test_import_variants` (Review Focus 3: list-wrapped, `@graph`, HowToSection steps flattened, yield string/list → 4, `PT1H30M`→90, image as str/list/ImageObject, entities like `&amp;` unescaped), `test_no_recipe_returns_none`, `test_check_url_rejects` (`ftp://x`, `http://localhost/`, `http://192.168.1.5/`, `http://10.0.0.1`, `http://[::1]/`), `test_get_enforces_max_bytes` (local `http.server` in a thread serving 4 MB → FetchError; **`check_url` bypass via monkeypatch for this local test**), `test_parse_search_itemlist`, `test_parse_search_next_data`, `test_parse_search_links` (relative links absolutised, dedup, max 20, non-recipe links like `/recept/kyckling/` category pages excluded — pattern requires `-<digits>/`), `test_preview_cache` (second call within ttl doesn't fetch; after ttl fetches).
- [ ] Fail → implement → pass. Commit `feat(kitchen): recipe import from JSON-LD and ICA search parsing`.

### Task 6: Recipes repository, suggestions and API

**Files:**
- Create: `backend/app/kitchen/suggest.py`, `backend/app/routers/kitchen_recipes.py`
- Modify: `backend/app/kitchen/repo.py`, `backend/app/models.py`, `backend/app/main.py`
- Test: `backend/tests/kitchen/test_suggest.py`, `backend/tests/kitchen/test_recipes_api.py`

**Interfaces:**
- Consumes: Tasks 2, 4, 5.
- Produces: `suggest.evaluate(ingredients: list[dict], items: dict[int, dict]) -> dict` → `{"have": int, "total": int, "missing": [{"id","name","item_id"}], "unknown": [{"id","name"}], "low_used": int}` (counts non-optional, non-ignored lines; staple or in_stock/low = have; archived/missing item id = unknown); `suggest.sort_key(recipe_row, ev) -> tuple` per spec §6 (missing+unknown asc, low_used desc, last_cooked asc with NULL first, title).
- API (spec §10): `GET /api/recipes` → list sorted by `sort_key`, each `{id,title,servings,minutes,source,photo/thumb urls,cooked_count,last_cooked,eval}`; `GET /api/recipes/{id}` adds `ingredients:[{id,text,name,item_id,optional,ignored,state:"have"|"missing"|"unknown"|"optional"}]`, `steps:[str]`, `source_url`; `POST /api/recipes` (multipart: title, servings, minutes, ingredients text, steps text, optional photo) → 201; `PATCH /api/recipes/{id}` (JSON same fields; replacing ingredients re-parses and relinks); `DELETE` archives; `POST /api/recipes/{id}/photo`; `PATCH /api/recipes/{id}/ingredients/{ing_id}` (`{"item_id": int}` or `{"ignored": true}`; writes `ingredient_map[name]`, then `rematch_unknown`); `POST /api/recipes/{id}/missing-to-list` → `{"added": n}` (note `"till <titel>"`); `POST /api/recipes/{id}/cooked` (`{"updates":[{"item_id","status"}]}` uses `repo.set_status`, increments cooked_count, sets last_cooked); `POST /api/recipes/import` (`{"url"}`; duplicate → 200 existing `{"id", "existing": true}`, new → 201; image saved with `save_photo`, failure ignored); `GET /api/ica/search?q=` (q 1–80 chars) → `{"results":[...]}`; `GET /api/ica/preview?url=` (must be `https://www.ica.se/recept/...`) → `{title, image, total, have, missing:[name], saved_id|null}`. FetchError → 502 with its message; NoRecipe → 422 "Hittade inget recept på sidan.". Blocking network/photo work runs in `run_in_threadpool`.

- [ ] Tests: `test_evaluate_counts` (staple counts as have; optional ignored; unknown separate), `test_sort_order`, `test_create_own_recipe_links_ingredients`, `test_recipe_detail_states`, `test_link_ingredient_updates_map_and_other_recipes` (two recipes with "purjolök" unknown; link one → both linked), `test_ignore_ingredient`, `test_missing_to_list` (item entries + text entries with note, no duplicates), `test_cooked_updates_status_and_count`, `test_import_creates_recipe` (monkeypatch `fetch.get` to return fixture), `test_import_duplicate_returns_existing`, `test_import_fetch_error_502`, `test_ica_search_and_preview` (monkeypatched), `test_ica_preview_rejects_other_hosts`, `test_archive_item_unlinks_and_removes_entry` (recipe part), `test_new_item_rematches_unknown` (create item "Purjolök" → recipe line now linked).
- [ ] Fail → implement → pass. Commit `feat(kitchen): recipes, suggestions, import and ICA API`.

### Task 7: Recipe UI (kiosk + phone)

**Files:**
- Create: `frontend/src/kitchen/{Recipes.jsx, RecipeCard.jsx, RecipeView.jsx, LinkIngredientSheet.jsx, CookedSheet.jsx, IcaSearch.jsx}`, `frontend/src/kitchen/admin/{RecipeList.jsx, RecipeEdit.jsx, RecipeImport.jsx}`
- Modify: `frontend/src/App.jsx`, `frontend/src/admin/{AdminRoutes.jsx, AdminHome.jsx}`, rebuilt static
- Test: extend `backend/tests/e2e/test_kitchen_ui.py`

**Interfaces:** Consumes Task 6 API. UI per spec §9 (Recept, Receptvy, Sök på ICA, phone Recept admin). IcaSearch chips = in-stock items from Kyl and Frukt & grönt first, then others, max 12, plus KioskInput; previews fetched with a 4-wide queue; offline/502 shows the API detail text.

- [ ] E2E tests: `test_recipe_suggestions_and_missing_to_list` (seed recipe via API; card shows "Saknar 1: …"; open, "Lägg saknade på listan"; Handla shows entry), `test_link_unknown_ingredient` (tap ? row, pick item, row becomes ✓), `test_cooked_marks_out`, `test_phone_create_and_import_recipe` (390×844; import uses server started with env `TVATT_FAKE_FETCH_DIR` pointing at fixtures — `fetch.get` reads `<dir>/<sha1(url)[:12]>.html` when that env var is set; test hook documented in `fetch.py`), `test_ica_search_ui` (same fake fetch: search page + preview pages, card shows "har X av Y", Spara → recipe appears).
- [ ] Fail → implement + build → pass. Commit `feat(kitchen): recipe pages, ICA search and phone recipe admin`. Push.

## Etapp 3 – Skanning

### Task 8: Barcodes and Open Food Facts

**Files:**
- Create: `backend/app/kitchen/products.py`
- Test: `backend/tests/kitchen/test_products.py`

**Interfaces:**
- Produces: `valid_gtin(code: str) -> bool` (EAN-8, UPC-A(12), EAN-13 checksums; 8-digit codes checked as EAN-8); `@dataclass Product(name: str, brand: str|None, quantity: str|None, category: str)`; `parse_off(data: dict) -> Product|None` (prefers `product_name_sv`, then `product_name`; name = "brand name quantity" deduplicated; status 0 → None); `guess_category(tags: list[str]) -> str` (spec §8 mapping, default Skafferi); `lookup(code) -> Product|None` raises `FetchError` (URL `https://world.openfoodfacts.org/api/v2/product/{code}.json?fields=product_name,product_name_sv,brands,quantity,categories_tags`, timeout 5).
- [ ] Tests: `test_valid_gtin` (valid: `4006381333931`, `96385074`, `036000291452`; each with last digit changed → invalid; letters, empty, 11 digits → invalid), `test_parse_off_names`, `test_parse_off_not_found`, `test_guess_category` (`en:dairies`→Kyl, `en:frozen-foods`→Frys, `en:breads`→Bröd, `en:beverages`→Dryck, `en:vegetables`→Frukt & grönt, `en:condiments`→Kryddor, `[]`→Skafferi), `test_lookup_uses_fetch` (monkeypatched).
- [ ] Fail → implement → pass. Commit `feat(kitchen): barcode validation and Open Food Facts lookup`.

### Task 9: Scanner

**Files:**
- Create: `backend/app/kitchen/scanner.py`, `backend/tests/kitchen/barcode_images.py` (EAN-13 renderer with numpy, quiet zone, module width 3 px, height 120 px, scaled into a 640×480 grey frame)
- Test: `backend/tests/kitchen/test_scanner.py`

**Interfaces:**
- Produces: `class CameraUnavailable(Exception)`; `decode(frame) -> list[str]` (gray conversion; supports both `detectAndDecodeWithType` and `detectAndDecode` return shapes; filters with `valid_gtin`); `class Scanner(source_factory, on_scan: Callable[[str], None], *, idle_seconds=120, debounce=3.0, clock=time.monotonic)` with `start() -> None` (idempotent; raises `CameraUnavailable` with Swedish message if cv2 missing or source fails to open), `heartbeat()`, `stop()`, `running: bool`, `error: str|None`, `last: dict|None` (`{"seq","code","at"}`), `latest_jpeg() -> bytes|None`; `default_source_factory()` (cv2.VideoCapture index `TVATT_CAMERA`, 640×480; if env `TVATT_FAKE_CAMERA` is a directory, cycles its PNG/JPG files instead — e2e hook). Frame source protocol: `read() -> ndarray|None`, `release()`. After 30 consecutive `None` reads the thread stops with `error = "Kameran slutade svara."`.
- [ ] Tests: `test_decode_generated_ean13`, `test_decode_blank_frame_empty`, `test_scan_debounce` (same code across frames → one callback within 3 s of fake clock; again after), `test_idle_stop` (fake clock past 120 s without heartbeat → stopped, source released), `test_start_is_idempotent` (two starts → one thread, one source open), `test_source_failure_sets_error` (then start clears error), `test_cv2_missing_raises` (monkeypatch import to fail), `test_latest_jpeg_available`.
- [ ] Fail → implement → pass. Commit `feat(kitchen): webcam barcode scanner`.

### Task 10: Scan + barcode API and scan UI

**Files:**
- Create: `backend/app/routers/kitchen_scan.py`, `frontend/src/kitchen/{ScanSheet.jsx, ScanResult.jsx, LinkBarcode.jsx, beep.js}`
- Modify: `backend/app/main.py` (`create_app(data_dir=None, scanner_factory=None)`; scanner stored on `app.state.scanner`, publishes `scan`; stopped on shutdown), `backend/app/models.py`, `frontend/src/components/TopBar.jsx` (Skanna, kiosk only), `frontend/src/kitchen/admin/ItemEdit.jsx` (barcodes list with remove), rebuilt static
- Test: `backend/tests/kitchen/test_scan_api.py`, extend `backend/tests/e2e/test_kitchen_ui.py`

**Interfaces:**
- API: `POST /api/scan/start` (503 detail "Ingen kamera hittades. Kontrollera att webbkameran sitter i." on `CameraUnavailable`; also acts as heartbeat) → `{"running": true}`; `POST /api/scan/stop`; `GET /api/scan/last` → `{"seq","code","at","error"}`; `GET /api/scan/stream` → `multipart/x-mixed-replace; boundary=frame`, ~10 fps, ends when scanner stops or client disconnects; `GET /api/barcodes/{code}` (invalid code → 422) → `{"code","item": item_json|null, "product": {...}|null, "lookup_failed": bool, "candidates": [item_json]}` (candidates: top 5 non-archived items whose name matches words of the product name via `ingredients.match`/substring); `POST /api/barcodes` (`{"code","item_id"}` or `{"code","new_item":{"name","category"}}`; upserts mapping, stores product_name) → item_json; `DELETE /api/barcodes/{code}`; items' `item_json` gains `barcodes: [code]` in `GET /api/items/{id}` only.
- UI per spec §8: ScanSheet full-screen with `<img src="/api/scan/stream">`, listens to SSE `scan` topic → GET last; known code card with In i skafferiet / På inköpslistan / Slut; unknown with OFF suggestion, candidates, Sök (KioskInput), Ny vara (prefilled name, guessed category); Skriv koden numeric keypad; heartbeat every 30 s; Klar stops.
- [ ] API tests (fake scanner factory): `test_scan_start_503_without_camera`, `test_scan_flow_publishes_and_last`, `test_barcode_unknown_with_product` (monkeypatched lookup), `test_barcode_lookup_failed`, `test_link_barcode_existing_and_new_item`, `test_barcode_invalid_422`, `test_stream_returns_jpeg_parts`.
- [ ] E2E (server env `TVATT_FAKE_CAMERA` dir with generated EAN-13 PNGs; first code pre-linked to "Mjölk" via API, second unknown with `TVATT_FAKE_FETCH_DIR` OFF JSON fixture): `test_scan_known_item_to_pantry`, `test_scan_unknown_new_item`, `test_manual_code_entry`.
- [ ] Fail → implement + build → pass. Commit `feat(kitchen): scan sheet, barcode linking and scan API`.

### Task 11: Install, check script, docs

**Files:**
- Modify: `backend/requirements.txt` (`opencv-python-headless>=4.8`), `deploy/tvatt.service` (`SupplementaryGroups=video`), `deploy/install.sh` (extract unit install into `deploy/install-service.sh` used by both), `deploy/update.sh` (re-render unit, `daemon-reload` only when changed), `README.md` (Kök-avsnitt), `claude/kontext.md` in the Project (status line + decisions)
- Create: `scripts/check_kitchen.py`, `deploy/install-service.sh`
- Test: extend `backend/tests/test_deploy.py`

**Interfaces:** `scripts/check_kitchen.py [--camera-seconds 15] [--base http://localhost]` prints `✓/✗ Kamera`, `✓/✗ Open Food Facts` (looks up `7310865004703`; ✓ when the API answers, whether or not the product is found, and prints the name if any), `✓/✗ ICA-sök` (q=kyckling, count), `✓/✗ ICA-import` (first hit: title + ingredient count); exit code 0 if all ✓ else 1. Camera check uses the running server's `/api/scan/*` when reachable, else `Scanner` directly.
- [ ] Tests: `test_update_reinstalls_changed_unit` (fake `sudo`, `systemctl`, `git`, venv pip on PATH; unit differs → copied + daemon-reload logged; same → not), `test_service_has_video_group`, `test_check_kitchen_offline` (all network monkeypatched to fail → exit 1, prints ✗ lines, no traceback).
- [ ] Fail → implement → pass. Full suite. Commit `feat(deploy): kitchen install changes, check script and README`. Push.

### Task 12: Final review

- [ ] Run whole suite twice (flaky check), inspect all screenshots in 800×480 and 390×844.
- [ ] Dispatch one fresh reviewer (most capable model) over the diff since `93e8b8d` with spec + plan; fix every Important finding with a test; push.
- [ ] Update `claude/kontext.md` status and decisions in the Project.

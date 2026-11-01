"""Browser checks of the Kök section (kiosk 800×480 and phone 390×844)."""

import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

from tests.e2e.test_ui import (  # noqa: E402,F401  (fixtures are used by name)
    KIOSK, PHONE, _finish_soon, _start_wash, add_garment, api, browser, new_page, server, shot,
)


FIX = Path(__file__).resolve().parents[1] / "kitchen" / "fixtures"
BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def kserver(tmp_path):
    """Like `server`, but with fake internet (TVATT_FAKE_FETCH_DIR) and a fake camera folder."""
    from tests.e2e.test_ui import _free_port

    fake, cam, data = tmp_path / "fake", tmp_path / "cam", tmp_path / "data"
    fake.mkdir()
    cam.mkdir()
    port = _free_port()
    env = {"TVATT_DATA": str(data), "PATH": "/usr/bin:/bin", "TVATT_FAKE_FETCH_DIR": str(fake), "TVATT_FAKE_CAMERA": str(cam)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory", "app.main:create_app", "--port", str(port)],
        cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(base + "/api/health")
            break
        except OSError:
            time.sleep(0.1)
    yield {"base": base, "db": data / "tvatt.db", "fake": fake, "cam": cam}
    proc.terminate()
    proc.wait(5)


def fake_page(srv, url, fixture):
    from app.kitchen.fetch import fake_name

    shutil.copy(FIX / fixture, srv["fake"] / f"{fake_name(url)}.html")


def post_form(base, path, fields):
    data = urllib.parse.urlencode(fields).encode()
    with urllib.request.urlopen(urllib.request.Request(base + path, data=data, method="POST")) as r:
        return __import__("json").load(r)


def add_recipe(base, title, ingredients, steps="Laga maten."):
    return post_form(base, "/api/recipes", {"title": title, "ingredients": ingredients, "steps": steps, "servings": "4"})


def item(base, name):
    return next(i for i in api(base, "GET", "/api/items") if i["name"] == name)


def set_item(base, name, **fields):
    return api(base, "PATCH", f"/api/items/{item(base, name)['id']}", fields)


def no_hscroll(pg):
    return pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_switch_sections_keeps_wash_chip(server, browser):
    base = server["base"]
    g = add_garment(base, "Svart hoodie", in_basket=True)
    _start_wash(base, [g["id"]])
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1")
    pg.get_by_role("button", name="Kök").click()
    pw.expect(pg.get_by_role("button", name="Skafferi")).to_be_visible()
    pw.expect(pg.locator(".wash-chip")).to_be_visible()
    pg.get_by_role("button", name="Handla").click()
    pg.get_by_role("button", name="Tvätt", exact=True).click()
    pw.expect(pg.get_by_role("button", name="Tvätta")).to_be_visible()
    pg.get_by_role("button", name="Kök").click()
    pw.expect(pg.get_by_role("heading", name="Inköpslista")).to_be_visible()  # remembers last kitchen page
    _finish_soon(server["db"])
    pg.reload()
    pw.expect(pg.get_by_role("heading", name="Tvätten är klar!")).to_be_visible(timeout=6000)
    assert errors == []


def test_mark_out_goes_to_list_and_undo(server, browser):
    base = server["base"]
    set_item(base, "Mjölk", status="in_stock")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("button", name="Mjölk, Finns").click()
    sheet = pg.locator(".sheet")
    shot(pg, "kiosk-item-sheet")
    sheet.get_by_role("button", name="Slut", exact=True).click()
    pw.expect(pg.get_by_text("Mjölk lades på inköpslistan")).to_be_visible()
    pg.get_by_role("button", name="Ångra").click()
    pw.expect(pg.get_by_role("button", name="Mjölk, Finns")).to_be_visible()
    time.sleep(0.3)
    assert item(base, "Mjölk")["status"] == "in_stock"
    assert api(base, "GET", "/api/shopping")["entries"] == []

    pg.get_by_role("button", name="Mjölk, Finns").click()
    pg.locator(".sheet").get_by_role("button", name="Slut", exact=True).click()
    pg.get_by_role("button", name="Handla").click()
    pw.expect(pg.locator(".shop-list")).to_contain_text("Mjölk")
    shot(pg, "kiosk-shopping")
    assert errors == []


def test_pantry_filter_and_counted(server, browser):
    base = server["base"]
    set_item(base, "Ägg", count=6)
    set_item(base, "Smör", status="low")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("tab", name="Hemma").click()
    pw.expect(pg.get_by_role("button", name="Ägg, 6 st")).to_be_visible()
    pw.expect(pg.get_by_role("button", name="Smör, Snart slut")).to_be_visible()
    pw.expect(pg.get_by_role("button", name="Mjölk, Slut")).to_have_count(0)
    pg.get_by_role("button", name="Ägg, 6 st").click()
    pg.get_by_role("button", name="Minska antal").click()
    pw.expect(pg.locator(".sheet")).to_contain_text("5 st")
    time.sleep(0.3)
    assert item(base, "Ägg")["count"] == 5
    shot(pg, "kiosk-pantry")
    assert no_hscroll(pg)
    assert errors == []


def test_frequent_and_unpack(server, browser):
    base = server["base"]
    e = api(base, "POST", "/api/shopping", {"item_id": item(base, "Kaffe")["id"]})["entry"]
    api(base, "DELETE", f"/api/shopping/{e['id']}")
    api(base, "POST", "/api/shopping", {"item_id": item(base, "Ägg")["id"]})
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/handla")
    freq = pg.locator(".frequent")
    pw.expect(freq.get_by_role("button", name="Ägg")).to_have_attribute("aria-pressed", "true")
    freq.get_by_role("button", name="Kaffe").click()
    pw.expect(pg.locator(".shop-list")).to_contain_text("Kaffe")
    pg.get_by_role("button", name="Packa upp").click()
    pw.expect(pg.locator(".sheet").get_by_role("checkbox")).to_have_count(2)
    pg.get_by_role("button", name="Det här köptes").click()
    pw.expect(pg.get_by_text("Listan är tom")).to_be_visible()
    time.sleep(0.3)
    assert item(base, "Kaffe")["status"] == "in_stock"
    assert item(base, "Ägg")["count"] == 1
    assert errors == []


def test_keyboard_adds_text_entry(server, browser):
    base = server["base"]
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/handla")
    pg.get_by_role("button", name="Annat…").click()
    kb = pg.locator(".osk")
    pw.expect(kb).to_be_visible()
    for ch in "äpplemos":
        kb.get_by_role("button", name=ch, exact=True).click()
    pw.expect(pg.locator(".sheet input")).to_have_value("äpplemos")
    shot(pg, "kiosk-keyboard")
    pg.get_by_role("button", name="Lägg till").click()
    pw.expect(pg.locator(".shop-list")).to_contain_text("Äpplemos")
    assert api(base, "GET", "/api/shopping")["entries"][0]["text"] == "Äpplemos"
    assert errors == []


def test_new_item_on_kiosk(server, browser):
    base = server["base"]
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("button", name="Ny vara").click()
    kb = pg.locator(".osk")
    for ch in "tahini":
        kb.get_by_role("button", name=ch, exact=True).click()
    pg.locator(".sheet").get_by_role("radio", name="Skafferi").click()
    pg.get_by_role("button", name="Spara vara").click()
    pw.expect(pg.get_by_role("button", name="Tahini, Finns")).to_be_visible()
    assert item(base, "Tahini")["category"] == "Skafferi"
    assert errors == []


def test_phone_item_edit(server, browser):
    base = server["base"]
    errors = []
    pg = new_page(browser, PHONE, errors)
    pg.goto(base + "/#/admin")
    pg.get_by_role("button", name="Varor").click()
    pg.get_by_role("button", name="Mjölk Slut", exact=True).click()
    pg.get_by_label("Namn", exact=True).fill("Mellanmjölk")
    pg.get_by_label("Basvara").check()
    pg.get_by_role("button", name="Spara").click()
    pw.expect(pg.get_by_text("Sparat.")).to_be_visible()
    shot(pg, "phone-item-edit")
    it = next(i for i in api(base, "GET", "/api/items") if i["id"] == item(base, "Mellanmjölk")["id"])
    assert it["staple"] is True
    pg.goto(base + "/#/kok/skafferi")
    pw.expect(pg.get_by_role("button", name="Mellanmjölk, Slut")).to_be_visible()
    assert no_hscroll(pg)
    assert errors == []


# ---------- recipes ----------

def test_recipe_suggestions_and_missing_to_list(server, browser):
    base = server["base"]
    set_item(base, "Pasta", status="in_stock")
    add_recipe(base, "Pasta med grädde", "400 g pasta\n2 dl vispgrädde")
    add_recipe(base, "Bara pasta", "400 g pasta\nsalt")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/recept")
    cards = pg.locator(".recipe-card")
    pw.expect(cards.first).to_contain_text("Bara pasta")
    pw.expect(cards.first).to_contain_text("Allt finns hemma")
    pw.expect(cards.nth(1)).to_contain_text("Saknar 1: vispgrädde")
    shot(pg, "kiosk-recipes")
    cards.nth(1).click()
    pw.expect(pg.get_by_role("heading", name="Pasta med grädde")).to_be_visible()
    shot(pg, "kiosk-recipe-view")
    pg.get_by_role("button", name="Lägg saknade på listan").click()
    pw.expect(pg.get_by_text("1 vara lades på inköpslistan")).to_be_visible()
    pg.get_by_role("button", name="Handla").click()
    pw.expect(pg.locator(".shop-list")).to_contain_text("Grädde")
    pw.expect(pg.locator(".shop-list")).to_contain_text("till Pasta med grädde")
    assert no_hscroll(pg)
    assert errors == []


def test_link_unknown_ingredient(server, browser):
    base = server["base"]
    r = add_recipe(base, "Halloumisallad", "1 st halloumi")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + f"/?kiosk=1#/kok/recept/{r['id']}")
    pg.get_by_role("button", name="1 st halloumi, okänd vara").click()
    kb = pg.locator(".osk")
    for ch in "ost":
        kb.get_by_role("button", name=ch, exact=True).click()
    shot(pg, "kiosk-link-ingredient")
    pg.locator(".sheet").get_by_role("button", name="Ost", exact=True).click()
    pw.expect(pg.get_by_role("button", name="1 st halloumi, saknas")).to_be_visible()
    d = api(base, "GET", f"/api/recipes/{r['id']}")
    assert d["ingredients"][0]["item_id"] == item(base, "Ost")["id"]
    assert errors == []


def test_cooked_marks_out(server, browser):
    base = server["base"]
    set_item(base, "Grädde", status="in_stock")
    r = add_recipe(base, "Gräddsås", "2 dl vispgrädde")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + f"/?kiosk=1#/kok/recept/{r['id']}")
    pg.get_by_role("button", name="Vi lagade den").click()
    row = pg.locator(".cooked-row", has_text="Grädde")
    row.get_by_role("radio", name="Slut", exact=True).click()
    pg.get_by_role("button", name="Klart").click()
    pw.expect(pg.get_by_text("Grädde lades på inköpslistan").or_(pg.get_by_text("Smaklig måltid"))).to_be_visible()
    time.sleep(0.3)
    assert item(base, "Grädde")["status"] == "out"
    assert api(base, "GET", f"/api/recipes/{r['id']}")["cooked_count"] == 1
    assert errors == []


def test_phone_create_and_import_recipe(kserver, browser):
    base = kserver["base"]
    url = "https://www.ica.se/recept/kramig-kycklinggryta-722668/"
    fake_page(kserver, url, "ica_recipe.html")
    errors = []
    pg = new_page(browser, PHONE, errors)
    pg.goto(base + "/#/admin")
    pg.get_by_role("button", name="Recept").click()
    pg.get_by_role("button", name="Nytt recept").click()
    pg.get_by_label("Titel").fill("Omelett")
    pg.get_by_label("Ingredienser").fill("3 ägg\n1 dl mjölk")
    pg.get_by_label("Gör så här").fill("Vispa.\nStek.")
    pg.get_by_role("button", name="Spara recept").click()
    pw.expect(pg.get_by_text("Receptet är sparat.")).to_be_visible()
    assert any(r["title"] == "Omelett" for r in api(base, "GET", "/api/recipes"))

    pg.goto(base + "/#/admin/recept")
    pg.get_by_role("button", name="Importera från länk").click()
    pg.get_by_label("Länk till receptet").fill(url)
    pg.get_by_role("button", name="Hämta recept").click()
    pw.expect(pg.get_by_label("Titel")).to_have_value("Krämig kycklinggryta med curry")
    shot(pg, "phone-recipe-imported")
    assert any(r["source"] == "ica" for r in api(base, "GET", "/api/recipes"))
    assert errors == []


def test_ica_search_ui(kserver, browser):
    base = kserver["base"]
    fake_page(kserver, "https://www.ica.se/recept/?q=kyckling", "ica_search_itemlist.html")
    fake_page(kserver, "https://www.ica.se/recept/kramig-kycklinggryta-722668/", "ica_recipe.html")
    fake_page(kserver, "https://www.ica.se/recept/kyckling-i-ugn-713399/", "sections_recipe.html")
    set_item(base, "Kyckling", status="in_stock")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/recept")
    pg.get_by_role("button", name="Sök på ICA").click()
    pg.get_by_role("button", name="Kyckling", exact=True).click()
    pg.get_by_role("button", name="Sök", exact=True).click()
    card = pg.locator(".ica-card", has_text="Krämig kycklinggryta")
    pw.expect(card).to_contain_text("har 1 av 6")
    shot(pg, "kiosk-ica")
    card.get_by_role("button", name="Spara").click()
    pw.expect(card.get_by_role("button", name="Öppna")).to_be_visible()
    assert any(r["source"] == "ica" for r in api(base, "GET", "/api/recipes"))
    assert errors == []


def test_ica_search_offline_message(kserver, browser):
    base = kserver["base"]
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/ica")
    pg.get_by_label("Sök recept").click()
    kb = pg.locator(".osk")
    for ch in "soppa":
        kb.get_by_role("button", name=ch, exact=True).click()
    pg.get_by_role("button", name="Sök", exact=True).click()
    pw.expect(pg.get_by_text("Kunde inte nå www.ica.se")).to_be_visible()
    assert errors == []


def test_link_ingredient_to_new_item(server, browser):
    base = server["base"]
    r = add_recipe(base, "Grillad halloumi", "1 st halloumi")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + f"/?kiosk=1#/kok/recept/{r['id']}")
    pg.get_by_role("button", name="1 st halloumi, okänd vara").click()
    pg.get_by_role("button", name="Ny vara ”Halloumi”").click()
    pw.expect(pg.get_by_role("button", name="1 st halloumi, saknas")).to_be_visible()
    assert item(base, "Halloumi")["status"] == "out"
    assert errors == []


# ---------- scanning ----------

CODE_A = "4006381333931"
CODE_B = "7310865004703"


def show_code(srv, code):
    import cv2

    from tests.kitchen.barcode_images import ean13_frame

    cv2.imwrite(str(srv["cam"] / f"{code}.png"), ean13_frame(code))


def test_scan_known_item_to_pantry(kserver, browser):
    base = kserver["base"]
    api(base, "POST", "/api/barcodes", {"code": CODE_A, "item_id": item(base, "Mjölk")["id"]})
    api(base, "POST", "/api/shopping", {"item_id": item(base, "Mjölk")["id"]})
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("button", name="Skanna").click()
    pw.expect(pg.get_by_text("Håll streckkoden mot kameran")).to_be_visible()
    show_code(kserver, CODE_A)
    card = pg.locator(".scan-result")
    pw.expect(card.get_by_role("heading", name="Mjölk")).to_be_visible(timeout=10000)
    shot(pg, "kiosk-scan-known")
    card.get_by_role("button", name="In i skafferiet").click()
    pw.expect(pg.get_by_text("Mjölk finns nu i skafferiet")).to_be_visible()
    time.sleep(0.3)
    assert item(base, "Mjölk")["status"] == "in_stock"
    assert api(base, "GET", "/api/shopping")["entries"] == []  # bought, so off the list
    pg.get_by_role("button", name="Klar", exact=True).click()
    pw.expect(pg.locator(".scan")).to_have_count(0)
    for _ in range(50):  # the camera is stopped right after the sheet closes
        if api(base, "GET", "/api/scan/last")["running"] is False:
            break
        time.sleep(0.1)
    assert api(base, "GET", "/api/scan/last")["running"] is False
    assert errors == []


def test_scan_unknown_new_item(kserver, browser):
    import json as _json

    from app.kitchen.fetch import fake_name
    from app.kitchen.products import OFF_URL

    base = kserver["base"]
    (kserver["fake"] / f"{fake_name(OFF_URL.format(code=CODE_B))}.json").write_text(_json.dumps(
        {"status": 1, "product": {"product_name": "Havredryck", "brands": "Oatly", "quantity": "1 l", "categories_tags": ["en:beverages"]}}
    ))
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("button", name="Skanna").click()
    show_code(kserver, CODE_B)
    card = pg.locator(".scan-result")
    pw.expect(card).to_contain_text("Oatly Havredryck 1 l", timeout=10000)
    shot(pg, "kiosk-scan-unknown")
    card.get_by_role("button", name="Ny vara").click()
    pw.expect(pg.get_by_label("Namn på varan")).to_have_value("Havredryck")
    pw.expect(pg.get_by_role("radio", name="Dryck")).to_have_attribute("aria-checked", "true")
    pg.get_by_role("button", name="Spara vara").click()
    pw.expect(card.get_by_role("heading", name="Havredryck")).to_be_visible()
    card.get_by_role("button", name="På inköpslistan").click()
    pw.expect(pg.get_by_text("Havredryck lades på inköpslistan")).to_be_visible()
    hv = item(base, "Havredryck")
    assert hv["on_list"] is True and hv["category"] == "Dryck"
    assert api(base, "GET", f"/api/barcodes/{CODE_B}")["item"]["id"] == hv["id"]
    assert errors == []


def test_manual_code_entry(kserver, browser):
    base = kserver["base"]
    api(base, "POST", "/api/barcodes", {"code": CODE_A, "item_id": item(base, "Smör")["id"]})
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/kok/handla")
    pg.get_by_role("button", name="Skanna").click()
    pg.get_by_role("button", name="Skriv koden").click()
    pad = pg.locator(".osk-numeric")
    for ch in CODE_A:
        pad.get_by_role("button", name=ch, exact=True).click()
    pad.get_by_role("button", name="Klar").click()
    card = pg.locator(".scan-result")
    pw.expect(card.get_by_role("heading", name="Smör")).to_be_visible()
    card.get_by_role("button", name="Slut", exact=True).click()
    pw.expect(pg.get_by_text("Smör lades på inköpslistan")).to_be_visible()
    assert errors == []


def test_scan_without_camera_shows_error(server, browser):
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(server["base"] + "/?kiosk=1#/kok/skafferi")
    pg.get_by_role("button", name="Skanna").click()
    pw.expect(pg.get_by_text("Ingen kamera hittades")).to_be_visible(timeout=10000)
    pw.expect(pg.get_by_role("button", name="Försök igen")).to_be_visible()
    pw.expect(pg.get_by_role("button", name="Skriv koden")).to_be_visible()
    shot(pg, "kiosk-scan-nocamera")
    assert errors == []


def test_no_scan_button_on_phone(server, browser):
    errors = []
    pg = new_page(browser, PHONE, errors)
    pg.goto(server["base"] + "/#/kok/skafferi")
    pw.expect(pg.get_by_role("button", name="Skafferi")).to_be_visible()
    pw.expect(pg.get_by_role("button", name="Skanna")).to_have_count(0)
    assert errors == []

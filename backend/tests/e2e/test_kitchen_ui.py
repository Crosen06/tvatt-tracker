"""Browser checks of the Kök section (kiosk 800×480 and phone 390×844)."""

import time

import pytest

pw = pytest.importorskip("playwright.sync_api")

from tests.e2e.test_ui import (  # noqa: E402,F401  (fixtures are used by name)
    KIOSK, PHONE, _finish_soon, _start_wash, add_garment, api, browser, new_page, server, shot,
)


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

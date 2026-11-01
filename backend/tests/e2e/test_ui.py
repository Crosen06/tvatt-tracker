"""Browser checks of the real app (kiosk 800×480 and phone 390×844).

Skipped automatically when Playwright or its Chromium is unavailable.
"""

import io
import json
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")

BACKEND = Path(__file__).resolve().parents[2]
SCREENS = Path(__file__).parent / "screens"
KIOSK = {"width": 800, "height": 480}
PHONE = {"width": 390, "height": 844}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    port = _free_port()
    data = tmp_path / "data"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "--factory", "app.main:create_app", "--port", str(port)],
        cwd=BACKEND,
        env={"TVATT_DATA": str(data), "PATH": "/usr/bin:/bin"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(base + "/api/health")
            break
        except OSError:
            time.sleep(0.1)
    yield {"base": base, "db": data / "tvatt.db"}
    proc.terminate()
    proc.wait(5)


@pytest.fixture
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # pragma: no cover
            pytest.skip(f"Chromium unavailable: {e}")
        yield b
        b.close()


def new_page(browser, viewport, errors):
    pg = browser.new_page(viewport=viewport)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    return pg


def shot(pg, name):
    SCREENS.mkdir(exist_ok=True)
    pg.screenshot(path=str(SCREENS / f"{name}.png"))


def api(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, method=method, data=data)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.load(r) if r.status != 204 else None


def add_garment(base, name, person_id=1, color="dark", temp=40, in_basket=False):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (40, 40, 60)).save(buf, "JPEG")
    boundary = "xyz"
    fields = {
        "person_id": person_id, "name": name, "max_temp": temp, "color": color,
        "max_spin": 1200, "care": "normal", "tumble_dry": "true",
    }
    body = b"".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, v in fields.items()
    )
    body += (
        f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="p.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    body += buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(base + "/api/garments", data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as r:
        g = json.load(r)
    if in_basket:
        api(base, "POST", f"/api/garments/{g['id']}/basket", {"in_basket": True})
    return g


def test_kiosk_empty_states(server, browser):
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(server["base"] + "/?kiosk=1")
    pw.expect(pg.get_by_text("Charlie har inga plagg än")).to_be_visible()
    pw.expect(pg.get_by_text("tvatt.local")).to_be_visible()
    shot(pg, "kiosk-empty-person")
    pg.get_by_role("button", name="Tvätta").click()
    pw.expect(pg.get_by_text("Tvättkorgen är tom")).to_be_visible()
    shot(pg, "kiosk-empty-wash")
    assert errors == []


def test_toggle_basket_kiosk(server, browser):
    add_garment(server["base"], "Svart hoodie")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(server["base"] + "/?kiosk=1")
    card = pg.get_by_role("button", name="Svart hoodie, Inte i tvättkorgen")
    box = card.bounding_box()
    assert box["width"] >= 72 and box["height"] >= 72
    card.click()
    pw.expect(pg.get_by_role("button", name="Svart hoodie, I tvättkorgen")).to_be_visible()
    time.sleep(0.3)
    assert api(server["base"], "GET", "/api/garments")[0]["in_basket"] is True
    shot(pg, "kiosk-person")
    assert errors == []


def test_add_garment_mobile_shows_on_kiosk(server, browser, tmp_path):
    from PIL import Image

    photo = tmp_path / "big.jpg"
    Image.new("RGB", (3000, 4000), (170, 40, 60)).save(photo, quality=90)
    errors = []
    kiosk = new_page(browser, KIOSK, errors)
    kiosk.goto(server["base"] + "/?kiosk=1#/p/2")
    pw.expect(kiosk.get_by_text("Kiki har inga plagg än")).to_be_visible()

    phone = new_page(browser, PHONE, errors)
    phone.goto(server["base"] + "/#/admin/ny")
    phone.set_input_files("input[type=file]", str(photo))
    phone.get_by_role("radio", name="Kiki").click()
    phone.get_by_placeholder("Till exempel Svart hoodie").fill("Röd tröja")
    phone.get_by_role("radio", name="Kulört").click()
    phone.get_by_role("button", name="Spara plagg").click()
    pw.expect(phone.get_by_text("finns nu under Kiki")).to_be_visible()
    shot(phone, "phone-saved")

    pw.expect(kiosk.get_by_role("button", name="Röd tröja, Inte i tvättkorgen")).to_be_visible(timeout=5000)
    g = api(server["base"], "GET", "/api/garments")[0]
    assert (g["person_id"], g["color"]) == (2, "colored")
    assert errors == []


def test_wash_flow_done_overlay(server, browser):
    base = server["base"]
    a = add_garment(base, "Svart hoodie", in_basket=True)
    add_garment(base, "Mörka jeans", person_id=3, in_basket=True)
    add_garment(base, "Vit t-shirt", color="white", temp=60, in_basket=True)
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/tvatta")
    first = pg.locator(".suggestion").first
    pw.expect(first).to_contain_text("Mörkt 40°")
    pw.expect(first).to_contain_text("2 plagg")
    shot(pg, "kiosk-suggestions")
    first.get_by_role("button", name="Starta tvätt").click()
    pw.expect(pg.get_by_role("radio", name="Bomull 60°")).to_be_disabled()
    pg.locator(".sheet").get_by_role("button", name="Starta tvätt").click()
    pw.expect(pg.locator(".running-time")).to_contain_text("kvar")
    shot(pg, "kiosk-running")

    # Fast-forward: make the wash end in two seconds.
    soon = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat(timespec="seconds")
    with sqlite3.connect(server["db"]) as conn:
        conn.execute("UPDATE wash SET ends_at=? WHERE status='running'", (soon,))
    pg.reload()
    pw.expect(pg.get_by_role("heading", name="Tvätten är klar!")).to_be_visible(timeout=6000)
    shot(pg, "kiosk-done")
    pg.get_by_role("button", name="Tömt maskinen").click()
    pw.expect(pg.get_by_role("heading", name="Tvätten är klar!")).to_be_hidden()
    garments = {g["id"]: g for g in api(base, "GET", "/api/garments")}
    assert garments[a["id"]]["in_basket"] is False
    assert sum(g["in_basket"] for g in garments.values()) == 1
    assert errors == []


def _finish_soon(db, seconds=1):
    soon = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE wash SET ends_at=? WHERE status='running'", (soon,))


def _start_wash(base, garment_ids, program_name="Bomull 40°"):
    prog = next(p for p in api(base, "GET", "/api/programs") if p["name"] == program_name)
    return api(base, "POST", "/api/washes", {"program_id": prog["id"], "garment_ids": garment_ids})


def test_done_on_phone_is_a_dismissable_banner(server, browser):
    base = server["base"]
    g = add_garment(base, "Svart hoodie", in_basket=True)
    _start_wash(base, [g["id"]])
    _finish_soon(server["db"])
    errors = []
    phone = new_page(browser, PHONE, errors)
    phone.goto(base + "/#/admin")
    banner = phone.get_by_role("status").filter(has_text="Tvätten är klar")
    pw.expect(banner).to_be_visible(timeout=5000)
    pw.expect(phone.get_by_role("heading", name="Tvätten är klar!")).to_have_count(0)
    shot(phone, "phone-done-banner")
    banner.get_by_role("button", name="Stäng").click()
    pw.expect(banner).to_be_hidden()
    phone.get_by_role("button", name="Alla plagg").click()
    pw.expect(phone.get_by_role("heading", name="Alla plagg")).to_be_visible()
    assert api(base, "GET", "/api/washes/current")["wash"] is not None
    assert errors == []


def test_wake_tap_is_swallowed_after_idle(server, browser):
    add_garment(server["base"], "Svart hoodie")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.clock.install()
    pg.goto(server["base"] + "/?kiosk=1")
    pw.expect(pg.get_by_role("button", name="Svart hoodie, Inte i tvättkorgen")).to_be_visible()
    pg.clock.fast_forward("10:00")
    pg.get_by_role("button", name="Svart hoodie, Inte i tvättkorgen").click()
    pg.wait_for_timeout(300)
    assert api(server["base"], "GET", "/api/garments")[0]["in_basket"] is False
    pg.get_by_role("button", name="Svart hoodie, Inte i tvättkorgen").click()
    pw.expect(pg.get_by_role("button", name="Svart hoodie, I tvättkorgen")).to_be_visible()
    assert errors == []


def test_offline_banner_clears_after_successful_reload(server, browser):
    base = server["base"]
    g = add_garment(base, "Svart hoodie")
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1")
    pw.expect(pg.get_by_role("button", name="Svart hoodie, Inte i tvättkorgen")).to_be_visible()
    pg.route("**/api/garments", lambda route: route.abort())
    api(base, "POST", f"/api/garments/{g['id']}/basket", {"in_basket": True})
    pw.expect(pg.get_by_text("Ingen kontakt med tvätt-trackern")).to_be_visible(timeout=5000)
    pg.unroute("**/api/garments")
    api(base, "POST", f"/api/garments/{g['id']}/basket", {"in_basket": False})
    pw.expect(pg.get_by_text("Ingen kontakt med tvätt-trackern")).to_be_hidden(timeout=5000)


def test_pick_start_waits_for_current_check(server, browser):
    base = server["base"]
    add_garment(base, "A", in_basket=True)
    add_garment(base, "B", in_basket=True)
    errors = []
    pg = new_page(browser, KIOSK, errors)
    held = []
    pg.goto(base + "/?kiosk=1#/tvatta")
    pg.get_by_role("tab", name="Välj själv").click()
    pg.get_by_role("button", name="A", exact=True).click()
    pw.expect(pg.get_by_role("button", name="Starta tvätt (1)")).to_be_enabled()
    pg.route("**/api/suggestions/check", lambda route: held.append(route))
    pg.get_by_role("button", name="B", exact=True).click()
    pw.expect(pg.get_by_role("button", name="Starta tvätt (1)")).to_have_count(0)
    start = pg.get_by_role("button", name="Starta tvätt (2)")
    if start.count():
        pw.expect(start).to_be_disabled()
    for _ in range(50):
        if held:
            break
        pg.wait_for_timeout(50)
    held[0].continue_()
    pw.expect(pg.get_by_role("button", name="Starta tvätt (2)")).to_be_enabled()
    assert errors == []


def test_wool_cannot_use_cotton_program(server, browser):
    base = server["base"]
    from urllib.request import Request  # noqa: F401

    g = add_garment(base, "Ullsockor", in_basket=True)
    api(base, "PATCH", f"/api/garments/{g['id']}", {"care": "wool", "max_temp": 30})
    errors = []
    pg = new_page(browser, KIOSK, errors)
    pg.goto(base + "/?kiosk=1#/tvatta")
    pg.locator(".suggestion").first.get_by_role("button", name="Starta tvätt").click()
    pw.expect(pg.get_by_role("radio", name="Snabbtvätt 30°")).to_be_disabled()
    pw.expect(pg.get_by_role("radio", name="Ull 30°")).to_be_enabled()
    assert errors == []

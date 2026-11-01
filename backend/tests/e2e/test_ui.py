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

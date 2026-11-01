import time

import pytest
from starlette.testclient import TestClient

from app.kitchen import fetch, products
from app.kitchen.products import Product
from app.kitchen.scanner import NO_CAMERA, CameraUnavailable
from app.main import create_app
from tests.kitchen.barcode_images import blank_frame, ean13_frame
from tests.kitchen.test_scanner import FakeSource, wait_for

CODE = "4006381333931"
OTHER = "7310865004703"


def make_client(data_dir, frames=None, fail=False):
    def factory():
        if fail:
            raise CameraUnavailable(NO_CAMERA)
        return FakeSource(frames or [blank_frame()])

    return TestClient(create_app(data_dir, camera_factory=factory))


@pytest.fixture
def scan_client(tmp_path):
    with make_client(tmp_path / "d", [ean13_frame(CODE)]) as c:
        yield c


def item_id(client, name):
    return next(i["id"] for i in client.get("/api/items").json() if i["name"] == name)


def test_scan_start_503_without_camera(tmp_path):
    with make_client(tmp_path / "d", fail=True) as c:
        r = c.post("/api/scan/start")
        assert r.status_code == 503 and r.json()["detail"] == NO_CAMERA
        assert c.get("/api/scan/last").json()["running"] is False


def test_scan_flow_publishes_and_last(scan_client):
    seen = []
    scan_client.app.state.bus.publish = seen.append
    assert scan_client.get("/api/scan/last").json() == {"seq": 0, "code": None, "at": None, "error": None, "running": False}
    assert scan_client.post("/api/scan/start").json() == {"running": True}
    assert wait_for(lambda: scan_client.get("/api/scan/last").json()["code"] == CODE)
    assert "scan" in seen
    assert scan_client.post("/api/scan/start").status_code == 200  # heartbeat
    assert scan_client.post("/api/scan/stop").json() == {"running": False}


def test_stream_returns_jpeg_parts(scan_client):
    scan_client.post("/api/scan/start")
    assert wait_for(lambda: scan_client.app.state.scanner.latest_jpeg() is not None)
    with scan_client.stream("GET", "/api/scan/stream") as r:
        assert r.headers["content-type"].startswith("multipart/x-mixed-replace")
        chunk = next(r.iter_bytes())
        assert b"--frame" in chunk and b"image/jpeg" in chunk
        scan_client.app.state.scanner.stop()


def test_stream_when_not_running_ends(scan_client):
    r = scan_client.get("/api/scan/stream")
    assert r.status_code == 409


def test_barcode_unknown_with_product(client, monkeypatch):
    monkeypatch.setattr(products, "lookup", lambda code: Product("Arla Ko Mellanmjölk 1,5% 1 l", "Arla Ko", "1 l", "Kyl", "Mellanmjölk 1,5%"))
    r = client.get(f"/api/barcodes/{CODE}").json()
    assert r["item"] is None and r["lookup_failed"] is False
    assert r["product"]["name"] == "Arla Ko Mellanmjölk 1,5% 1 l" and r["product"]["category"] == "Kyl"
    assert r["product"]["short_name"] == "Mellanmjölk 1,5%"
    assert "Mjölk" in [c["name"] for c in r["candidates"]]


def test_barcode_lookup_failed(client, monkeypatch):
    def boom(code):
        raise fetch.FetchError("Kunde inte nå world.openfoodfacts.org.")

    monkeypatch.setattr(products, "lookup", boom)
    r = client.get(f"/api/barcodes/{CODE}").json()
    assert (r["item"], r["product"], r["lookup_failed"]) == (None, None, True)
    monkeypatch.setattr(products, "lookup", lambda code: None)
    assert client.get(f"/api/barcodes/{CODE}").json()["lookup_failed"] is False


def test_link_barcode_existing_and_new_item(client, monkeypatch):
    called = []
    monkeypatch.setattr(products, "lookup", lambda code: called.append(code))
    mid = item_id(client, "Mjölk")
    r = client.post("/api/barcodes", json={"code": CODE, "item_id": mid, "product_name": "Arla Mellanmjölk"})
    assert r.status_code == 200 and r.json()["name"] == "Mjölk"
    known = client.get(f"/api/barcodes/{CODE}").json()
    assert known["item"]["id"] == mid and called == []
    assert client.get(f"/api/items/{mid}").json()["barcodes"] == [{"code": CODE, "product_name": "Arla Mellanmjölk"}]

    r = client.post("/api/barcodes", json={"code": OTHER, "new_item": {"name": "Havredryck", "category": "Dryck"}})
    assert r.status_code == 200 and r.json()["name"] == "Havredryck" and r.json()["status"] == "out"
    assert client.post("/api/barcodes", json={"code": OTHER, "new_item": {"name": "mjölk", "category": "Kyl"}}).status_code == 409
    # relinking moves the code
    client.post("/api/barcodes", json={"code": CODE, "item_id": item_id(client, "Fil")})
    assert client.get(f"/api/barcodes/{CODE}").json()["item"]["name"] == "Fil"
    assert client.delete(f"/api/barcodes/{CODE}").status_code == 204
    assert client.delete(f"/api/barcodes/{CODE}").status_code == 404


def test_barcode_of_archived_item_is_unknown(client, monkeypatch):
    monkeypatch.setattr(products, "lookup", lambda code: None)
    mid = item_id(client, "Mjölk")
    client.post("/api/barcodes", json={"code": CODE, "item_id": mid})
    client.delete(f"/api/items/{mid}")
    assert client.get(f"/api/barcodes/{CODE}").json()["item"] is None


def test_barcode_invalid_422(client):
    assert client.get("/api/barcodes/4006381333932").status_code == 422
    assert client.get("/api/barcodes/abc").status_code in (404, 422)
    assert client.post("/api/barcodes", json={"code": "123", "item_id": 1}).status_code == 422
    assert client.post("/api/barcodes", json={"code": CODE}).status_code == 422


def test_heartbeat_never_restarts(tmp_path):
    with make_client(tmp_path / "d", [blank_frame()]) as c:
        r = c.post("/api/scan/heartbeat")
        assert r.status_code == 409 and r.json()["detail"] == "Kameran är inte igång."
        c.post("/api/scan/start")
        assert c.post("/api/scan/heartbeat").json() == {"running": True}
        c.post("/api/scan/stop")
        assert c.post("/api/scan/heartbeat").status_code == 409
        assert c.app.state.scanner.running is False


def test_scan_start_and_exit_publish(tmp_path):
    with make_client(tmp_path / "d", [blank_frame()]) as c:
        seen = []
        c.app.state.bus.publish = seen.append
        c.post("/api/scan/start")
        assert "scan" in seen
        seen.clear()
        c.post("/api/scan/stop")
        assert wait_for(lambda: "scan" in seen)

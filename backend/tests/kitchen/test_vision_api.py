import time

import numpy as np
import pytest
from starlette.testclient import TestClient

from app.kitchen import vision
from app.kitchen.vision import HistogramEmbedder
from app.main import create_app
from tests.kitchen.barcode_images import ean13_frame
from tests.kitchen.vision_images import scene

CODE = "4006381333931"


class Cam:
    """A camera whose picture the test changes; every read adds fresh noise like a real webcam."""

    def __init__(self, item=None):
        self.item, self.raw, self.n = item, None, 0

    def show(self, item=None, raw=None, wait=True):
        """Change the picture; by default wait until the scanner has read it (if it is running)."""
        self.item, self.raw = item, raw
        start = self.n
        end = time.time() + 2
        while wait and self.n < start + 3 and time.time() < end:
            time.sleep(0.01)

    def read(self):
        time.sleep(0.01)
        self.n += 1
        return self.raw if self.raw is not None else scene(self.item, seed=self.n % 50)

    def release(self):
        pass


def fake_loader(data_dir):
    return HistogramEmbedder(), None


def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def cam():
    return Cam()


@pytest.fixture
def vc(tmp_path, cam):
    with TestClient(create_app(tmp_path / "d", camera_factory=lambda: cam, vision_loader=fake_loader)) as c:
        yield c
        c.app.state.scanner.stop()
        c.app.state.vision.wait_idle()


def new_item(client, name, category="Kyl"):
    r = client.post("/api/items", json={"name": name, "category": category})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def learn(client, cam, item_id, item, n=3):
    cam.show(item)
    assert wait_for(lambda: client.app.state.scanner.latest_frame() is not None)
    saved = 0
    for _ in range(n):
        r = client.post("/api/vision/capture", json={"item_id": item_id})
        assert r.status_code == 200, r.text
        saved += r.json()["saved"]
        time.sleep(0.03)
    return saved


def test_unavailable_without_model(client):
    assert client.get("/api/vision/status").json() == {"available": False, "message": vision.NOT_INSTALLED, "images": 0}
    r = client.post("/api/vision/identify")
    assert r.status_code == 503 and r.json()["detail"] == vision.NOT_INSTALLED
    assert client.post("/api/vision/capture", json={"item_id": 1}).status_code == 503
    assert client.post("/api/vision/confirm", json={"token": "x", "item_id": 1}).json() == {"saved": False}
    assert client.get("/api/vision/items").json() == []


def test_identify_needs_running_camera(vc):
    assert vc.get("/api/vision/status").json()["available"] is True
    r = vc.post("/api/vision/identify")
    assert r.status_code == 409 and r.json()["detail"] == "Kameran är inte igång."
    assert vc.post("/api/vision/capture", json={"item_id": 1}).status_code == 409


def test_learn_then_identify_and_confirm(vc, cam):
    milk, banana = new_item(vc, "Testmjölk"), new_item(vc, "Testbanan", "Frukt & grönt")
    vc.post("/api/scan/start")
    assert learn(vc, cam, milk, "milk") >= 1
    assert learn(vc, cam, banana, "banana") >= 1
    assert vc.get("/api/vision/status").json()["images"] >= 2

    cam.show("milk")
    r = vc.post("/api/vision/identify").json()
    assert r["decision"] == "sure"
    assert r["matches"][0]["item"]["id"] == milk and r["matches"][0]["item"]["name"] == "Testmjölk"
    assert [m["item"]["id"] for m in r["matches"]] == [milk, banana]
    before = len(vc.get(f"/api/items/{milk}/images").json())
    # the same picture again is a duplicate, so confirming it saves nothing new
    assert vc.post("/api/vision/confirm", json={"token": r["token"], "item_id": milk}).json() == {"saved": False}
    # confirming it as the other item teaches that item
    assert vc.post("/api/vision/confirm", json={"token": r["token"], "item_id": banana}).json() == {"saved": True}
    assert len(vc.get(f"/api/items/{milk}/images").json()) == before
    assert vc.post("/api/vision/confirm", json={"token": "unknown", "item_id": milk}).json() == {"saved": False}


def test_identify_with_nothing_learned(vc, cam):
    vc.post("/api/scan/start")
    cam.show("milk")
    assert wait_for(lambda: vc.app.state.scanner.latest_frame() is not None)
    r = vc.post("/api/vision/identify").json()
    assert r["decision"] == "none" and r["matches"] == [] and r["token"]


def test_capture_and_confirm_errors(vc, cam):
    vc.post("/api/scan/start")
    assert wait_for(lambda: vc.app.state.scanner.latest_frame() is not None)
    assert vc.post("/api/vision/capture", json={"item_id": 9999}).status_code == 404
    assert vc.post("/api/vision/capture", json={"item_id": "abc"}).status_code == 422
    assert vc.post("/api/vision/capture", json={}).status_code == 422
    assert vc.post("/api/vision/confirm", json={"token": "", "item_id": 1}).status_code == 422
    token = vc.post("/api/vision/identify").json()["token"]
    gone = new_item(vc, "Borta")
    vc.delete(f"/api/items/{gone}")
    assert vc.post("/api/vision/confirm", json={"token": token, "item_id": gone}).status_code == 404
    assert vc.get("/api/items/abc/images").status_code in (404, 422)
    assert vc.get("/api/items/9999/images").status_code == 404
    assert vc.delete("/api/vision/images/9999").status_code == 404


def test_list_and_delete_pictures(vc, cam):
    milk = new_item(vc, "Testmjölk")
    vc.post("/api/scan/start")
    learn(vc, cam, milk, "milk")
    learn(vc, cam, milk, "coffee")  # a second, different picture for the same item
    images = vc.get(f"/api/items/{milk}/images").json()
    assert len(images) >= 2 and all(i["source"] == "learn" for i in images)
    listing = vc.get("/api/vision/items").json()
    assert listing == [{"item_id": milk, "name": "Testmjölk", "count": len(images), "cover": images[0]["url"]}]
    assert vc.get(images[0]["url"]).status_code == 200
    data_dir = vc.app.state.data_dir
    assert vc.delete(f"/api/vision/images/{images[0]['id']}").status_code == 204
    assert not (data_dir / "vision" / images[0]["url"].rsplit("/", 1)[1]).exists()
    assert len(vc.get(f"/api/items/{milk}/images").json()) == len(images) - 1
    assert vc.delete(f"/api/items/{milk}/images").status_code == 204
    assert vc.get(f"/api/items/{milk}/images").json() == []
    assert list((data_dir / "vision").iterdir()) == []
    assert vc.get("/api/vision/items").json() == []


def test_archived_item_not_suggested(vc, cam):
    milk, coffee = new_item(vc, "Testmjölk"), new_item(vc, "Testkaffe", "Skafferi")
    vc.post("/api/scan/start")
    learn(vc, cam, milk, "milk")
    learn(vc, cam, coffee, "coffee")
    vc.delete(f"/api/items/{milk}")
    cam.show("milk")
    r = vc.post("/api/vision/identify").json()
    assert all(m["item"]["id"] != milk for m in r["matches"])
    assert vc.get("/api/vision/items").json()[0]["item_id"] == coffee


def test_barcode_teaches_picture_when_linked_and_when_known(vc, cam):
    milk = new_item(vc, "Testmjölk")
    cam.show(raw=ean13_frame(CODE), wait=False)
    vc.post("/api/scan/start")
    assert wait_for(lambda: vc.get("/api/scan/last").json()["code"] == CODE)
    assert wait_for(lambda: vc.app.state.vision.tokens.get(vc.app.state.vision.tokens._by_code.get(CODE, "")) is not None)
    r = vc.post("/api/barcodes", json={"code": CODE, "item_id": milk})
    assert r.status_code == 200
    images = vc.get(f"/api/items/{milk}/images").json()
    assert [i["source"] for i in images] == ["scan"]
    # Next time the known code is read, the picture is learned right away
    vc.post("/api/scan/stop")
    vc.app.state.vision.wait_idle()
    vc.app.state.vision.on_barcode(CODE, scene("milk"))
    assert [i["source"] for i in vc.get(f"/api/items/{milk}/images").json()] == ["scan", "scan"]
    vc.app.state.vision.on_barcode(CODE, scene("milk", seed=5))  # the same view again adds nothing
    assert len(vc.get(f"/api/items/{milk}/images").json()) == 2


def test_automatic_suggestion(vc, cam):
    milk, banana = new_item(vc, "Testmjölk"), new_item(vc, "Testbanan", "Frukt & grönt")
    seen = []
    publish = vc.app.state.bus.publish
    vc.app.state.bus.publish = lambda t: (seen.append(t), publish(t))
    vc.post("/api/scan/start")
    learn(vc, cam, milk, "milk")
    learn(vc, cam, banana, "banana")
    cam.show(None)
    time.sleep(1.2)  # empty scene becomes the background
    first = vc.get("/api/vision/last").json()["seq"]
    cam.show("banana")
    assert wait_for(lambda: vc.get("/api/vision/last").json()["seq"] > first, timeout=4)
    last = vc.get("/api/vision/last").json()
    assert last["matches"][0]["item"]["id"] == banana and last["decision"] in ("sure", "maybe") and last["token"]
    assert "vision" in seen
    time.sleep(1.0)
    assert vc.get("/api/vision/last").json()["seq"] == last["seq"]  # still the same hold: no repeat


def test_worker_error_does_not_stop_scanner(tmp_path):
    class Flaky(HistogramEmbedder):
        calls = 0

        def embed(self, img):
            Flaky.calls += 1
            if Flaky.calls > 1:
                raise RuntimeError("model broke")
            return super().embed(img)

    cam = Cam()
    app = create_app(tmp_path / "d", camera_factory=lambda: cam, vision_loader=lambda d: (Flaky(), None))
    with TestClient(app) as c:
        cam.show(None, wait=False)
        c.post("/api/scan/start")
        time.sleep(1.0)
        cam.show(raw=ean13_frame(CODE))
        assert wait_for(lambda: c.get("/api/scan/last").json()["code"] == CODE)
        assert c.get("/api/scan/last").json()["running"] is True
        c.app.state.scanner.stop()
        c.app.state.vision.wait_idle()


def test_cap_removes_oldest_automatic_first(vc, monkeypatch):
    monkeypatch.setattr(vision, "MAX_PER_ITEM", 3)
    milk = new_item(vc, "Testmjölk")
    svc = vc.app.state.vision
    rng = np.random.default_rng(1)
    vecs = [vision.unit(rng.normal(size=HistogramEmbedder.dim)) for _ in range(5)]
    assert svc._save(milk, vecs[0], b"jpeg", "learn")
    assert svc._save(milk, vecs[1], b"jpeg", "scan")
    assert svc._save(milk, vecs[2], b"jpeg", "confirm")
    assert svc._save(milk, vecs[3], b"jpeg", "learn")  # over the cap: the oldest automatic one goes
    assert sorted(i["source"] for i in svc.item_images(milk)) == ["confirm", "learn", "learn"]
    assert svc._save(milk, vecs[4], b"jpeg", "learn")
    assert sorted(i["source"] for i in svc.item_images(milk)) == ["learn", "learn", "learn"]
    assert len(list((vc.app.state.data_dir / "vision").iterdir())) == 3

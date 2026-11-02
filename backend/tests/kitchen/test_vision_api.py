import time

import numpy as np
import pytest
from starlette.testclient import TestClient

from app.kitchen import locate, vision
from app.kitchen.vision import HistogramEmbedder
from app.main import create_app
from tests.kitchen.barcode_images import ean13_frame
from tests.kitchen.vision_images import scene

CODE = "4006381333931"


def locate_image(frame):
    return locate.locate(frame).image


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
        return self.raw if self.raw is not None else scene(self.item, seed=self.n % 50, person=True)

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
    huge = 2**70
    assert vc.get(f"/api/items/{huge}/images").status_code == 404
    assert vc.delete(f"/api/vision/images/{huge}").status_code == 404
    assert vc.post("/api/vision/capture", json={"item_id": huge}).status_code == 422
    assert vc.post("/api/vision/confirm", json={"token": "x", "item_id": huge}).status_code == 422


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
    vc.app.state.vision.wait_idle()
    assert [i["source"] for i in vc.get(f"/api/items/{milk}/images").json()] == ["scan", "scan"]
    vc.app.state.vision.on_barcode(CODE, scene("milk", seed=5))  # the same view again adds nothing
    vc.app.state.vision.wait_idle()
    assert len(vc.get(f"/api/items/{milk}/images").json()) == 2


def test_automatic_suggestion(vc, cam):  # noqa: PLR0915
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


def test_full_of_learned_pictures_keeps_them(vc, monkeypatch):
    monkeypatch.setattr(vision, "MAX_PER_ITEM", 2)
    milk = new_item(vc, "Testmjölk")
    svc = vc.app.state.vision
    rng = np.random.default_rng(2)
    vecs = [vision.unit(rng.normal(size=HistogramEmbedder.dim)) for _ in range(3)]
    assert svc._save(milk, vecs[0], b"jpeg", "learn")
    assert svc._save(milk, vecs[1], b"jpeg", "learn")
    assert svc._save(milk, vecs[2], b"jpeg", "confirm") is False  # would push out a learned picture
    assert sorted(i["source"] for i in svc.item_images(milk)) == ["learn", "learn"]


def test_gallery_forgets_deleted_newest_picture(vc):
    milk, coffee = new_item(vc, "Testmjölk"), new_item(vc, "Testkaffe", "Skafferi")
    svc = vc.app.state.vision
    emb = HistogramEmbedder()
    m = emb.embed(locate_image(scene("milk")))
    c = emb.embed(locate_image(scene("coffee")))
    assert svc._save(coffee, c, b"jpeg", "learn")
    assert svc._save(milk, m, b"jpeg", "learn")
    assert svc._matches(m)[0][0] == milk
    newest = svc.item_images(milk)[0]["id"]
    assert svc.delete_image(newest)
    assert svc._save(coffee, emb.embed(locate_image(scene("bread"))), b"jpeg", "learn")  # reuses the row id
    assert all(item_id != milk for item_id, _ in svc._matches(m))


def test_model_id_includes_feature_length(tmp_path):
    from tests.kitchen.onnx_tiny import tiny_classifier

    tiny_classifier(tmp_path / "m.onnx", size=224, feat=6)
    assert vision.OnnxEmbedder(tmp_path / "m.onnx").model_id == "mobilenetv2-2022apr-6-obj1"
    assert HistogramEmbedder().model_id == "histogram-v1-obj1"


def test_capture_without_item_saves_nothing(vc, cam):
    milk = new_item(vc, "Testmjölk")
    vc.post("/api/scan/start")
    cam.show(None)
    assert wait_for(lambda: vc.app.state.scanner.latest_frame() is not None)
    r = vc.post("/api/vision/capture", json={"item_id": milk})
    assert r.status_code == 200 and r.json() == {"saved": False, "count": 0, "found": False}
    cam.show("milk")
    r = vc.post("/api/vision/capture", json={"item_id": milk}).json()
    assert r == {"saved": True, "count": 1, "found": True}


def test_capture_item_too_close_saves_nothing(vc, cam):
    milk = new_item(vc, "Testmjölk")
    vc.post("/api/scan/start")
    cam.show(raw=np.full((480, 640, 3), (40, 40, 200), np.uint8))  # fills the whole box
    r = vc.post("/api/vision/capture", json={"item_id": milk}).json()
    assert r == {"saved": False, "count": 0, "found": False}


def test_legacy_pictures_removed_on_start(tmp_path):
    from app.db import connect

    data = tmp_path / "d"
    app = create_app(data, vision_loader=fake_loader)
    vecs = vision.to_blob(np.ones(HistogramEmbedder.dim))
    with TestClient(app) as c:
        milk = new_item(c, "Testmjölk")
        conn = connect(app.state.db_path)
        with conn:
            for name, model in (("old.jpg", "histogram-v1"), ("old2.jpg", "mobilenetv2-2022apr-1280"), ("new.jpg", "histogram-v1-obj1")):
                (data / "vision" / name).write_bytes(b"jpeg")
                conn.execute(
                    "INSERT INTO item_image (item_id, file, model, embedding, source, created_at) VALUES (?, ?, ?, ?, 'learn', '2026-11-01T00:00:00Z')",
                    (milk, name, model, vecs),
                )
        conn.close()
        assert c.get("/api/vision/status").json()["images"] == 1
        assert [i["url"] for i in c.get(f"/api/items/{milk}/images").json()] == ["/vision/new.jpg"]
        assert sorted(p.name for p in (data / "vision").iterdir()) == ["new.jpg"]


def test_same_item_different_shirt():
    emb = HistogramEmbedder()
    a = emb.embed(locate_image(scene("milk", person=True, shirt=0)))
    b = emb.embed(locate_image(scene("milk", person=True, shirt=1, seed=3)))
    other = emb.embed(locate_image(scene("coffee", person=True, shirt=0)))
    assert vision.cosine(a, b) >= 0.9
    assert vision.cosine(a, other) < 0.8


def test_worker_keeps_latest_analysis(vc, cam):
    milk = new_item(vc, "Testmjölk")
    svc = vc.app.state.vision
    vc.post("/api/scan/start")
    assert learn(vc, cam, milk, "milk") >= 1
    cam.show("milk")
    assert wait_for(lambda: (svc.analysis or {}).get("decision") == "sure", timeout=3)
    a = svc.analysis
    assert a["found"] and a["label"] == "Testmjölk" and a["has_gallery"] and a["score"] > 0.8 and a["contour"]
    img = np.full((360, 640, 3), 90, np.uint8)
    drawn = svc.draw_overlay(img.copy(), (480, 640))
    assert (np.abs(drawn.astype(int) - (113, 191, 47)) <= 12).all(axis=-1).sum() > 100  # green outline
    vc.app.state.scanner.stop()
    svc.wait_idle()
    assert svc.analysis is None
    assert svc.draw_overlay(img.copy(), (480, 640)).tolist() == img.tolist()  # nothing drawn without the worker


def test_overlay_drawn_in_stream_picture(vc, cam):
    import cv2

    milk = new_item(vc, "Testmjölk")
    vc.post("/api/scan/start")
    assert learn(vc, cam, milk, "milk") >= 1
    cam.show("milk")
    svc = vc.app.state.vision
    assert wait_for(lambda: (svc.analysis or {}).get("decision") == "sure", timeout=3)
    time.sleep(0.3)
    shown = cv2.imdecode(np.frombuffer(vc.app.state.scanner.latest_jpeg(), np.uint8), cv2.IMREAD_COLOR)
    assert (np.abs(shown.astype(int) - (113, 191, 47)) <= 30).all(axis=-1).sum() > 100
    assert vc.app.state.scanner.latest_frame() is not None
    raw = vc.app.state.scanner.latest_frame()
    assert (np.abs(raw.astype(int) - (113, 191, 47)) <= 30).all(axis=-1).sum() == 0  # the real picture stays clean

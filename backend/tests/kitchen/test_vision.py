import numpy as np
import pytest

from app.kitchen import vision
from app.kitchen.vision import Gallery, HistogramEmbedder, OnnxEmbedder, TokenStore, Watcher, decide
from tests.kitchen.onnx_tiny import tiny_classifier
from tests.kitchen.vision_images import scene


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_center_crop_is_middle_square():
    frame = np.zeros((1080, 1920, 3), np.uint8)
    crop = vision.center_crop(frame)
    assert crop.shape == (864, 864, 3)
    frame[540, 960] = 255
    assert vision.center_crop(frame)[432, 432].tolist() == [255, 255, 255]


def test_model_input_size_and_grey():
    assert vision.model_input(np.zeros((480, 640, 3), np.uint8)).shape == (224, 224, 3)
    assert vision.model_input(np.zeros((480, 640), np.uint8)).shape == (224, 224, 3)


def test_preprocess_normalises_rgb():
    img = np.zeros((224, 224, 3), np.uint8)
    img[:, :, 2] = 255  # red in BGR
    blob = vision.preprocess(img)
    assert blob.shape == (1, 3, 224, 224) and blob.dtype == np.float32
    assert blob[0, 0, 0, 0] == pytest.approx((1 - 0.485) / 0.229, rel=1e-5)  # R channel first
    assert blob[0, 2, 0, 0] == pytest.approx((0 - 0.406) / 0.225, rel=1e-5)


def test_blob_round_trip_is_unit_float16():
    v = np.arange(1, 11, dtype=np.float32)
    back = vision.from_blob(vision.to_blob(v))
    assert back.shape == (10,)
    assert float(np.linalg.norm(back)) == pytest.approx(1.0, abs=1e-3)
    assert vision.cosine(back, v) == pytest.approx(1.0, abs=1e-3)


class FakeLayer:
    def __init__(self, t):
        self.type = t


class FakeNet:
    def __init__(self, layers):
        self.layers = layers

    def getLayerNames(self):
        return [n for n, _ in self.layers]

    def getLayer(self, name):
        return FakeLayer(dict(self.layers)[name])


def test_feature_layer_is_last_pool_before_classifier():
    net = FakeNet([("conv", "Convolution"), ("pool", "Pooling"), ("flat", "Flatten"), ("fc", "Gemm"),
                   ("shape", "Reshape"), ("prob", "Softmax")])
    assert vision.feature_layer(net) == "flat"
    assert vision.feature_layer(FakeNet([("conv", "Convolution"), ("pool", "Pooling")])) == "pool"
    assert vision.feature_layer(FakeNet([("conv", "Convolution"), ("fc", "Gemm")])) is None


def test_onnx_embedder_uses_feature_layer(tmp_path):
    path = tmp_path / "tiny.onnx"
    tiny_classifier(path, size=224, feat=6, classes=5)
    emb = OnnxEmbedder(path)
    assert emb.dim == 6  # the pooled features, not the 5 class scores
    a = emb.embed(vision.model_input(scene("milk")))
    assert a.shape == (6,) and float(np.linalg.norm(a)) == pytest.approx(1.0, abs=1e-5)
    assert emb.embed(scene("milk")[:300, :300]).shape == (6,)  # any size is resized


def test_load_embedder(tmp_path, monkeypatch):
    monkeypatch.delenv("TVATT_FAKE_VISION", raising=False)
    monkeypatch.delenv("TVATT_VISION_MODEL", raising=False)
    emb, msg = vision.load_embedder(tmp_path)
    assert emb is None and msg == vision.NOT_INSTALLED
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "mobilenetv2.onnx").write_bytes(b"not a model")
    emb, msg = vision.load_embedder(tmp_path)
    assert emb is None and msg == vision.BROKEN_MODEL
    tiny_classifier(tmp_path / "models" / "mobilenetv2.onnx", size=224)
    emb, msg = vision.load_embedder(tmp_path)
    assert isinstance(emb, OnnxEmbedder) and msg is None
    monkeypatch.setenv("TVATT_FAKE_VISION", "1")
    emb, msg = vision.load_embedder(tmp_path)
    assert isinstance(emb, HistogramEmbedder)


def test_histogram_embedder_tells_items_apart():
    emb = HistogramEmbedder()
    e = {name: emb.embed(vision.model_input(scene(name, seed=i))) for i, name in enumerate(["milk", "banana", "coffee"])}
    again = emb.embed(vision.model_input(scene("milk", seed=9, shift=15)))
    assert vision.cosine(again, e["milk"]) > 0.95
    assert vision.cosine(again, e["banana"]) < 0.8
    assert vision.cosine(again, e["coffee"]) < 0.8


def test_gallery_best_picture_per_item():
    g = Gallery()
    assert g.match([1.0, 0.0]) == []
    g.set([(1, [1, 0, 0]), (1, [0.8, 0.6, 0]), (2, [0, 1, 0]), (3, [0, 0, 1])])
    m = g.match([0.9, 0.1, 0])
    assert [i for i, _ in m] == [1, 2, 3]
    assert m[0][1] == pytest.approx(vision.cosine([0.9, 0.1, 0], [1, 0, 0]))
    assert len(g.match([0.9, 0.1, 0], k=2)) == 2
    assert g.match([1.0, 0.0]) == []  # other model's dimension


LIMITS = {"sure": 0.8, "maybe": 0.65, "margin": 0.05}


@pytest.mark.parametrize("matches, expected", [
    ([], "none"),
    ([(1, 0.9)], "sure"),
    ([(1, 0.9), (2, 0.87)], "maybe"),  # too close to the second best
    ([(1, 0.9), (2, 0.84)], "sure"),
    ([(1, 0.7), (2, 0.2)], "maybe"),
    ([(1, 0.6)], "none"),
])
def test_decide(matches, expected):
    assert decide(matches, LIMITS) == expected


def test_thresholds_from_env(monkeypatch):
    monkeypatch.setenv("TVATT_VISION_SURE", "0.9")
    monkeypatch.setenv("TVATT_VISION_MAYBE", "bad")
    t = vision.thresholds()
    assert t["sure"] == 0.9 and t["maybe"] == 0.65


def test_token_store_limit_expiry_and_codes():
    clock = Clock()
    store = TokenStore(limit=2, ttl=10, clock=clock)
    a = store.put("a")
    b = store.put("b", code="123")
    c = store.put("c")
    assert store.get(a) is None  # pushed out by the limit
    assert store.get(b) == "b" and store.get(c) == "c"
    assert store.for_code("123") == "b"
    assert store.for_code("123") is None  # taken
    clock.t += 11
    assert store.get(c) is None
    assert store.get("nope") is None


def embed_fn():
    emb = HistogramEmbedder()
    return lambda frame: emb.embed(vision.model_input(frame))


def learned(*items):
    """A recognise() callback that suggests only items in a gallery learned from these scenes."""
    embed = embed_fn()
    g = Gallery()
    g.set((i, embed(scene(name, seed=100 + i))) for i, name in enumerate(items))
    calls = []

    def recognise(vec):
        sure = decide(g.match(vec), LIMITS) == "sure"
        calls.append(sure)
        return sure

    recognise.calls = calls
    return recognise


def run(watcher, frames, clock, recognise, step=0.25):
    out = []
    embed = embed_fn()
    for f in frames:
        out.append(watcher.step(f, embed, recognise))
        clock.t += step
    return out


def hits(out):
    return [i for i, v in enumerate(out) if v is not None]


def test_watcher_empty_scene_never_suggests():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("banana")
    out = run(w, [scene(None, seed=i) for i in range(20)], clock, rec)
    assert hits(out) == []


def test_watcher_one_suggestion_per_hold():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("banana", "coffee")
    frames = [scene(None, seed=i) for i in range(4)] + [scene("banana", seed=10 + i) for i in range(10)]
    assert hits(run(w, frames, clock, rec)) == [6]  # arrives at 4 (moved), still at 5 and 6 → once
    # take it away and hold it up again: one more suggestion
    frames = [scene(None, seed=30 + i) for i in range(4)] + [scene("banana", seed=40 + i) for i in range(6)]
    assert len(hits(run(w, frames, clock, rec))) == 1


def test_watcher_hand_shake_is_same_hold():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("banana")
    frames = [scene(None, seed=i) for i in range(4)] + [scene("banana", seed=10 + i) for i in range(4)]
    frames += [scene("banana", seed=20, shift=40)] + [scene("banana", seed=21 + i, shift=40) for i in range(4)]
    assert len(hits(run(w, frames, clock, rec))) == 1


def test_watcher_item_held_when_opening_is_suggested():
    clock = Clock()
    w = Watcher(clock)
    assert hits(run(w, [scene("banana", seed=i) for i in range(6)], clock, learned("banana"))) == [2]


def test_watcher_unrecognised_scene_becomes_background():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("banana")
    # Opened while holding something unknown: it is not suggested and becomes the background …
    out = run(w, [scene("coffee", seed=i) for i in range(5)], clock, rec)
    assert hits(out) == [] and rec.calls == [False]
    # … and when it is put down, the empty kitchen replaces it; the banana is still found
    frames = [scene(None, seed=10 + i) for i in range(4)] + [scene("banana", seed=20 + i) for i in range(4)]
    assert len(hits(run(w, frames, clock, rec))) == 1


def test_watcher_barcode_hold_not_suggested_again():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("coffee")
    embed = embed_fn()
    run(w, [scene(None, seed=i) for i in range(4)], clock, rec)
    w.barcode_seen(embed(scene("coffee", seed=50)))
    # still holding the scanned item, with a shake after the quiet time: no card pops up again
    frames = [scene("coffee", seed=60 + i) for i in range(12)] + [scene("coffee", seed=80 + i, shift=30) for i in range(6)]
    assert hits(run(w, frames, clock, rec)) == []
    # put down and held up again: suggested
    frames = [scene(None, seed=90 + i) for i in range(4)] + [scene("coffee", seed=95 + i) for i in range(4)]
    assert len(hits(run(w, frames, clock, rec))) == 1


def test_watcher_waits_after_barcode_without_picture():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("coffee")
    run(w, [scene(None, seed=i) for i in range(4)], clock, rec)
    w.barcode_seen()
    frames = [scene("bread", seed=10 + i, shift=(-1) ** i * 60) for i in range(4)] + [scene("coffee", seed=20 + i) for i in range(12)]
    out = run(w, frames, clock, rec)
    assert len(hits(out)) == 1
    assert hits(out)[0] * 0.25 >= vision.QUIET_AFTER_BARCODE - 0.5


def test_watcher_moving_item_not_recognised():
    clock = Clock()
    w = Watcher(clock)
    rec = learned("milk")
    run(w, [scene(None, seed=i) for i in range(4)], clock, rec)
    out = run(w, [scene("milk", seed=10 + i, shift=(-1) ** i * 60) for i in range(10)], clock, rec)
    assert hits(out) == []

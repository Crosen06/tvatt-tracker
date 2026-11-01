import importlib.util
import json
from pathlib import Path

from app.kitchen import scanner
from tests.kitchen.barcode_images import blank_frame, ean13_frame

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "camera_test.py"
CODE = "4006381333931"


def load_script():
    spec = importlib.util.spec_from_file_location("camera_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeCam:
    def __init__(self, index):
        self.released = False

    def read(self):
        return ean13_frame(CODE, size=(1080, 1920))

    def info(self):
        return {"width": 1920, "height": 1080, "format": "MJPG", "fps": 30.0, "autofocus": 1.0}

    def release(self):
        self.released = True


def test_camera_test_reads_code_and_saves_picture(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scanner, "CvSource", FakeCam)
    mod = load_script()
    monkeypatch.setattr(mod, "release_app_camera", lambda base: None)
    out = tmp_path / "bild.jpg"
    assert mod.main(["--seconds", "0.3", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert f"Läste {CODE}" in text and "1920×1080 MJPG" in text
    assert out.stat().st_size > 1000
    assert json.loads(text.strip().splitlines()[-1])["codes"] == [CODE]


def test_camera_test_warns_about_low_resolution(tmp_path, monkeypatch, capsys):
    class LowRes(FakeCam):
        def read(self):
            return blank_frame()

        def info(self):
            return {**super().info(), "width": 640, "height": 480}

    monkeypatch.setattr(scanner, "CvSource", LowRes)
    mod = load_script()
    monkeypatch.setattr(mod, "release_app_camera", lambda base: None)
    assert mod.main(["--seconds", "0.2", "--out", str(tmp_path / "b.jpg")]) == 1
    text = capsys.readouterr().out
    assert "bara 640×480" in text and "Ingen streckkod" in text


def test_camera_test_recognize_prints_best_matches(tmp_path, monkeypatch, capsys):
    from app.kitchen import vision
    from app.main import create_app
    from tests.kitchen.vision_images import scene

    monkeypatch.setenv("TVATT_FAKE_VISION", "1")
    app = create_app(tmp_path / "data")
    svc = app.state.vision
    emb = vision.HistogramEmbedder()
    conn = __import__("app.db", fromlist=["connect"]).connect(app.state.db_path)
    ids = {n: conn.execute("SELECT id FROM item WHERE name=?", (n,)).fetchone()[0] for n in ("Banan", "Kaffe")}
    conn.close()
    for name, what in (("Banan", "banana"), ("Kaffe", "coffee")):
        svc._save(ids[name], emb.embed(vision.model_input(scene(what))), b"jpeg", "learn")

    class BananaCam(FakeCam):
        def read(self):
            return scene("banana", seed=3)

    monkeypatch.setattr(scanner, "CvSource", BananaCam)
    mod = load_script()
    monkeypatch.setattr(mod, "release_app_camera", lambda base: None)
    rc = mod.main(["--seconds", "1.2", "--recognize", "--data", str(tmp_path / "data"), "--out", str(tmp_path / "b.jpg")])
    text = capsys.readouterr().out
    assert rc == 0
    assert "histogram-v1" in text and "2 inlärda bilder av 2 varor" in text
    line = next(l for l in text.splitlines() if l.startswith("  Banan"))
    assert "Kaffe" in line and "säker" in line


def test_camera_test_recognize_without_model(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TVATT_FAKE_VISION", raising=False)
    monkeypatch.delenv("TVATT_VISION_MODEL", raising=False)
    monkeypatch.setattr(scanner, "CvSource", FakeCam)
    mod = load_script()
    assert mod.main(["--recognize", "--data", str(tmp_path)]) == 1
    assert "inte installerad" in capsys.readouterr().out


def test_camera_test_reads_settings_file(tmp_path, monkeypatch):
    monkeypatch.delenv("TVATT_VISION_SURE", raising=False)
    monkeypatch.delenv("TVATT_CAMERA", raising=False)
    (tmp_path / "tvatt.env").write_text("# own settings\nTVATT_VISION_SURE=0.9\nTVATT_CAMERA=2\n")
    seen = []

    class Cam(FakeCam):
        def __init__(self, index):
            seen.append(index)
            super().__init__(index)

    monkeypatch.setattr(scanner, "CvSource", Cam)
    mod = load_script()
    monkeypatch.setattr(mod, "release_app_camera", lambda base: None)
    mod.main(["--seconds", "0.1", "--data", str(tmp_path), "--out", str(tmp_path / "b.jpg")])
    import os

    assert seen == [2] and os.environ["TVATT_VISION_SURE"] == "0.9"
    monkeypatch.delenv("TVATT_VISION_SURE")
    monkeypatch.delenv("TVATT_CAMERA")

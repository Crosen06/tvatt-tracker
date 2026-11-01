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

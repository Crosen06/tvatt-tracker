"""Tests for the Pi shell scripts, using fake wlopm/chromium commands on PATH."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "deploy"


@pytest.fixture
def stub_server():
    state = {"body": {"wash": None, "server_now": "2026-11-01T12:00:00+00:00"}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            data = json.dumps(state["body"], separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def fake_bin(tmp_path, name, log):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    exe = bin_dir / name
    exe.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    exe.chmod(0o755)
    return bin_dir


def run(script, env, *args):
    return subprocess.run([str(DEPLOY / script), *args], env=env, capture_output=True, text=True, timeout=20)


def test_wake_on_done_turns_screen_on(tmp_path, stub_server):
    state, base = stub_server
    log = tmp_path / "wlopm.log"
    env = {"PATH": f"{fake_bin(tmp_path, 'wlopm', log)}:/usr/bin:/bin", "TVATT_BASE": base, "HOME": str(tmp_path)}

    state["body"]["wash"] = {"id": 1, "is_done": False}
    assert run("wake-on-done.sh", env, "--once").returncode == 0
    assert not log.exists()

    state["body"]["wash"] = {"id": 1, "is_done": True}
    assert run("wake-on-done.sh", env, "--once").returncode == 0
    assert log.read_text().strip() == "--on *"


def test_kiosk_clears_crash_flag_and_launches(tmp_path):
    log = tmp_path / "chromium.log"
    bin_dir = fake_bin(tmp_path, "chromium", log)
    prefs = tmp_path / ".config" / "tvatt-kiosk" / "Default" / "Preferences"
    prefs.parent.mkdir(parents=True)
    prefs.write_text('{"profile":{"exit_type":"Crashed","exited_cleanly":false}}')
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TVATT_BASE": "http://127.0.0.1:9",
        "TVATT_WAIT_SECONDS": "0",
        "TVATT_KIOSK_ONCE": "1",
    }
    r = run("kiosk.sh", env)
    assert r.returncode == 0, r.stderr
    assert '"exit_type":"Normal"' in prefs.read_text()
    assert '"exited_cleanly":true' in prefs.read_text()
    args = log.read_text()
    for flag in ("--kiosk", "--no-first-run", "--noerrdialogs", "http://127.0.0.1:9/?kiosk=1"):
        assert flag in args


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def update_env(tmp_path):
    log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("git", "systemctl", "pkill", "pip", "curl"):
        exe = bin_dir / name
        exe.write_text(f'#!/bin/sh\necho "{name} $@" >> "{log}"\n')
        exe.chmod(0o755)
    sudo = bin_dir / "sudo"
    sudo.write_text('#!/bin/sh\nexec "$@"\n')
    sudo.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path),
        "TVATT_UNIT_PATH": str(tmp_path / "tvatt.service"), "TVATT_PIP": str(bin_dir / "pip"),
    }
    return env, log


def test_update_reinstalls_changed_unit(tmp_path):
    env, log = update_env(tmp_path)
    unit = tmp_path / "tvatt.service"
    unit.write_text("[Service]\nEnvironment=TVATT_DATA=/home/pi/min-data\nold\n")
    r = run("update.sh", env)
    assert r.returncode == 0, r.stderr
    calls = log.read_text()
    assert "systemctl daemon-reload" in calls and "systemctl restart tvatt.service" in calls
    text = unit.read_text()
    assert "SupplementaryGroups=video" in text
    assert "Environment=TVATT_DATA=/home/pi/min-data" in text  # keeps the data dir it was installed with
    assert "EnvironmentFile=-/home/pi/min-data/tvatt.env" in text  # own settings survive updates
    assert "@REPO@" not in text

    log.write_text("")
    r = run("update.sh", env)
    assert r.returncode == 0, r.stderr
    assert "daemon-reload" not in log.read_text()
    assert "systemctl restart tvatt.service" in log.read_text()


def test_service_has_video_group():
    assert "SupplementaryGroups=video" in (DEPLOY / "tvatt.service").read_text()


def test_requirements_include_opencv():
    reqs = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    assert "opencv-python-headless>=4.8" in reqs


def test_check_kitchen_offline_and_fake_camera(tmp_path):
    import cv2

    from tests.kitchen.barcode_images import ean13_frame

    cam, fake = tmp_path / "cam", tmp_path / "fake"
    cam.mkdir()
    fake.mkdir()
    cv2.imwrite(str(cam / "a.png"), ean13_frame("4006381333931"))
    env = {
        "PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "TVATT_FAKE_CAMERA": str(cam), "TVATT_FAKE_FETCH_DIR": str(fake),
        "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
    }
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_kitchen.py"), "--base", "http://127.0.0.1:9", "--camera-seconds", "5"],
        env=env, capture_output=True, text=True, timeout=60,
    )
    out = r.stdout
    assert r.returncode == 1, out + r.stderr
    assert "✓ Kamera" in out and "4006381333931" in out
    assert "✗ Open Food Facts" in out and "✗ ICA-sök" in out
    assert "Traceback" not in out + r.stderr


def test_update_installs_optional_zxing(tmp_path):
    env, log = update_env(tmp_path)
    r = run("update.sh", env)
    assert r.returncode == 0, r.stderr
    assert "zxing-cpp" in log.read_text()
    assert "zxing-cpp" in (DEPLOY / "install.sh").read_text()


def test_update_fetches_model_but_survives_failure(tmp_path):
    env, log = update_env(tmp_path)
    r = run("update.sh", env)
    assert r.returncode == 0, r.stderr
    assert "curl" in log.read_text()  # the stub writes nothing, so the checksum fails …
    assert "Bildmodellen kunde inte hämtas" in r.stdout  # … and the update still finishes


def _model_env(tmp_path, content: bytes, sha: str | None = None):
    import hashlib

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "curl.log"
    src = tmp_path / "model.bin"
    src.write_bytes(content)
    curl = bin_dir / "curl"
    curl.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nwhile [ "$1" != "-o" ]; do shift; done\ncp "{src}" "$2"\n')
    curl.chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "TVATT_MODEL_SHA256": sha or hashlib.sha256(content).hexdigest()}
    return env, log


def test_get_model_downloads_once(tmp_path):
    data = tmp_path / "data"
    env, log = _model_env(tmp_path, b"model bytes")
    r = run("get-model.sh", env, str(data))
    assert r.returncode == 0, r.stderr
    assert (data / "models" / "mobilenetv2.onnx").read_bytes() == b"model bytes"
    r = run("get-model.sh", env, str(data))
    assert r.returncode == 0 and "finns redan" in r.stdout
    assert len(log.read_text().splitlines()) == 1  # not downloaded again
    assert [p.name for p in (data / "models").iterdir()] == ["mobilenetv2.onnx"]


def test_get_model_refuses_wrong_checksum(tmp_path):
    data = tmp_path / "data"
    env, _ = _model_env(tmp_path, b"tampered", sha="0" * 64)
    r = run("get-model.sh", env, str(data))
    assert r.returncode == 1 and "fel kontrollsumma" in r.stderr
    assert list((data / "models").iterdir()) == []  # no model and no temp file left


def test_model_checksum_matches_app():
    from app.kitchen import vision

    assert vision.MODEL_SHA256 in (DEPLOY / "get-model.sh").read_text()

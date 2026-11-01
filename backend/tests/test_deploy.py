"""Tests for the Pi shell scripts, using fake wlopm/chromium commands on PATH."""

import json
import os
import subprocess
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

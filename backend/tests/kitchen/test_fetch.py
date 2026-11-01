import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.kitchen import fetch
from app.kitchen.fetch import FetchError


@pytest.mark.parametrize("url", [
    "ftp://example.se/x", "http://localhost/", "http://127.0.0.1:8000/", "http://192.168.1.5/",
    "http://10.0.0.1/", "http://[::1]/", "http://169.254.1.1/", "javascript:alert(1)", "", "https:///nohost",
])
def test_check_url_rejects(url):
    with pytest.raises(FetchError):
        fetch.check_url(url)


def test_check_url_accepts_public_ip():
    fetch.check_url("https://93.184.215.14/recept/")


@pytest.fixture
def local_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/big":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"x" * (4 * 1024 * 1024))
            elif self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://192.168.0.1/admin")
                self.end_headers()
            elif self.path == "/missing":
                self.send_response(404)
                self.end_headers()
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write("hej åäö".encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def allow_only_loopback(monkeypatch):
    real = fetch.check_url

    def check(url):
        if url.startswith("http://127.0.0.1:"):
            return
        real(url)

    monkeypatch.setattr(fetch, "check_url", check)


def test_get_enforces_max_bytes(local_server, monkeypatch):
    allow_only_loopback(monkeypatch)
    assert fetch.get(local_server + "/ok") == "hej åäö".encode()
    with pytest.raises(FetchError, match="för stor"):
        fetch.get(local_server + "/big")


def test_get_rejects_redirect_to_private(local_server, monkeypatch):
    allow_only_loopback(monkeypatch)
    with pytest.raises(FetchError):
        fetch.get(local_server + "/redirect")


def test_get_404_message(local_server, monkeypatch):
    allow_only_loopback(monkeypatch)
    with pytest.raises(FetchError, match="finns inte"):
        fetch.get(local_server + "/missing")


def test_fake_fetch_dir(tmp_path, monkeypatch):
    url = "https://www.ica.se/recept/?q=kyckling"
    (tmp_path / f"{fetch.fake_name(url)}.html").write_text("fake")
    monkeypatch.setenv("TVATT_FAKE_FETCH_DIR", str(tmp_path))
    assert fetch.get(url) == b"fake"
    with pytest.raises(FetchError):
        fetch.get("https://www.ica.se/recept/annat-1/")

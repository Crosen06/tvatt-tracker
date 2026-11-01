"""The one place that fetches from the internet (ica.se, recipe sites, Open Food Facts).

Callers use `fetch.get(...)` (module attribute) so tests can replace it.

Test hook: when TVATT_FAKE_FETCH_DIR is set, get() reads `<dir>/<fake_name(url)>.*` instead of the network.
"""

import hashlib
import ipaddress
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

USER_AGENT = "Tvatt-tracker-Kok/1.0 (+https://github.com/Crosen06/tvatt-tracker)"
MAX_BYTES = 3_000_000


class FetchError(Exception):
    """Message is Swedish and safe to show to the user."""


def fake_name(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _host(url: str) -> str:
    return urlsplit(url).hostname or url


def check_url(url: str) -> None:
    """Allow only http(s) URLs that point at public addresses (not the home network)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        raise FetchError("Länken ser inte ut som en webbadress.")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise FetchError("Länken ser inte ut som en webbadress.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        raise FetchError(f"Kunde inte nå {parts.hostname}. Kontrollera Pi:ns internetanslutning.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise FetchError("Länken går inte att hämta.")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_CheckedRedirect)


def _fake(url: str, folder: str) -> bytes:
    for p in Path(folder).glob(fake_name(url) + ".*"):
        return p.read_bytes()
    raise FetchError(f"Kunde inte nå {_host(url)}. Kontrollera Pi:ns internetanslutning.")


def get(url: str, *, timeout: float = 10, max_bytes: int = MAX_BYTES, accept: str = "text/html,application/json") -> bytes:
    fake_dir = os.environ.get("TVATT_FAKE_FETCH_DIR")
    if fake_dir:
        return _fake(url, fake_dir)
    check_url(url)
    host = _host(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "sv"})
    try:
        with _opener.open(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FetchError(f"Sidan finns inte ({host}).")
        raise FetchError(f"{host} svarade med fel {e.code}. Försök igen senare.")
    except FetchError:
        raise
    except (urllib.error.URLError, OSError, ValueError):
        raise FetchError(f"Kunde inte nå {host}. Kontrollera Pi:ns internetanslutning.")
    if len(data) > max_bytes:
        raise FetchError(f"Sidan från {host} är för stor.")
    return data

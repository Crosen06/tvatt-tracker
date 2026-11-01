"""Check the parts of the kitchen that can only be tried on the Pi: webcam, Open Food Facts and ica.se.

Run on the Pi (from the repo folder):

    .venv/bin/python scripts/check_kitchen.py

Options: --base http://localhost (the running app), --camera-seconds 15, --skip-camera.
Exits 0 when everything works, 1 otherwise. Never changes any data except starting/stopping the camera.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.kitchen import fetch, ica, products, recipe_import  # noqa: E402

OK, FAIL, NOTE = "✓", "✗", "!"
failures = 0


def say(mark: str, what: str, detail: str = "") -> None:
    global failures
    if mark == FAIL:
        failures += 1
    print(f"{mark} {what}" + (f": {detail}" if detail else ""), flush=True)


def _post(base: str, path: str):
    req = urllib.request.Request(base + path, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.load(r)


def server_up(base: str) -> bool:
    try:
        _get(base, "/api/health")
        return True
    except (OSError, ValueError):
        return False


def check_camera_via_server(base: str, seconds: float) -> None:
    try:
        _post(base, "/api/scan/start")
    except urllib.error.HTTPError as e:
        detail = json.load(e).get("detail", str(e)) if e.code == 503 else f"fel {e.code}"
        return say(FAIL, "Kamera", detail)
    first = _get(base, "/api/scan/last")["seq"]
    print(f"  Håll upp en vara med streckkod mot kameran ({int(seconds)} s)…", flush=True)
    code = None
    end = time.time() + seconds
    while time.time() < end and code is None:
        last = _get(base, "/api/scan/last")
        if last["error"]:
            break
        if last["seq"] > first:
            code = last["code"]
        time.sleep(0.3)
    last = _get(base, "/api/scan/last")
    _post(base, "/api/scan/stop")
    report_camera(code, last["error"])


def check_camera_direct(seconds: float) -> None:
    from app.kitchen.scanner import CameraUnavailable, Scanner, default_source_factory

    codes = []
    scanner = Scanner(default_source_factory, codes.append)
    try:
        scanner.start()
    except CameraUnavailable as e:
        return say(FAIL, "Kamera", str(e))
    print(f"  Håll upp en vara med streckkod mot kameran ({int(seconds)} s)…", flush=True)
    end = time.time() + seconds
    while time.time() < end and not codes and scanner.running:
        time.sleep(0.2)
    error = scanner.error
    scanner.stop()
    report_camera(codes[0] if codes else None, error)


def report_camera(code, error) -> None:
    if error:
        say(FAIL, "Kamera", error)
    elif code:
        say(OK, "Kamera", f"läste streckkoden {code}")
    else:
        say(OK, "Kamera", "kameran går, men ingen streckkod lästes. Prova med mer ljus eller håll varan 15–25 cm bort.")


def check_off() -> None:
    try:
        p = products.lookup("7310865004703")
    except fetch.FetchError as e:
        return say(FAIL, "Open Food Facts", str(e))
    say(OK, "Open Food Facts", p.name if p else "tjänsten svarar (testvaran fanns inte)")


def check_ica() -> str | None:
    try:
        hits = ica.search("kyckling")
    except fetch.FetchError as e:
        say(FAIL, "ICA-sök", str(e))
        return None
    if not hits:
        say(FAIL, "ICA-sök", "hittade inga recept – ica.se har troligen ändrat sin sida")
        return None
    say(OK, "ICA-sök", f"{len(hits)} recept för ”kyckling”")
    return hits[0]["url"]


def check_import(url: str) -> None:
    try:
        r = recipe_import.import_url(url)
    except fetch.FetchError as e:
        return say(FAIL, "ICA-import", str(e))
    except recipe_import.NoRecipe:
        return say(FAIL, "ICA-import", f"hittade ingen receptdata på {url}")
    say(OK, "ICA-import", f"{r.title} ({len(r.ingredients)} ingredienser, {len(r.steps)} steg)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost")
    ap.add_argument("--camera-seconds", type=float, default=15)
    ap.add_argument("--skip-camera", action="store_true")
    args = ap.parse_args(argv)

    if not args.skip_camera:
        try:
            if server_up(args.base):
                check_camera_via_server(args.base, args.camera_seconds)
            else:
                print(f"  (appen svarar inte på {args.base}, provar kameran direkt)", flush=True)
                check_camera_direct(args.camera_seconds)
        except Exception as e:  # noqa: BLE001 - report, don't crash
            say(FAIL, "Kamera", str(e))
    check_off()
    url = check_ica()
    if url:
        check_import(url)
    else:
        say(NOTE, "ICA-import", "hoppades över eftersom sökningen inte gav något")
    print("Allt fungerar." if failures == 0 else f"{failures} del(ar) fungerar inte. Se raderna med {FAIL}.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Show what the webcam really gives the barcode reader, and save a full-size picture.

Run on the Pi (from the repo folder) while the scan sheet in the app is closed:

    .venv/bin/python scripts/camera_test.py

Options: --seconds 15, --size 1920x1080, --camera 0, --out ~/tvatt-data/kamera-test.jpg, --recognize.
Prints the resolution, picture format, frame rate, focus and sharpness, tries to read a barcode
the whole time and saves the sharpest frame so it can be looked at on a computer.

With --recognize it also loads the image model and, once a second, prints the three learned items
the picture looks most like, with their scores. Use it to tune TVATT_VISION_SURE / _MAYBE.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.kitchen import scanner, vision  # noqa: E402

DECISION = {"sure": "säker", "maybe": "osäker", "none": "ingen träff"}


def load_gallery(data: Path, model_id: str):
    """Learned pictures for the active model, and item names, straight from the database."""
    gallery, names = vision.Gallery(), {}
    db = data / "tvatt.db"
    if not db.is_file():
        return gallery, names
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT m.item_id, m.embedding, i.name FROM item_image m JOIN item i ON i.id=m.item_id "
            "WHERE i.archived=0 AND m.model=?", (model_id,)
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    finally:
        conn.close()
    gallery.set((r[0], vision.from_blob(r[1])) for r in rows)
    names = {r[0]: r[2] for r in rows}
    return gallery, names


def release_app_camera(base: str) -> None:
    """The app holds the camera while scanning; ask it to let go (fine if the app is not running)."""
    try:
        req = urllib.request.Request(base + "/api/scan/stop", data=b"{}", method="POST",
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3).read()
        time.sleep(1)
    except Exception:  # noqa: BLE001
        pass


def sharpness(cv2, gray) -> float:
    """Variance of the Laplacian in the middle of the picture: higher is sharper."""
    h, w = gray.shape
    mid = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    return float(cv2.Laplacian(mid, cv2.CV_64F).var())


def main(argv=None) -> int:
    data = Path(os.environ.get("TVATT_DATA", Path.home() / "tvatt-data"))
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--size", default="", help="e.g. 1280x720 (default: as the app, normally 1920x1080)")
    ap.add_argument("--camera", type=int, default=int(os.environ.get("TVATT_CAMERA", "0")))
    ap.add_argument("--out", type=Path, default=data / "kamera-test.jpg")
    ap.add_argument("--base", default="http://localhost")
    ap.add_argument("--recognize", action="store_true", help="also show which learned items the picture looks like")
    ap.add_argument("--data", type=Path, default=data, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.size:
        os.environ["TVATT_CAMERA_SIZE"] = args.size

    try:
        cv2 = scanner._load_cv2()
    except ImportError:
        print("✗ OpenCV saknas. Kör ./deploy/update.sh först.")
        return 1
    embedder = gallery = None
    names: dict = {}
    if args.recognize:
        embedder, message = vision.load_embedder(args.data)
        if embedder is None:
            print(f"✗ {message}")
            return 1
        gallery, names = load_gallery(args.data, embedder.model_id)
        print(f"Bildmodell: {embedder.model_id}, {getattr(embedder, 'dim', '?')} värden per bild, "
              f"{len(gallery)} inlärda bilder av {len(set(names))} varor. Gränser: {vision.thresholds()}")
    release_app_camera(args.base)
    try:
        source = scanner.CvSource(args.camera)
    except scanner.CameraUnavailable as e:
        print(f"✗ {e} (Är skanningen öppen i appen? Stäng den och prova igen.)")
        return 1

    try:
        for _ in range(10):  # let exposure settle
            source.read()
        info = source.info()
        print(f"Kamera {args.camera}: {info['width']}×{info['height']} {info['format']}, "
              f"autofokus={info['autofocus']}, avkodare: {scanner.decoder_name()}")
        if info["width"] < 1280:
            print(f"! Kameran ger bara {info['width']}×{info['height']}. Det räcker sällan för vanliga streckkoder.")
        print(f"Håll upp en streckkod mot kameran ({int(args.seconds)} s)…", flush=True)

        best, best_score, codes, frames = None, -1.0, [], 0
        start = next_guess = time.time()
        while time.time() - start < args.seconds:
            frame = source.read()
            if frame is None:
                continue
            frames += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = sharpness(cv2, gray)
            if score > best_score:
                best, best_score = frame, score
            for code in scanner.decode(frame):
                if code not in codes:
                    codes.append(code)
                    print(f"✓ Läste {code}", flush=True)
            if embedder is not None and time.time() >= next_guess:
                next_guess = time.time() + 1
                t0 = time.perf_counter()
                vec = embedder.embed(vision.model_input(frame))
                ms = (time.perf_counter() - t0) * 1000
                matches = gallery.match(vec)
                shown = " · ".join(f"{names.get(i, i)} {s:.2f}" for i, s in matches) or "inga inlärda varor"
                print(f"  {shown} → {DECISION[vision.decide(matches)]} ({ms:.0f} ms)", flush=True)
        fps = frames / max(time.time() - start, 0.001)
    finally:
        source.release()

    print(f"Bilder: {frames} ({fps:.1f} per sekund inklusive avkodning), bästa skärpa: {best_score:.0f}")
    if best is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.out), best, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"Sparade den skarpaste bilden i {args.out}")
    print(json.dumps({"info": info, "codes": codes, "fps": round(fps, 1), "sharpness": round(best_score)}))
    if args.recognize:
        return 0
    if not codes:
        print("✗ Ingen streckkod lästes. Titta på bilden: är strecken suddiga, håll varan längre bort; "
              "är de pyttesmå, håll den närmare.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

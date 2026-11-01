"""Fill a running tvatt-tracker with example garments (for trying the UI).

Usage: python scripts/sample_data.py [http://localhost:8000]
Uses only the standard library + Pillow.
"""

import io
import json
import sys
import urllib.request
import uuid

from PIL import Image, ImageDraw

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

SHIRT = [(70, 60), (110, 40), (130, 55), (170, 55), (190, 40), (230, 60), (260, 110), (225, 130), (215, 110), (215, 250), (85, 250), (85, 110), (75, 130), (40, 110)]
PANTS = [(95, 40), (205, 40), (215, 260), (165, 260), (150, 120), (135, 260), (85, 260)]
TOWEL = [(60, 60), (240, 60), (240, 240), (60, 240)]
SOCK = [(120, 40), (175, 40), (175, 190), (215, 215), (215, 255), (140, 255), (120, 225)]

GARMENTS = [
    # person, name, shape, rgb, temp, color, spin, care, dry, in_basket
    (1, "Svart hoodie", SHIRT, (38, 40, 48), 40, "dark", 1200, "normal", True, True),
    (1, "Mörka jeans", PANTS, (44, 62, 102), 40, "dark", 1000, "normal", False, True),
    (1, "Vit t-shirt", SHIRT, (245, 245, 240), 60, "white", 1400, "normal", True, False),
    (1, "Träningströja", SHIRT, (30, 50, 80), 40, "dark", 800, "synthetic", False, True),
    (1, "Ullsockor", SOCK, (120, 100, 90), 30, "dark", 600, "wool", False, False),
    (1, "Grå mjukisbyxor", PANTS, (95, 98, 105), 40, "dark", 1200, "normal", True, False),
    (2, "Rosa blus", SHIRT, (232, 150, 170), 30, "colored", 800, "delicate", False, True),
    (2, "Beige kofta", SHIRT, (220, 200, 165), 30, "light", 800, "wool", False, False),
    (2, "Svart klänning", SHIRT, (25, 25, 30), 40, "dark", 800, "synthetic", False, True),
    (2, "Vita lakan", TOWEL, (250, 250, 250), 60, "white", 1400, "normal", True, True),
    (3, "Badlakan", TOWEL, (240, 240, 235), 60, "white", 1400, "normal", True, True),
    (3, "Röd skjorta", SHIRT, (190, 40, 45), 40, "colored", 1000, "normal", True, False),
    (3, "Arbetsbyxor", PANTS, (55, 60, 50), 60, "dark", 1200, "normal", True, True),
    (3, "Blå skjorta", SHIRT, (150, 185, 225), 40, "light", 1000, "normal", True, False),
]


def photo(shape, rgb) -> bytes:
    img = Image.new("RGB", (300, 300), (214, 220, 228))
    d = ImageDraw.Draw(img)
    d.polygon(shape, fill=rgb, outline=(120, 125, 135))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue()


def post_multipart(url, fields, file_bytes):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="p.jpg"\r\n'
        "Content-Type: image/jpeg\r\n\r\n".encode() + file_bytes + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(url, data=b"".join(parts), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main():
    for person, name, shape, rgb, temp, color, spin, care, dry, basket in GARMENTS:
        g = post_multipart(
            f"{BASE}/api/garments",
            {"person_id": person, "name": name, "max_temp": temp, "color": color,
             "max_spin": spin, "care": care, "tumble_dry": str(dry).lower()},
            photo(shape, rgb),
        )
        if basket:
            post_json(f"{BASE}/api/garments/{g['id']}/basket", {"in_basket": True})
    print(f"Added {len(GARMENTS)} garments to {BASE}")


if __name__ == "__main__":
    main()

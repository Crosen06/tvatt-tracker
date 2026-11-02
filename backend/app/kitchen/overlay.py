"""Draw the guide box, the item's outline and its score into the camera preview (spec 2026-11-02 §7.2).

Drawn on the Pi into the MJPEG picture itself, so the outline always lines up with the picture.
Text goes through Pillow, since OpenCV's built-in fonts have no å, ä or ö.
"""

from pathlib import Path

FRESH = 1.5  # seconds an analysis is shown
FONT_PATH = Path(__file__).resolve().parents[1] / "static" / "fonts" / "poppins-medium.woff"
WHITE = (255, 255, 255)
INK = (24, 24, 24)
COLOURS = {"sure": (113, 191, 47), "maybe": (61, 179, 242), "none": WHITE}  # BGR of #2fbf71, #f2b33d
HINT = "Håll varan i rutan"
CORNER = 0.18  # length of the box's corner marks, as a share of its side

_fonts: dict = {}


def _np():
    import numpy as np  # noqa: PLC0415

    return np


def _cv2():
    import cv2  # noqa: PLC0415

    return cv2


def label_text(analysis: dict) -> str:
    label, pct = analysis.get("label") or "", round(float(analysis.get("score") or 0) * 100)
    decision = analysis.get("decision")
    if decision == "sure" and label:
        return f"{label} {pct} %"
    if decision == "maybe" and label:
        return f"{label}? {pct} %"
    if analysis.get("has_gallery") and label:
        return f"Okänd ({label} {pct} %)"
    return "Okänd"


def _font(size: int):
    if size not in _fonts:
        from PIL import ImageFont  # noqa: PLC0415

        try:
            _fonts[size] = ImageFont.truetype(str(FONT_PATH), size)
        except OSError:
            try:
                _fonts[size] = ImageFont.load_default(size)
            except TypeError:  # Pillow < 10.1
                _fonts[size] = ImageFont.load_default()
    return _fonts[size]


def _text(img, text: str, x: int, y: int, size: int, fill, ink, *, below: bool = False) -> None:
    """A rounded label with `text`, its bottom-centre at (x, y) (top-centre when `below`), kept inside img."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    np = _np()
    font = _font(size)
    left, top, right, bottom = font.getbbox(text)
    pad = max(3, size // 3)
    w, h = right - left + 2 * pad, bottom - top + 2 * pad
    ih, iw = img.shape[:2]
    w, h = min(w, iw), min(h, ih)
    x0 = int(min(max(0, x - w // 2), iw - w))
    y0 = int(y if below else y - h)
    y0 = min(max(0, y0), ih - h)
    region = img[y0:y0 + h, x0:x0 + w]
    patch = Image.fromarray(np.ascontiguousarray(region[:, :, ::-1])).convert("RGBA")
    layer = Image.new("RGBA", patch.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=(*fill[::-1], 230))
    draw.text((pad - left, pad - top), text, font=font, fill=(*ink[::-1], 255))
    out = Image.alpha_composite(patch, layer).convert("RGB")
    img[y0:y0 + h, x0:x0 + w] = np.asarray(out)[:, :, ::-1]


def _corners(img, box, scale_x, scale_y) -> tuple[int, int, int, int]:
    cv2 = _cv2()
    bx, by, bw, bh = box
    x0, y0 = round(bx * scale_x), round(by * scale_y)
    x1, y1 = round((bx + bw) * scale_x), round((by + bh) * scale_y)
    n = max(4, round((x1 - x0) * CORNER))
    for (cx, cy), (dx, dy) in (((x0, y0), (1, 1)), ((x1, y0), (-1, 1)), ((x0, y1), (1, -1)), ((x1, y1), (-1, -1))):
        cv2.line(img, (cx, cy), (cx + dx * n, cy), WHITE, 2, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * n), WHITE, 2, cv2.LINE_AA)
    return x0, y0, x1, y1


def draw(img, frame_size, box, analysis: dict | None, now: float):
    """Draw on `img` (a scaled copy of a picture of `frame_size` = (h, w)) and return it."""
    cv2, np = _cv2(), _np()
    ih, iw = img.shape[:2]
    sx, sy = iw / frame_size[1], ih / frame_size[0]
    size = max(10, round(16 * iw / 640))
    x0, _, x1, y1 = _corners(img, box, sx, sy)
    fresh = bool(analysis and analysis.get("found") and analysis.get("contour") and now - analysis["at"] <= FRESH)
    if not fresh:
        _text(img, HINT, (x0 + x1) // 2, y1 + 4, size, INK, WHITE, below=True)
        return img
    colour = COLOURS.get(analysis.get("decision"), WHITE)
    pts = np.array([(round(x * sx), round(y * sy)) for x, y in analysis["contour"]], np.int32)
    cv2.polylines(img, [pts], True, colour, 3, cv2.LINE_AA)
    top = int(pts[:, 1].min())
    cx = int((pts[:, 0].min() + pts[:, 0].max()) // 2)
    if top >= size * 2:
        _text(img, label_text(analysis), cx, top - 4, size, colour, INK)
    else:  # no room above: inside, under the top edge
        _text(img, label_text(analysis), cx, top + 4, size, colour, INK, below=True)
    return img

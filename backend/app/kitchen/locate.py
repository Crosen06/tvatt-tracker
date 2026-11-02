"""Find the item held up in the guide box (spec: docs/specs/2026-11-02-varans-kontur-design.md §4).

The person holding the item fills most of the camera picture, so the whole picture says more about
them than about the item. The item is held in a square guide box in the middle; GrabCut separates it
from what is around it (shirt, kitchen), with faces as forced background. The model then sees only
the item, on neutral grey. OpenCV and numpy are imported lazily so the app runs without them.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

BOX_DEFAULT = 0.6  # side of the guide box, as a share of the picture's shorter side
BOX_MIN, BOX_MAX = 0.3, 0.9
MARGIN = 0.2  # ring around the box, as a share of its side, that shows what is *not* the item
WORK_SIZE = 200  # GrabCut runs on the work area scaled to at most this many pixels a side
ITERATIONS = 3
MIN_AREA, MAX_AREA = 0.04, 0.92  # share of the box a cut-out must cover to count as the item
PAD = 0.1  # space around the item in the model's picture
DILATE = 3  # px of the picture kept around the item's edge
GREY = (124, 116, 104)  # BGR ImageNet mean: ≈ 0 after normalisation
INPUT_SIZE = 224

FACE_FILE = "face_yunet.onnx"
FACE_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
FACE_WIDTH = 320
FACE_SCORE = 0.7
FACE_GROW = 0.15

_face_warned = False


def _np():
    import numpy as np  # noqa: PLC0415

    return np


def _cv2():
    import cv2  # noqa: PLC0415

    return cv2


def box_fraction() -> float:
    try:
        value = float(os.environ.get("TVATT_VISION_BOX", BOX_DEFAULT))
    except ValueError:
        return BOX_DEFAULT
    if value != value:  # NaN
        return BOX_DEFAULT
    return min(BOX_MAX, max(BOX_MIN, value))


def guide_box(shape, fraction: float | None = None) -> tuple[int, int, int, int]:
    """(x, y, w, h) of the centred square the item is held in; `shape` is (h, w[, c])."""
    h, w = shape[:2]
    side = max(1, int(min(h, w) * (box_fraction() if fraction is None else fraction)))
    return (w - side) // 2, (h - side) // 2, side, side


@dataclass
class Located:
    box: tuple[int, int, int, int]
    contour: list[tuple[int, int]] | None  # the item's outline in picture coordinates
    found: bool
    image: object  # 224×224 BGR uint8: what the model sees and what is saved
    area: float  # share of the box covered by the item (0 when not found)


def _clip_rect(x0, y0, x1, y1, w, h):
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def _cut(frame, box, faces):
    """The item's mask in the work area, or None. Returns (mask, (x0, y0), contour, share)."""
    cv2, np = _cv2(), _np()
    h, w = frame.shape[:2]
    bx, by, bs, _ = box
    m = int(bs * MARGIN)
    x0, y0, x1, y1 = _clip_rect(bx - m, by - m, bx + bs + m, by + bs + m, w, h)
    rw, rh = x1 - x0, y1 - y0
    scale = min(1.0, WORK_SIZE / max(rw, rh))
    sw, sh = max(1, round(rw * scale)), max(1, round(rh * scale))
    if min(sw, sh) < 16:
        return None
    small = cv2.resize(frame[y0:y1, x0:x1], (sw, sh), interpolation=cv2.INTER_AREA)

    def to_small(x, y):
        return round((x - x0) * scale), round((y - y0) * scale)

    mask = np.full((sh, sw), cv2.GC_BGD, np.uint8)
    (ax, ay), (az, aw) = to_small(bx, by), to_small(bx + bs, by + bs)
    mask[max(ay, 0):aw, max(ax, 0):az] = cv2.GC_PR_FGD
    for fx, fy, fw, fh in faces:
        (fx0, fy0), (fx1, fy1) = to_small(fx, fy), to_small(fx + fw, fy + fh)
        mask[max(fy0, 0):max(fy1, 0), max(fx0, 0):max(fx1, 0)] = cv2.GC_BGD
    mask[0, :] = mask[-1, :] = cv2.GC_BGD
    mask[:, 0] = mask[:, -1] = cv2.GC_BGD
    box_cells = int((mask[max(ay, 0):aw, max(ax, 0):az] >= 0).sum())
    if not (mask == cv2.GC_PR_FGD).any() or box_cells == 0:
        return None

    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, None, bgd, fgd, ITERATIONS, cv2.GC_INIT_WITH_MASK)
    fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    inside = np.zeros_like(fg)
    inside[max(ay, 0):aw, max(ax, 0):az] = 1
    fg = cv2.morphologyEx(fg & inside, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    biggest = max(contours, key=cv2.contourArea)
    filled = np.zeros_like(fg)
    cv2.drawContours(filled, [biggest], -1, 1, thickness=cv2.FILLED)
    share = float(filled.sum()) / box_cells
    if not MIN_AREA <= share <= MAX_AREA:
        return None
    approx = cv2.approxPolyDP(biggest, 0.01 * cv2.arcLength(biggest, True), True).reshape(-1, 2)
    contour = [
        (min(w - 1, max(0, round(x0 + px / scale))), min(h - 1, max(0, round(y0 + py / scale))))
        for px, py in approx.tolist()
    ]
    full = cv2.resize(filled, (rw, rh), interpolation=cv2.INTER_NEAREST)
    return full, (x0, y0), contour, share


def _item_image(frame, mask, origin):
    """The item on neutral grey, in a square around it, scaled to 224×224."""
    cv2, np = _cv2(), _np()
    h, w = frame.shape[:2]
    x0, y0 = origin
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * DILATE + 1, 2 * DILATE + 1))
    mask = cv2.dilate(mask, k)
    full = np.zeros((h, w), np.uint8)
    full[y0:y0 + mask.shape[0], x0:x0 + mask.shape[1]] = mask
    rx, ry, rw, rh = cv2.boundingRect(mask)
    rx, ry = rx + x0, ry + y0
    side = min(max(h, w), max(1, int(max(rw, rh) * (1 + 2 * PAD))))
    cx, cy = rx + rw / 2, ry + rh / 2
    sx = int(min(max(0, cx - side / 2), max(0, w - side)))
    sy = int(min(max(0, cy - side / 2), max(0, h - side)))
    crop = frame[sy:sy + side, sx:sx + side].copy()
    crop[full[sy:sy + side, sx:sx + side] == 0] = GREY
    return _square_resize(crop)


def _square_resize(img):
    """Pad to a square with grey (when clipped by the picture's edge), then scale to 224×224."""
    cv2 = _cv2()
    h, w = img.shape[:2]
    if h != w:
        side = max(h, w)
        top, left = (side - h) // 2, (side - w) // 2
        img = cv2.copyMakeBorder(img, top, side - h - top, left, side - w - left, cv2.BORDER_CONSTANT, value=GREY)
    return cv2.resize(img, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)


def _box_image(frame, box, faces):
    """Fallback: the whole guide box, with faces grey."""
    bx, by, bs, _ = box
    crop = frame[by:by + bs, bx:bx + bs].copy()
    for fx, fy, fw, fh in faces:
        x0, y0, x1, y1 = _clip_rect(fx - bx, fy - by, fx + fw - bx, fy + fh - by, crop.shape[1], crop.shape[0])
        if x1 > x0 and y1 > y0:
            crop[y0:y1, x0:x1] = GREY
    return _square_resize(crop)


def locate(frame, faces=()) -> Located:
    """Where the item in the guide box is, and the picture the model should see. Never raises on odd input."""
    cv2 = _cv2()
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    faces = [tuple(int(v) for v in f) for f in faces]
    box = guide_box(frame.shape)
    try:
        cut = _cut(frame, box, faces)
    except Exception:  # noqa: BLE001  - GrabCut can fail on odd pictures; fall back to the box
        log.debug("GrabCut failed", exc_info=True)
        cut = None
    if cut is not None:
        mask, origin, contour, share = cut
        return Located(box, contour, True, _item_image(frame, mask, origin), round(share, 3))
    return Located(box, None, False, _box_image(frame, box, faces), 0.0)


class FaceFinder:
    """Faces in the picture (YuNet via cv2.FaceDetectorYN), grown a little, in picture coordinates."""

    def __init__(self, path: Path):
        cv2, np = _cv2(), _np()
        self._det = cv2.FaceDetectorYN.create(str(path), "", (FACE_WIDTH, FACE_WIDTH), FACE_SCORE)
        self.find(np.zeros((240, FACE_WIDTH, 3), np.uint8))  # a broken file fails here, not later

    def find(self, frame) -> list[tuple[int, int, int, int]]:
        cv2 = _cv2()
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        h, w = frame.shape[:2]
        s = FACE_WIDTH / w if w > FACE_WIDTH else 1.0
        small = cv2.resize(frame, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA) if s != 1.0 else frame
        self._det.setInputSize((small.shape[1], small.shape[0]))
        _, found = self._det.detect(small)
        out = []
        for f in [] if found is None else found:
            x, y, fw, fh = (float(v) / s for v in f[:4])
            gx, gy = fw * FACE_GROW, fh * FACE_GROW
            x0, y0, x1, y1 = _clip_rect(int(x - gx), int(y - gy), int(x + fw + gx), int(y + fh + gy), w, h)
            if x1 > x0 and y1 > y0:
                out.append((x0, y0, x1 - x0, y1 - y0))
        return out


def face_model_path(data_dir: Path) -> Path:
    env = os.environ.get("TVATT_FACE_MODEL")
    return Path(env).expanduser() if env else Path(data_dir) / "models" / FACE_FILE


def load_faces(data_dir: Path) -> FaceFinder | None:
    """The face finder, or None when the model is missing or broken (faces are then not filtered)."""
    global _face_warned
    path = face_model_path(data_dir)
    if not path.is_file():
        return None
    try:
        return FaceFinder(path)
    except Exception:  # noqa: BLE001  - a broken download must not stop recognition
        if not _face_warned:
            _face_warned = True
            log.warning("Could not load the face model %s; faces are not filtered out", path, exc_info=True)
        return None

"""Recognise pantry items from the webcam picture (spec: docs/specs/2026-11-01-bildigenkanning-design.md).

A pretrained image model turns the middle of the picture into an embedding ("fingerprint"); an item is
recognised by its nearest learned pictures. Nothing here touches the database or the web layer; see
`vision_service.py` for that. OpenCV and numpy are imported lazily so the app runs without them.
"""

import os
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

MODEL_ID = "mobilenetv2-2022apr"
FAKE_ID = "histogram-v1"
MODEL_FILE = "mobilenetv2.onnx"
MODEL_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"
NOT_INSTALLED = "Bildigenkänningen är inte installerad. Kör ./deploy/update.sh."
BROKEN_MODEL = "Bildmodellen gick inte att läsa in. Kör ./deploy/update.sh."

CROP_FRACTION = 0.8  # side of the centre square, as a share of the picture's shorter side
INPUT_SIZE = 224
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

DUPLICATE = 0.97  # a new picture this close to one already learned for the item adds nothing
BACKGROUND = 0.92  # a still picture this close to the empty scene means nothing is held up
STILL_DIFF = 6.0  # mean grey-level change (0-255) between checks below which the picture is still
STILL_CHECKS = 2
QUIET_AFTER_BARCODE = 2.0  # seconds: a barcode just read wins over recognition
MAX_PER_ITEM = 40
TOKEN_LIMIT = 30
TOKEN_TTL = 600.0

CLASSIFIER_TYPES = {"Gemm", "InnerProduct", "MatMul"}
FEATURE_TYPES = {"Pooling", "Flatten", "Reshape"}


def thresholds() -> dict:
    def env(name, default):
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return default

    return {
        "sure": env("TVATT_VISION_SURE", 0.80),
        "maybe": env("TVATT_VISION_MAYBE", 0.65),
        "margin": env("TVATT_VISION_MARGIN", 0.05),
    }


def _np():
    import numpy as np  # noqa: PLC0415

    return np


def _cv2():
    import cv2  # noqa: PLC0415

    return cv2


def center_crop(frame, fraction: float = CROP_FRACTION):
    """The square in the middle of the picture, where the item is held."""
    h, w = frame.shape[:2]
    side = max(1, int(min(h, w) * fraction))
    y, x = (h - side) // 2, (w - side) // 2
    return frame[y:y + side, x:x + side]


def model_input(frame):
    """The 224×224 BGR picture the model sees; also what is saved as the learned picture."""
    cv2 = _cv2()
    crop = center_crop(frame)
    if crop.ndim == 2:
        crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    return cv2.resize(crop, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)


def unit(vec):
    np = _np()
    vec = np.asarray(vec, dtype=np.float32).ravel()
    n = float(np.linalg.norm(vec))
    return vec / n if n > 0 else vec


def to_blob(vec) -> bytes:
    return unit(vec).astype(_np().float16).tobytes()


def from_blob(blob: bytes):
    np = _np()
    return np.frombuffer(blob, dtype=np.float16).astype(np.float32)


def preprocess(img224):
    """BGR uint8 224×224 → NCHW float32, RGB, ImageNet-normalised."""
    np = _np()
    rgb = img224[:, :, ::-1].astype(np.float32) / 255.0
    rgb = (rgb - np.array(MEAN, np.float32)) / np.array(STD, np.float32)
    return np.ascontiguousarray(rgb.transpose(2, 0, 1)[np.newaxis])


def feature_layer(net) -> str | None:
    """Name of the last pooling/flatten layer before the classifier (classic OpenCV DNN engine)."""
    names = list(net.getLayerNames())
    types = []
    for name in names:
        try:
            types.append(net.getLayer(name).type)
        except Exception:  # noqa: BLE001
            types.append("")
    last_cls = max((i for i, t in enumerate(types) if t in CLASSIFIER_TYPES), default=len(names))
    candidates = [names[i] for i in range(last_cls) if types[i] in FEATURE_TYPES]
    return candidates[-1] if candidates else None


class OnnxEmbedder:
    """Penultimate-layer features of an ONNX image classifier, run with cv2.dnn."""

    model_id = MODEL_ID

    def __init__(self, path: Path, input_size: int = INPUT_SIZE):
        cv2 = _cv2()
        self.input_size = input_size
        try:  # OpenCV 5's new engine cannot return inner layers; the classic one can (4.x has only that)
            self._net = cv2.dnn.readNetFromONNX(str(path), cv2.dnn.ENGINE_CLASSIC)
        except (AttributeError, TypeError):
            self._net = cv2.dnn.readNetFromONNX(str(path))
        self.layer = feature_layer(self._net)
        self.dim = len(self.embed(_np().zeros((input_size, input_size, 3), _np().uint8)))

    def embed(self, img):
        cv2 = _cv2()
        if img.shape[:2] != (self.input_size, self.input_size):
            img = cv2.resize(img, (self.input_size, self.input_size), interpolation=cv2.INTER_AREA)
        self._net.setInput(preprocess(img))
        out = self._net.forward(self.layer) if self.layer else self._net.forward()
        return unit(out)


class HistogramEmbedder:
    """Colour histogram + tiny grey picture. For tests and development only (TVATT_FAKE_VISION=1)."""

    model_id = FAKE_ID
    dim = 8 * 4 * 4 + 64

    def embed(self, img):
        cv2, np = _cv2(), _np()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256]).ravel()
        hist = hist / max(float(hist.sum()), 1.0)
        grey = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (8, 8), interpolation=cv2.INTER_AREA).astype(np.float32)
        grey = (grey - grey.mean()) / 255.0
        return unit(np.concatenate([hist * 4.0, grey.ravel() * 0.5]))


def model_path(data_dir: Path) -> Path:
    env = os.environ.get("TVATT_VISION_MODEL")
    return Path(env).expanduser() if env else Path(data_dir) / "models" / MODEL_FILE


def load_embedder(data_dir: Path):
    """(embedder, None) when recognition can run, else (None, message for the user)."""
    if os.environ.get("TVATT_FAKE_VISION") == "1":
        try:
            _cv2()
        except ImportError:
            return None, NOT_INSTALLED
        return HistogramEmbedder(), None
    path = model_path(data_dir)
    if not path.is_file():
        return None, NOT_INSTALLED
    try:
        return OnnxEmbedder(path), None
    except Exception:  # noqa: BLE001  - a broken download must not take the app down
        return None, BROKEN_MODEL


class Gallery:
    """Embeddings of learned pictures; an item's score is its best picture's cosine similarity."""

    def __init__(self):
        np = _np()
        self._items = np.zeros(0, dtype=np.int64)
        self._mat = np.zeros((0, 0), dtype=np.float32)

    def set(self, rows) -> None:
        """rows: iterable of (item_id, vector)."""
        np = _np()
        rows = list(rows)
        self._items = np.array([r[0] for r in rows], dtype=np.int64)
        self._mat = np.stack([unit(r[1]) for r in rows]) if rows else np.zeros((0, 0), dtype=np.float32)

    def __len__(self) -> int:
        return len(self._items)

    def match(self, vec, k: int = 3) -> list[tuple[int, float]]:
        if not len(self._items) or self._mat.shape[1] != len(vec):
            return []
        sims = self._mat @ unit(vec)
        best: dict[int, float] = {}
        for item_id, s in zip(self._items.tolist(), sims.tolist()):
            if s > best.get(item_id, -2.0):
                best[item_id] = s
        return sorted(best.items(), key=lambda p: (-p[1], p[0]))[:k]


def decide(matches: list[tuple[int, float]], limits: dict | None = None) -> str:
    limits = limits or thresholds()
    if not matches:
        return "none"
    best = matches[0][1]
    second = matches[1][1] if len(matches) > 1 else -1.0
    if best >= limits["sure"] and best - second >= limits["margin"]:
        return "sure"
    return "maybe" if best >= limits["maybe"] else "none"


def cosine(a, b) -> float:
    return float(unit(a) @ unit(b))


class TokenStore:
    """Recent pictures waiting to be confirmed, by random token and by barcode."""

    def __init__(self, limit: int = TOKEN_LIMIT, ttl: float = TOKEN_TTL, clock=time.monotonic):
        self.limit, self.ttl, self._clock = limit, ttl, clock
        self._entries: OrderedDict[str, tuple[float, object]] = OrderedDict()
        self._by_code: dict[str, str] = {}
        self._lock = threading.Lock()

    def put(self, entry, code: str | None = None) -> str:
        token = uuid.uuid4().hex[:16]
        with self._lock:
            self._entries[token] = (self._clock(), entry)
            if code:
                self._by_code[code] = token
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
        return token

    def get(self, token: str):
        with self._lock:
            hit = self._entries.get(token)
            if hit is None:
                return None
            if self._clock() - hit[0] > self.ttl:
                del self._entries[token]
                return None
            return hit[1]

    def for_code(self, code: str):
        with self._lock:
            token = self._by_code.pop(code, None)
        return self.get(token) if token else None


class Watcher:
    """Decides when the automatic mode should try to recognise the picture.

    `step` returns an embedding to match when something new is held still in front of the camera,
    otherwise None. The first still scene is taken as the empty background.
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._prev = None
        self._still = 0
        self._moved = True
        self._background = None
        self._barcode_at = -1e9

    def barcode_seen(self) -> None:
        self._barcode_at = self._clock()

    def step(self, frame, embed):
        cv2, np = _cv2(), _np()
        grey = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(grey, (32, 24), interpolation=cv2.INTER_AREA).astype(np.float32)
        diff = float(np.abs(small - self._prev).mean()) if self._prev is not None else float("inf")
        self._prev = small
        if diff >= STILL_DIFF:
            self._still, self._moved = 0, True
            return None
        self._still += 1
        if self._still < STILL_CHECKS or not self._moved:
            return None
        if self._clock() - self._barcode_at < QUIET_AFTER_BARCODE:
            return None  # try again on the next check
        self._moved = False
        vec = embed(frame)
        if self._background is None or cosine(vec, self._background) >= BACKGROUND:
            self._background = vec
            return None
        return vec

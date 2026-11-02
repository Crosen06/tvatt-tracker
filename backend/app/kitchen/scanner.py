"""Read the USB webcam in a background thread and decode barcodes (spec §8).

The browser never touches the camera: the page shows `latest_jpeg()` as an MJPEG stream and
learns about codes through the `scan` SSE topic. OpenCV is imported only when scanning starts,
so the rest of the app works on a Pi without it.

Test hook: if TVATT_FAKE_CAMERA is a folder, `default_source_factory` shows the images in it
instead of a real camera (an empty folder shows a blank frame).
"""

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from app.kitchen.products import valid_gtin

NO_CAMERA = "Ingen kamera hittades. Kontrollera att webbkameran sitter i."
CAMERA_STOPPED = "Kameran slutade svara."
WIDTH, HEIGHT = 640, 480  # size of the fake camera's frames
# A normal EAN-13 is ~31 mm wide (95 bars). At 15-25 cm a webcam sees ~20-30 cm of width, so a
# 640 px frame gives under one pixel per bar and nothing decodes. Ask for full HD instead; the
# camera falls back to the nearest size it supports. Override with TVATT_CAMERA_SIZE=1280x720.
CAPTURE_SIZE = (1920, 1080)
PREVIEW_WIDTH = 640  # the on-screen preview is downscaled; decoding uses the full frame
MAX_FAILED_READS = 30
DECODE_EVERY = 3  # frames; a 30 fps webcam is decoded ~10 times a second
PREVIEW_EVERY = 3


class CameraUnavailable(Exception):
    pass


def _load_cv2():
    import cv2  # noqa: PLC0415  (optional dependency)

    return cv2


_detector = None
_detector_lock = threading.Lock()
_zxing = None  # None: not tried yet, False: unavailable or broken, else the zxingcpp module


def _load_zxing():
    """zxing-cpp reads blurry and small codes much better than OpenCV; optional."""
    global _zxing
    if _zxing is None:
        try:
            import zxingcpp  # noqa: PLC0415  (optional dependency)

            _zxing = zxingcpp
        except ImportError:
            _zxing = False
    return _zxing or None


def decoder_name() -> str:
    return "zxing-cpp" if _load_zxing() else "OpenCV"


def _decode_zxing(zx, gray) -> list[str] | None:
    global _zxing
    try:
        return [r.text for r in zx.read_barcodes(gray)]
    except Exception:  # noqa: BLE001  - an unexpected zxing build must not stop scanning
        _zxing = False
        return None


def _valid(codes) -> list[str]:
    out = []
    for code in codes or ():
        if valid_gtin(code) and code not in out:
            out.append(code)
    return out


def decode(frame) -> list[str]:
    """Valid GTIN codes found in a BGR or grey frame."""
    global _detector
    cv2 = _load_cv2()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    zx = _load_zxing()
    if zx is not None:
        codes = _decode_zxing(zx, gray)
        if codes is not None:
            return _valid(codes)
    with _detector_lock:
        if _detector is None:
            _detector = cv2.barcode.BarcodeDetector()
        if hasattr(_detector, "detectAndDecodeWithType"):
            result = _detector.detectAndDecodeWithType(gray)
            # OpenCV ≥ 4.8: (ok, infos, types, points); some builds return (infos, types, points).
            infos = result[1] if isinstance(result[0], bool) else result[0]
        else:  # pragma: no cover - older contrib builds
            result = _detector.detectAndDecode(gray)
            infos = result[1] if isinstance(result[0], bool) else result[0]
    if isinstance(infos, str):
        infos = [infos]
    return _valid(infos)


def capture_size() -> tuple[int, int]:
    raw = os.environ.get("TVATT_CAMERA_SIZE", "")
    try:
        w, h = (int(v) for v in raw.lower().split("x"))
        if w > 0 and h > 0:
            return w, h
    except ValueError:
        pass
    return CAPTURE_SIZE


class CvSource:
    def __init__(self, index: int, size: tuple[int, int] | None = None):
        cv2 = _load_cv2()
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraUnavailable(NO_CAMERA)
        width, height = size or capture_size()
        # MJPG first: over USB 2 most webcams only give full HD at a usable frame rate as MJPG.
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # ignored by fixed-focus cameras
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # decode the newest frame, not a queued one

    def info(self) -> dict:
        cv2 = _load_cv2()
        fourcc = int(self._cap.get(cv2.CAP_PROP_FOURCC))
        return {
            "width": int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "format": "".join(chr((fourcc >> 8 * i) & 0xFF) for i in range(4)).strip("\x00") or "?",
            "fps": round(self._cap.get(cv2.CAP_PROP_FPS), 1),
            "autofocus": self._cap.get(cv2.CAP_PROP_AUTOFOCUS),
        }

    def read(self):
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        self._cap.release()


class FolderSource:
    """Shows the newest image in a folder, re-checking the folder on every read (e2e tests).

    A file named `unplugged` in the folder makes reads fail, like a camera pulled out.
    """

    def __init__(self, folder, delay: float = 1 / 15):
        self.folder, self.delay = Path(folder), delay

    def read(self):
        import numpy as np

        cv2 = _load_cv2()
        time.sleep(self.delay)
        if (self.folder / "unplugged").exists():
            return None
        files = sorted(self.folder.glob("*.png"), key=lambda p: p.stat().st_mtime)
        if files:
            img = cv2.imread(str(files[-1]))
            if img is not None:
                return img
        return np.full((HEIGHT, WIDTH, 3), 180, dtype=np.uint8)

    def release(self):
        pass


def preview(frame, cv2):
    h, w = frame.shape[:2]
    if w <= PREVIEW_WIDTH:
        return frame
    return cv2.resize(frame, (PREVIEW_WIDTH, round(h * PREVIEW_WIDTH / w)), interpolation=cv2.INTER_AREA)


def default_source_factory():
    fake = os.environ.get("TVATT_FAKE_CAMERA")
    if fake and Path(fake).is_dir():
        return FolderSource(fake)
    return CvSource(int(os.environ.get("TVATT_CAMERA", "0")))


class Scanner:
    def __init__(self, source_factory: Callable, on_scan: Callable[[str], None], *, idle_seconds: float = 120,
                 debounce: float = 3.0, clock: Callable[[], float] = time.monotonic,
                 on_change: Callable[[], None] | None = None,
                 overlay: Callable | None = None):
        """`overlay(img, (h, w))` may draw on a copy of each preview picture (frame size given) and return it."""
        self._factory, self._on_scan = source_factory, on_scan
        self._overlay = overlay
        self._on_change = on_change or (lambda: None)
        self.idle_seconds, self.debounce, self._clock = idle_seconds, debounce, clock
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._jpeg: bytes | None = None
        self._frame = None
        self._seen: dict[str, float] = {}
        self._beat = 0.0
        self._seq = 0
        self.last: dict | None = None
        self.error: str | None = None

    @property
    def running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    def start(self) -> None:
        with self._lock:
            self._beat = self._clock()
            if self.running and not self._stop.is_set():
                return
            if self._thread is not None:
                self._thread.join(timeout=2)  # a stop is still finishing; wait, then start afresh
            try:
                cv2 = _load_cv2()
            except ImportError:
                raise CameraUnavailable(NO_CAMERA)
            source = self._factory()
            self.error = None
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(source, cv2, self._stop), name="scanner", daemon=True)
            self._thread.start()

    def heartbeat(self) -> None:
        self._beat = self._clock()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(timeout=2)

    def latest_jpeg(self) -> bytes | None:
        return self._jpeg

    def latest_frame(self):
        """The newest full-size picture (BGR), or None when the camera is not running."""
        return self._frame

    def _drawn(self, img, frame):
        """The preview with the overlay drawn on a copy (at ≤ 640 px the preview *is* the frame)."""
        if self._overlay is None:
            return img
        try:
            return self._overlay(img.copy(), frame.shape[:2])
        except Exception:  # noqa: BLE001  - a drawing error must never stop the camera
            return img

    def _hit(self, code: str) -> None:
        # Sliding window: a code held in view counts once; it must be out of view for `debounce`
        # seconds before it counts again.
        now = self._clock()
        prev = self._seen.get(code)
        self._seen[code] = now
        if prev is not None and now - prev < self.debounce:
            return
        self._seq += 1
        self.last = {"seq": self._seq, "code": code, "at": time.time()}
        self._on_scan(code)

    def _run(self, source, cv2, stop: threading.Event) -> None:
        failed = n = 0
        try:
            while not stop.is_set():
                if self._clock() - self._beat > self.idle_seconds:
                    break
                frame = source.read()
                if frame is None:
                    failed += 1
                    if failed >= MAX_FAILED_READS:
                        self.error = CAMERA_STOPPED
                        break
                    time.sleep(0.05)
                    continue
                failed = 0
                self._frame = frame
                if n % PREVIEW_EVERY == 0:
                    ok, buf = cv2.imencode(".jpg", self._drawn(preview(frame, cv2), frame), [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ok:
                        self._jpeg = buf.tobytes()
                if n % DECODE_EVERY == 0:
                    for code in decode(frame):
                        self._hit(code)
                n += 1
        except Exception:  # noqa: BLE001  - a broken camera must not take the app down
            self.error = CAMERA_STOPPED
        finally:
            source.release()
            self._jpeg = None
            self._frame = None
            self._on_change()

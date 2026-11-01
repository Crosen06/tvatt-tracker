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
WIDTH, HEIGHT = 640, 480
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


def decode(frame) -> list[str]:
    """Valid GTIN codes found in a BGR or grey frame."""
    global _detector
    cv2 = _load_cv2()
    with _detector_lock:
        if _detector is None:
            _detector = cv2.barcode.BarcodeDetector()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        if hasattr(_detector, "detectAndDecodeWithType"):
            result = _detector.detectAndDecodeWithType(gray)
            # OpenCV ≥ 4.8: (ok, infos, types, points); some builds return (infos, types, points).
            infos = result[1] if isinstance(result[0], bool) else result[0]
        else:  # pragma: no cover - older contrib builds
            result = _detector.detectAndDecode(gray)
            infos = result[1] if isinstance(result[0], bool) else result[0]
    if isinstance(infos, str):
        infos = [infos]
    out = []
    for code in infos or ():
        if valid_gtin(code) and code not in out:
            out.append(code)
    return out


class CvSource:
    def __init__(self, index: int):
        cv2 = _load_cv2()
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraUnavailable(NO_CAMERA)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)

    def read(self):
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        self._cap.release()


class FolderSource:
    """Shows the newest image in a folder, re-checking the folder on every read (e2e tests)."""

    def __init__(self, folder, delay: float = 1 / 15):
        self.folder, self.delay = Path(folder), delay

    def read(self):
        import numpy as np

        cv2 = _load_cv2()
        time.sleep(self.delay)
        files = sorted(self.folder.glob("*.png"), key=lambda p: p.stat().st_mtime)
        if files:
            img = cv2.imread(str(files[-1]))
            if img is not None:
                return img
        return np.full((HEIGHT, WIDTH, 3), 180, dtype=np.uint8)

    def release(self):
        pass


def default_source_factory():
    fake = os.environ.get("TVATT_FAKE_CAMERA")
    if fake and Path(fake).is_dir():
        return FolderSource(fake)
    return CvSource(int(os.environ.get("TVATT_CAMERA", "0")))


class Scanner:
    def __init__(self, source_factory: Callable, on_scan: Callable[[str], None], *, idle_seconds: float = 120,
                 debounce: float = 3.0, clock: Callable[[], float] = time.monotonic):
        self._factory, self._on_scan = source_factory, on_scan
        self.idle_seconds, self.debounce, self._clock = idle_seconds, debounce, clock
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._jpeg: bytes | None = None
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
            if self.running:
                return
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

    def _hit(self, code: str) -> None:
        now = self._clock()
        if now - self._seen.get(code, -1e9) < self.debounce:
            return
        self._seen[code] = now
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
                if n % PREVIEW_EVERY == 0:
                    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
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

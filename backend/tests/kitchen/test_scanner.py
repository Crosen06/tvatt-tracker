import threading
import time

import pytest

from app.kitchen import scanner
from app.kitchen.scanner import CameraUnavailable, Scanner, decode
from tests.kitchen.barcode_images import blank_frame, ean13_frame

CODE = "4006381333931"


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeSource:
    def __init__(self, frames, delay=0.005):
        self.frames, self.delay, self.i, self.released = frames, delay, 0, False

    def read(self):
        time.sleep(self.delay)
        f = self.frames[self.i % len(self.frames)] if self.frames else None
        self.i += 1
        return f

    def release(self):
        self.released = True


def wait_for(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def made():
    scanners = []
    yield scanners
    for s in scanners:
        s.stop()


def make(made, source, **kw):
    hits = []
    clock = kw.pop("clock", FakeClock())
    s = Scanner(lambda: source, hits.append, clock=clock, **kw)
    made.append(s)
    return s, hits, clock


def test_decode_generated_ean13():
    assert decode(ean13_frame(CODE)) == [CODE]
    assert decode(ean13_frame("7310865004703")) == ["7310865004703"]


def test_decode_blank_frame_empty():
    assert decode(blank_frame()) == []


def test_scan_debounce(made):
    s, hits, clock = make(made, FakeSource([ean13_frame(CODE)]))
    s.start()
    assert wait_for(lambda: len(hits) == 1)
    time.sleep(0.3)
    assert hits == [CODE]
    assert s.last["code"] == CODE and s.last["seq"] == 1
    clock.t += 3.1
    assert wait_for(lambda: len(hits) == 2)
    assert s.last["seq"] == 2


def test_idle_stop(made):
    src = FakeSource([blank_frame()])
    s, hits, clock = make(made, src)
    s.start()
    assert s.running
    clock.t += 60
    s.heartbeat()
    clock.t += 100
    time.sleep(0.2)
    assert s.running
    clock.t += 21
    assert wait_for(lambda: not s.running)
    assert src.released


def test_start_is_idempotent(made):
    calls = []

    def factory():
        calls.append(1)
        return FakeSource([blank_frame()])

    s = Scanner(factory, lambda c: None, clock=FakeClock())
    made.append(s)
    s.start()
    s.start()
    assert calls == [1]
    assert sum(t.name == "scanner" for t in threading.enumerate()) == 1


def test_source_failure_sets_error(made):
    sources = [FakeSource([], delay=0), FakeSource([blank_frame()])]
    s = Scanner(lambda: sources.pop(0), lambda c: None, clock=FakeClock())
    made.append(s)
    s.start()
    assert wait_for(lambda: not s.running)
    assert s.error == "Kameran slutade svara."
    s.start()
    assert s.running and s.error is None


def test_factory_unavailable_raises(made):
    def factory():
        raise CameraUnavailable("Ingen kamera hittades. Kontrollera att webbkameran sitter i.")

    s = Scanner(factory, lambda c: None)
    with pytest.raises(CameraUnavailable):
        s.start()
    assert not s.running


def test_cv2_missing_raises(made, monkeypatch):
    def boom():
        raise ImportError("no cv2")

    monkeypatch.setattr(scanner, "_load_cv2", boom)
    s, _, _ = make(made, FakeSource([blank_frame()]))
    with pytest.raises(CameraUnavailable, match="Ingen kamera"):
        s.start()


def test_latest_jpeg_available(made):
    s, _, _ = make(made, FakeSource([blank_frame()]))
    assert s.latest_jpeg() is None
    s.start()
    assert wait_for(lambda: s.latest_jpeg() is not None)
    assert s.latest_jpeg()[:2] == b"\xff\xd8"


def test_folder_source_cycles_images(tmp_path):
    import cv2

    src = scanner.FolderSource(tmp_path, delay=0)
    assert src.read().shape == (480, 640, 3)  # empty folder → blank frame
    cv2.imwrite(str(tmp_path / "a.png"), ean13_frame(CODE))
    assert decode(src.read()) == [CODE]


class TickingSource(FakeSource):
    """Advances the fake clock on every read, like a real camera delivering frames over time."""

    def __init__(self, frames_fn, clock, step=0.1):
        super().__init__([], delay=0.002)
        self.frames_fn, self.clock, self.step = frames_fn, clock, step

    def read(self):
        time.sleep(self.delay)
        self.clock.t += self.step
        self.i += 1
        return self.frames_fn(self.clock.t)


def test_code_held_in_view_fires_once(made):
    clock = FakeClock()
    start = clock.t
    code_frame, blank = ean13_frame(CODE), blank_frame()
    # In view for 6 s, away for 4 s, then back.
    src = TickingSource(lambda t: code_frame if (t - start < 6 or t - start > 10) else blank, clock)
    hits = []
    s = Scanner(lambda: src, hits.append, clock=clock)
    made.append(s)
    s.start()
    assert wait_for(lambda: clock.t - start > 5.5)
    assert hits == [CODE]
    assert wait_for(lambda: len(hits) == 2, timeout=8)


def test_thread_exit_notifies(made):
    changes = []
    s = Scanner(lambda: FakeSource([], delay=0), lambda c: None, on_change=lambda: changes.append(1), clock=FakeClock())
    made.append(s)
    s.start()
    assert wait_for(lambda: not s.running)
    assert wait_for(lambda: len(changes) >= 1)


def test_start_right_after_stop_restarts(made):
    s, _, _ = make(made, FakeSource([blank_frame()], delay=0.3))
    s.start()
    stopper = threading.Thread(target=s.stop)
    stopper.start()
    time.sleep(0.02)
    s.start()  # arrives while the old thread is still finishing its read
    stopper.join()
    time.sleep(0.5)
    assert s.running

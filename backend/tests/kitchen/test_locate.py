import logging
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.kitchen import locate
from tests.kitchen.vision_images import package_rect, scene

GREY = np.array(locate.GREY)


def contour_mask(shape, contour):
    mask = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(mask, [np.array(contour, np.int32)], 1)
    return mask


def rect_mask(shape, rect):
    x, y, w, h = rect
    mask = np.zeros(shape[:2], np.uint8)
    mask[y:y + h, x:x + w] = 1
    return mask


def iou(a, b) -> float:
    return float((a & b).sum()) / float((a | b).sum())


def test_box_fraction_env_and_limits(monkeypatch):
    monkeypatch.delenv("TVATT_VISION_BOX", raising=False)
    assert locate.box_fraction() == 0.6
    for raw, expected in (("0.5", 0.5), ("0.1", 0.3), ("2", 0.9), ("x", 0.6)):
        monkeypatch.setenv("TVATT_VISION_BOX", raw)
        assert locate.box_fraction() == expected


def test_guide_box_is_centred_square(monkeypatch):
    monkeypatch.delenv("TVATT_VISION_BOX", raising=False)
    assert locate.guide_box((480, 640)) == (176, 96, 288, 288)
    assert locate.guide_box((1080, 1920, 3), 0.5) == (690, 270, 540, 540)


@pytest.mark.parametrize("shirt", [0, 1])
@pytest.mark.parametrize("item", ["milk", "coffee", "banana"])
def test_cut_out_follows_package(item, shirt):
    frame = scene(item, person=True, shirt=shirt)
    found = locate.locate(frame)
    assert found.found
    assert iou(contour_mask(frame.shape, found.contour), rect_mask(frame.shape, package_rect())) >= 0.8
    assert found.image.shape == (224, 224, 3) and found.image.dtype == np.uint8
    for corner in (found.image[0, 0], found.image[0, -1], found.image[-1, 0], found.image[-1, -1]):
        assert np.abs(corner.astype(int) - GREY).max() <= 2
    assert 0.3 < found.area < 0.45  # the package covers ~37 % of the box


@pytest.mark.parametrize("person", [False, True])
def test_empty_box_never_raises(person):
    found = locate.locate(scene(None, person=person))
    assert found.image.shape == (224, 224, 3)
    assert found.box == (176, 96, 288, 288)


def test_too_big_is_not_found():
    frame = np.full((480, 640, 3), (40, 40, 200), np.uint8)
    frame = np.clip(frame + np.random.default_rng(1).normal(0, 3, frame.shape), 0, 255).astype(np.uint8)
    found = locate.locate(frame)
    assert not found.found and found.contour is None and found.area == 0
    expected = cv2.resize(frame[96:384, 176:464], (224, 224), interpolation=cv2.INTER_AREA)
    assert np.abs(found.image.astype(int) - expected.astype(int)).mean() < 2


def test_face_is_never_item():
    frame = scene("milk", person=True)
    x, y, w, h = package_rect()
    face = (x - 10, y - 20, w + 20, h // 4 + 20)  # over the package's top quarter
    found = locate.locate(frame, [face])
    assert found.found
    fx, fy, fw, fh = face
    inside = [p for p in found.contour if fx + 2 < p[0] < fx + fw - 2 and fy + 2 < p[1] < fy + fh - 2]
    assert inside == []
    assert contour_mask(frame.shape, found.contour)[fy + 3:fy + fh - 3, fx + 3:fx + fw - 3].sum() == 0


def test_face_is_grey_in_fallback_picture(monkeypatch):
    def broken(*a, **k):
        raise cv2.error("boom")

    monkeypatch.setattr(cv2, "grabCut", broken)
    frame = scene("milk")
    found = locate.locate(frame, [(176, 96, 144, 144)])  # the box's top-left quarter
    assert not found.found
    quarter = found.image[4:108, 4:108].astype(int)
    assert np.abs(quarter - GREY).max() <= 2
    assert np.abs(found.image[160:220, 160:220].astype(int) - GREY).max() > 20  # the rest is the picture


def test_odd_frames(monkeypatch):
    grey = cv2.cvtColor(scene("milk"), cv2.COLOR_BGR2GRAY)
    assert locate.locate(grey).image.shape == (224, 224, 3)
    tiny = cv2.resize(scene("milk"), (64, 48))
    assert locate.locate(tiny).image.shape == (224, 224, 3)

    def broken(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(cv2, "grabCut", broken)
    found = locate.locate(scene("milk"))
    assert not found.found and found.image.shape == (224, 224, 3)


def test_load_faces(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("TVATT_FACE_MODEL", raising=False)
    assert locate.load_faces(tmp_path) is None  # no file: quietly off
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / locate.FACE_FILE).write_bytes(b"not a model")
    locate._face_warned = False
    with caplog.at_level(logging.WARNING):
        assert locate.load_faces(tmp_path) is None
        assert locate.load_faces(tmp_path) is None
    assert sum("Ansiktsmodellen" in r.getMessage() or "face model" in r.getMessage() for r in caplog.records) == 1


MODELS = Path(os.environ.get("TVATT_TEST_MODELS", "/nonexistent"))


@pytest.mark.skipif(not (MODELS / locate.FACE_FILE).is_file(), reason="set TVATT_TEST_MODELS to a folder with the real models")
def test_real_face_model(monkeypatch):
    monkeypatch.setenv("TVATT_FACE_MODEL", str(MODELS / locate.FACE_FILE))
    faces = locate.load_faces(Path("/nonexistent"))
    assert faces is not None
    assert faces.find(np.full((480, 640, 3), 150, np.uint8)) == []
    assert faces.find(np.full((1080, 1920, 3), 150, np.uint8)) == []


@pytest.mark.parametrize("shirt", [0, 1])
@pytest.mark.parametrize("seed", range(4))
def test_empty_box_with_patterned_shirt_is_not_found(shirt, seed):
    found = locate.locate(scene(None, person=True, shirt=shirt, seed=seed))
    assert not found.found and found.contour is None


def test_found_item_stands_out_from_its_surroundings(monkeypatch):
    monkeypatch.delenv("TVATT_VISION_CONTRAST", raising=False)
    found = locate.locate(scene("milk", person=True, shirt=0))
    assert found.found and found.contrast >= locate.min_contrast() == 0.6
    monkeypatch.setenv("TVATT_VISION_CONTRAST", "0.99")  # stricter than the milk on stripes (≈0.95)
    assert not locate.locate(scene("milk", person=True, shirt=0)).found
    monkeypatch.setenv("TVATT_VISION_CONTRAST", "x")
    assert locate.min_contrast() == 0.6


@pytest.mark.parametrize("item, shirt", [((235, 235, 235), (60, 60, 60)), ((20, 20, 20), (60, 60, 60))])
def test_grey_items_are_found_by_lightness(item, shirt):
    frame = np.full((480, 640, 3), shirt, np.uint8)
    x, y, w, h = package_rect()
    frame[y:y + h, x:x + w] = item
    frame = np.clip(frame + np.random.default_rng(2).normal(0, 3, frame.shape), 0, 255).astype(np.uint8)
    assert locate.locate(frame).found


def test_missing_face_model_logged_once(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("TVATT_FACE_MODEL", raising=False)
    monkeypatch.setattr(locate, "_face_warned", False)
    with caplog.at_level(logging.INFO):
        assert locate.load_faces(tmp_path) is None
        assert locate.load_faces(tmp_path) is None
    assert sum("face model" in r.getMessage() for r in caplog.records) == 1

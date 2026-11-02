"""The real models on synthetic pictures. Skipped unless TVATT_TEST_MODELS points at a folder with
mobilenetv2.onnx and face_yunet.onnx (e.g. downloaded with deploy/get-model.sh)."""

import os
from pathlib import Path

import pytest

from app.kitchen import locate, vision
from tests.kitchen.vision_images import scene

MODELS = Path(os.environ.get("TVATT_TEST_MODELS", "/nonexistent"))
pytestmark = pytest.mark.skipif(not (MODELS / vision.MODEL_FILE).is_file(), reason="set TVATT_TEST_MODELS")


def test_same_item_beats_other_item_whatever_the_shirt(monkeypatch):
    monkeypatch.setenv("TVATT_FACE_MODEL", str(MODELS / locate.FACE_FILE))
    emb = vision.OnnxEmbedder(MODELS / vision.MODEL_FILE)
    faces = locate.load_faces(MODELS)

    def fp(frame):
        return emb.embed(locate.locate(frame, faces.find(frame) if faces else ()).image)

    milk0 = fp(scene("milk", person=True, shirt=0))
    milk1 = fp(scene("milk", person=True, shirt=1, seed=4))
    coffee0 = fp(scene("coffee", person=True, shirt=0, seed=7))
    same, other = vision.cosine(milk0, milk1), vision.cosine(milk0, coffee0)
    print(f"milk/milk (other shirt) {same:.3f}, milk/coffee (same shirt) {other:.3f}")
    assert same > other
    assert emb.model_id.endswith("-obj1")

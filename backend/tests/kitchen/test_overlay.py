import numpy as np
import pytest

from app.kitchen import overlay

GREEN = np.array((113, 191, 47))
YELLOW = np.array((61, 179, 242))
FRAME = (1080, 1920)
BOX = (552, 216, 648, 648)  # guide box of a 1920×1080 picture
CONTOUR = [(700, 300), (1050, 300), (1050, 800), (700, 800)]


def analysis(decision="sure", label="Mjölk", score=0.87, at=10.0, found=True, has_gallery=True):
    return {"at": at, "contour": CONTOUR if found else None, "found": found, "label": label, "score": score,
            "decision": decision, "has_gallery": has_gallery}


def near(img, colour, tol=12):
    return np.all(np.abs(img.astype(int) - colour) <= tol, axis=-1)


@pytest.mark.parametrize("a, text", [
    (analysis("sure", score=0.87), "Mjölk 87 %"),
    (analysis("maybe", score=0.71), "Mjölk? 71 %"),
    (analysis("none", score=0.42), "Okänd (Mjölk 42 %)"),
    (analysis("none", label="", score=0.0, has_gallery=False), "Okänd"),
])
def test_label_text(a, text):
    assert overlay.label_text(a) == text


def test_draw_sure_is_green():
    img = np.full((360, 640, 3), 90, np.uint8)
    out = overlay.draw(img, FRAME, BOX, analysis(), now=10.5)
    assert out.shape == (360, 640, 3)
    s = 640 / 1920
    # middle of the contour's left edge (x=700, y=550 in the full picture)
    x, y = round(700 * s), round(550 * s)
    assert near(out[y - 2:y + 3, x - 2:x + 3], GREEN).any()
    assert near(out, GREEN).sum() > 200


def test_draw_maybe_is_yellow():
    out = overlay.draw(np.full((360, 640, 3), 90, np.uint8), FRAME, BOX, analysis("maybe", score=0.7), now=10.5)
    assert near(out, YELLOW).sum() > 200 and near(out, GREEN).sum() == 0


def test_stale_analysis_draws_box_only():
    img = np.full((360, 640, 3), 90, np.uint8)
    out = overlay.draw(img, FRAME, BOX, analysis(at=10.0), now=12.0)
    assert near(out, GREEN).sum() == 0 and near(out, YELLOW).sum() == 0
    assert near(out, np.array((255, 255, 255)), tol=30).sum() > 50  # the box corners and the hint


def test_no_analysis_draws_box_and_hint():
    out = overlay.draw(np.full((360, 640, 3), 90, np.uint8), FRAME, BOX, None, now=0.0)
    s = 640 / 1920
    below = out[round((BOX[1] + BOX[3]) * s) + 2:, :]
    assert near(below, np.array((255, 255, 255)), tol=40).sum() > 20  # "Håll varan i rutan" under the box


def test_label_with_swedish_letters_without_font(monkeypatch, tmp_path):
    monkeypatch.setattr(overlay, "FONT_PATH", tmp_path / "missing.woff")
    monkeypatch.setattr(overlay, "_fonts", {})
    out = overlay.draw(np.full((360, 640, 3), 90, np.uint8), FRAME, BOX, analysis(label="Ärtsoppa åäö"), now=10.5)
    assert out.shape == (360, 640, 3)


def test_contour_at_top_edge_keeps_label_inside():
    a = analysis()
    a["contour"] = [(600, 0), (900, 0), (900, 400), (600, 400)]
    out = overlay.draw(np.full((360, 640, 3), 90, np.uint8), FRAME, BOX, a, now=10.5)
    assert out.shape == (360, 640, 3)

"""Synthetic camera pictures for the recognition tests."""

import cv2
import numpy as np


PACKAGE_H, PACKAGE_W = 0.42, 0.32  # share of the picture height; fits well inside the guide box (0.6)
SHIRTS = (((120, 60, 40), (90, 90, 90)), ((60, 140, 60), (40, 90, 40)))


def package_rect(size=(480, 640), shift: int = 0) -> tuple[int, int, int, int]:
    """(x, y, w, h) of the package that `scene` draws."""
    h, w = size
    ph, pw = int(h * PACKAGE_H), int(h * PACKAGE_W)
    return (w - pw) // 2 + shift, (h - ph) // 2, pw, ph


def scene(item: str | None = None, size=(480, 640), seed: int = 0, shift: int = 0,
          person: bool = False, shirt: int = 0) -> np.ndarray:
    """A grey kitchen wall, optionally with a person and a coloured "package" held in the middle.

    `person` draws a torso in shirt pattern `shirt` (0: dark blue/grey stripes, 1: green checks)
    behind the package and a skin-coloured oval "face" at the top.

    Items: "milk" (white/blue stripes), "banana" (yellow), "coffee" (red with a dark band),
    "bread" (brown).
    """
    rng = np.random.default_rng(seed)
    h, w = size
    img = np.full((h, w, 3), (150, 150, 145), dtype=np.uint8)
    img[: h // 3] = (170, 168, 160)
    if person:
        a, b = SHIRTS[shirt]
        top, left, right = int(h * 0.32), int(w * 0.18), int(w * 0.82)
        for yy in range(top, h):
            for xx in range(left, right, 10):
                if shirt == 0:
                    c = a if (yy // 20) % 2 == 0 else b
                else:
                    c = a if ((yy // 30) + (xx // 30)) % 2 == 0 else b
                img[yy, xx:min(xx + 10, right)] = c
        cv2.ellipse(img, (w // 2, int(h * 0.17)), (int(h * 0.08), int(h * 0.11)), 0, 0, 360, (120, 160, 210), -1)
    if item is not None:
        x, y, pw, ph = package_rect(size, shift)
        if item == "milk":
            img[y:y + ph, x:x + pw] = (245, 245, 245)
            for k in range(0, ph, 24):
                img[y + k:y + k + 10, x:x + pw] = (200, 90, 30)
        elif item == "banana":
            img[y:y + ph, x:x + pw] = (40, 210, 235)
        elif item == "coffee":
            img[y:y + ph, x:x + pw] = (40, 40, 200)
            img[y + ph // 3:y + ph // 2, x:x + pw] = (20, 20, 20)
        elif item == "bread":
            img[y:y + ph, x:x + pw] = (60, 110, 160)
        else:
            raise ValueError(item)
    noise = rng.normal(0, 3, img.shape)
    return np.clip(img.astype(int) + noise, 0, 255).astype(np.uint8)

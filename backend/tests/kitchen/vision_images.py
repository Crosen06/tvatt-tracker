"""Synthetic camera pictures for the recognition tests."""

import numpy as np


def scene(item: str | None = None, size=(480, 640), seed: int = 0, shift: int = 0) -> np.ndarray:
    """A grey kitchen wall, optionally with a coloured "package" held in the middle.

    Items: "milk" (white/blue stripes), "banana" (yellow), "coffee" (red with a dark band),
    "bread" (brown).
    """
    rng = np.random.default_rng(seed)
    h, w = size
    img = np.full((h, w, 3), (150, 150, 145), dtype=np.uint8)
    img[: h // 3] = (170, 168, 160)
    if item is not None:
        ph, pw = int(h * 0.7), int(h * 0.6)
        y, x = (h - ph) // 2, (w - pw) // 2 + shift
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

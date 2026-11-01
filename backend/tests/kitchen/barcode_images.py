"""Draw EAN-13 barcodes as images so the scanner can be tested with real decoding."""

import numpy as np

L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
R = ["".join("1" if b == "0" else "0" for b in code) for code in L]
G = [code[::-1] for code in R]
PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLG", "LGLGLG", "LGLGGL", "LGGLGL"]


def ean13_modules(code: str) -> str:
    assert len(code) == 13 and code.isdigit()
    first, left, right = int(code[0]), code[1:7], code[7:]
    bits = "101"
    for d, p in zip(left, PARITY[first]):
        bits += (L if p == "L" else G)[int(d)]
    bits += "01010"
    for d in right:
        bits += R[int(d)]
    return bits + "101"


def ean13_frame(code: str, module_px: int = 3, height: int = 150, size=(480, 640), seed: int = 1) -> np.ndarray:
    """A camera-like 640×480 BGR frame: label on a grey background, slightly blurred, with noise.

    OpenCV's detector looks for gradients, so perfectly sharp synthetic edges are not found;
    a little blur and noise make the frame look like a real webcam picture.
    """
    import cv2

    bits = "0" * 12 + ean13_modules(code) + "0" * 12
    row = np.array([20 if b == "1" else 235 for b in bits], dtype=np.uint8).repeat(module_px)
    img = np.full(size, 190, dtype=np.uint8)
    y, x = (size[0] - height) // 2, (size[1] - len(row)) // 2
    img[y - 20:y + height + 20, x - 10:x + len(row) + 10] = 235
    img[y:y + height, x:x + len(row)] = row
    img = cv2.GaussianBlur(img, (3, 3), 0)
    noise = np.random.default_rng(seed).normal(0, 4, img.shape)
    img = np.clip(img.astype(int) + noise, 0, 255).astype(np.uint8)
    return np.stack([img] * 3, axis=-1)


def blank_frame(size=(480, 640)) -> np.ndarray:
    return np.full((*size, 3), 180, dtype=np.uint8)

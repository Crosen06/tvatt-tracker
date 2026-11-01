"""Store garment photos: a 1200 px JPEG plus a 400 px thumbnail."""

import io
import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO = multi-picture JPEG from some phones
FULL_PX = 1200
THUMB_PX = 400
QUALITY = 82
MAX_PIXELS = 60_000_000  # ~60 MP; larger images could exhaust the Pi's memory


class UnsupportedPhoto(Exception):
    pass


class PhotoTooLarge(Exception):
    pass


def save_photo(data: bytes, photos_dir: Path) -> str:
    try:
        with warnings.catch_warnings():
            # We enforce MAX_PIXELS ourselves; Pillow's own warning would only add noise.
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data))
        with im:
            if im.format not in ALLOWED:
                raise UnsupportedPhoto(im.format)
            if im.width * im.height > MAX_PIXELS:
                raise PhotoTooLarge(f"{im.width}x{im.height}")
            if im.format in ("JPEG", "MPO"):
                im.draft("RGB", (FULL_PX * 2, FULL_PX * 2))  # decode at reduced size: far less memory
            im.load()
            img = ImageOps.exif_transpose(im).convert("RGB")
    except Image.DecompressionBombError as e:
        raise PhotoTooLarge(str(e)) from e
    except (UnidentifiedImageError, OSError) as e:
        raise UnsupportedPhoto(str(e)) from e

    name = f"{uuid.uuid4().hex}.jpg"
    full = img.copy()
    full.thumbnail((FULL_PX, FULL_PX))
    full.save(photos_dir / name, "JPEG", quality=QUALITY, optimize=True)
    thumb = img.copy()
    thumb.thumbnail((THUMB_PX, THUMB_PX))
    thumb.save(photos_dir / "thumb" / name, "JPEG", quality=QUALITY, optimize=True)
    return name


def delete_photo(name: str | None, photos_dir: Path) -> None:
    if not name:
        return
    for p in (photos_dir / name, photos_dir / "thumb" / name):
        p.unlink(missing_ok=True)

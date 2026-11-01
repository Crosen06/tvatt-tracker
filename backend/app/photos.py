"""Store garment photos: a 1200 px JPEG plus a 400 px thumbnail."""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED = {"JPEG", "PNG", "WEBP", "MPO"}  # MPO = multi-picture JPEG from some phones
FULL_PX = 1200
THUMB_PX = 400
QUALITY = 82


class UnsupportedPhoto(Exception):
    pass


def save_photo(data: bytes, photos_dir: Path) -> str:
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ALLOWED:
                raise UnsupportedPhoto(im.format)
            im.load()
            img = ImageOps.exif_transpose(im).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
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

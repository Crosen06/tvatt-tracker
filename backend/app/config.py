"""Resolve where the app keeps its database and photos."""

import os
from pathlib import Path


def resolve_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env = os.environ.get("TVATT_DATA")
    if env:
        return Path(env).expanduser()
    return Path.home() / "tvatt-data"

"""Generic loader for a folder of DNG frames (Pixel 6 experiment packages, brief §21).

Expected layout (produced by Hanson Camera Lab)::

    experiment_0001/raw/frame_000.dng …   metadata.json (optional)   motion/sensors.csv (optional)
"""

from __future__ import annotations

import json
from pathlib import Path

from ..raw import RawFrame, read_dng


def find_dngs(path: str | Path) -> list[Path]:
    path = Path(path)
    raw_dir = path / "raw" if (path / "raw").is_dir() else path
    files = sorted(p for p in raw_dir.iterdir() if p.suffix.lower() == ".dng")
    if not files:
        raise FileNotFoundError(f"No .dng files in {raw_dir}")
    return files


def load_dng_folder(path: str | Path) -> tuple[list[RawFrame], dict]:
    path = Path(path)
    frames = [read_dng(p) for p in find_dngs(path)]
    meta_file = path / "metadata.json"
    meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
    return frames, meta

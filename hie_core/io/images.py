"""Image output and EXIF orientation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
from PIL import Image


def apply_orientation(img: np.ndarray, orientation: int) -> np.ndarray:
    """Rotate/flip an array so it displays upright for the given EXIF orientation (1-8)."""
    ops = {
        1: lambda a: a,
        2: lambda a: a[:, ::-1],
        3: lambda a: a[::-1, ::-1],
        4: lambda a: a[::-1, :],
        5: lambda a: np.swapaxes(a, 0, 1),
        6: lambda a: np.rot90(a, k=-1),
        7: lambda a: np.rot90(a, k=1)[::-1, :],
        8: lambda a: np.rot90(a, k=1),
    }
    return np.ascontiguousarray(ops.get(int(orientation or 1), ops[1])(img))


def to_uint8(img: np.ndarray) -> np.ndarray:
    return np.clip(img * 255.0 + 0.5, 0, 255).astype(np.uint8)


def save_jpeg(path: str | Path, img: np.ndarray, quality: int = 95) -> None:
    Image.fromarray(to_uint8(img)).save(path, quality=quality, subsampling=0, optimize=True)


def save_png(path: str | Path, img: np.ndarray) -> None:
    Image.fromarray(to_uint8(img)).save(path, optimize=True)


def save_tiff16(path: str | Path, img: np.ndarray) -> None:
    tifffile.imwrite(path, np.clip(img * 65535.0 + 0.5, 0, 65535).astype(np.uint16), photometric="rgb")


def load_image(path: str | Path) -> np.ndarray:
    """Load an 8-bit image as float32 [0, 1] RGB (EXIF orientation is *not* applied)."""
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0

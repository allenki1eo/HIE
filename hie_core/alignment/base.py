"""Shared alignment types and warping.

Flow convention (same as OpenCV's Farnebäck/DIS): ``flow[y, x] = (dx, dy)`` means the
reference pixel (x, y) corresponds to the alternate-frame location (x + dx, y + dy).
Warping an alternate frame therefore samples it at ``(x + dx, y + dy)``.
All coordinates are in Bayer-*plane* pixels (half the sensor resolution).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import cv2
import numpy as np

_INTERP = {"nearest": cv2.INTER_NEAREST, "linear": cv2.INTER_LINEAR, "cubic": cv2.INTER_CUBIC}


@dataclass
class Alignment:
    flow: np.ndarray  # (H, W, 2) float32
    method: str
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def mean_displacement(self) -> float:
        return float(np.linalg.norm(self.flow.reshape(-1, 2).mean(axis=0)))


class Aligner(Protocol):
    name: str

    def __call__(self, ref_gray: np.ndarray, alt_gray: np.ndarray) -> Alignment: ...


def identity_flow(shape: tuple[int, int]) -> np.ndarray:
    return np.zeros((*shape, 2), dtype=np.float32)


def base_grid(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    h, w = shape
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return xs, ys


def warp(image: np.ndarray, flow: np.ndarray, interp: str = "cubic") -> tuple[np.ndarray, np.ndarray]:
    """Warp ``image`` (H, W) or (H, W, C<=4) by ``flow``; returns (warped, valid_mask)."""
    h, w = image.shape[:2]
    xs, ys = base_grid((h, w))
    map_x = xs + flow[..., 0]
    map_y = ys + flow[..., 1]
    if interp == "nearest":
        map_x, map_y = np.rint(map_x), np.rint(map_y)
    out = cv2.remap(
        np.ascontiguousarray(image, dtype=np.float32), map_x, map_y,
        interpolation=_INTERP[interp], borderMode=cv2.BORDER_REFLECT,
    )
    valid = (map_x >= 0) & (map_x <= w - 1) & (map_y >= 0) & (map_y <= h - 1)
    return out.reshape(image.shape), valid


def to_uint8_for_matching(gray: np.ndarray, *, denoise_sigma: float = 0.0) -> np.ndarray:
    """Map linear gray to 8-bit with a square-root curve (≈ variance-stabilising for shot noise)."""
    g = np.maximum(gray, 0.0).astype(np.float32)
    scale = float(np.quantile(g, 0.995)) or 1.0
    g = np.sqrt(np.clip(g / scale, 0.0, 1.0))
    if denoise_sigma > 0:
        g = cv2.GaussianBlur(g, (0, 0), denoise_sigma)
    return np.clip(g * 255.0 + 0.5, 0, 255).astype(np.uint8)

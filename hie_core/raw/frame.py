"""In-memory representation of one RAW capture."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import cv2
import numpy as np

from .bayer import PLANES, to_planes


@dataclass
class CaptureMetadata:
    """Capture state recorded by the camera. Fields are ``None`` when absent — never guessed."""

    make: str | None = None
    model: str | None = None
    unique_camera_model: str | None = None
    datetime: str | None = None
    iso: float | None = None
    exposure_time: float | None = None  # seconds
    f_number: float | None = None
    focal_length: float | None = None  # mm
    orientation: int = 1  # EXIF orientation
    bits_per_sample: int | None = None
    raw_white_level: float | None = None
    raw_black_level: list[float] | None = None
    as_shot_neutral: np.ndarray | None = None  # (3,) camera-space neutral, G normalised to 1
    color_matrix1: np.ndarray | None = None  # (3, 3) XYZ -> camera
    color_matrix2: np.ndarray | None = None
    camera_calibration1: np.ndarray | None = None
    camera_calibration2: np.ndarray | None = None
    forward_matrix1: np.ndarray | None = None  # (3, 3) white-balanced camera -> XYZ(D50)
    forward_matrix2: np.ndarray | None = None
    analog_balance: np.ndarray | None = None  # (3,)
    calibration_illuminant1: int | None = None
    calibration_illuminant2: int | None = None
    baseline_exposure: float | None = None
    noise_profile: np.ndarray | None = None  # (3, 2): per R, G, B -> (S, O); var = S*x + O
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in asdict(self).items():
            out[k] = v.tolist() if isinstance(v, np.ndarray) else v
        out["extras"] = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.extras.items()}
        return out


@dataclass
class RawFrame:
    """One Bayer RAW frame, normalised so black = 0 and sensor white = 1.

    Values are *not* clipped at 0: negative read-noise excursions are kept so that
    averaging many frames stays unbiased in the shadows.
    """

    cfa: np.ndarray  # (H, W) float32, even dimensions
    pattern: str  # 2x2 CFA layout, e.g. "BGGR"
    meta: CaptureMetadata
    lens_shading: np.ndarray | None = None  # (h, w, 4) gain grid in PLANES order
    source: str | None = None

    @property
    def shape(self) -> tuple[int, int]:
        return self.cfa.shape  # type: ignore[return-value]

    def planes(self) -> np.ndarray:
        """(H/2, W/2, 4) float32 planes in :data:`~hie_core.raw.bayer.PLANES` order."""
        return to_planes(self.cfa, self.pattern)

    def noise_params(self) -> tuple[np.ndarray, np.ndarray] | None:
        """Per-plane (S, O) from the DNG ``NoiseProfile`` in PLANES order, if recorded."""
        if self.meta.noise_profile is None:
            return None
        rgb = self.meta.noise_profile  # rows R, G, B
        idx = {"R": 0, "Gr": 1, "Gb": 1, "B": 2}
        s = np.array([rgb[idx[p], 0] for p in PLANES], dtype=np.float64)
        o = np.array([rgb[idx[p], 1] for p in PLANES], dtype=np.float64)
        return s, o


def upsample_shading(grid: np.ndarray, out_hw: tuple[int, int]) -> np.ndarray:
    """Bilinearly upsample an (h, w, C) gain grid whose corner samples sit on the image corners.

    Android's ``LENS_SHADING_MAP`` and the HDR+ sidecar maps place grid points at
    evenly spaced positions spanning the full image, so interpolation must be
    corner-aligned (``cv2.resize`` is centre-aligned and would shift the map).
    """
    h, w = grid.shape[:2]
    oh, ow = out_hw
    ys = np.linspace(0, h - 1, oh, dtype=np.float32)
    xs = np.linspace(0, w - 1, ow, dtype=np.float32)
    map_x, map_y = np.meshgrid(xs, ys)
    grid = np.ascontiguousarray(grid, dtype=np.float32)
    out = cv2.remap(grid, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out.reshape(oh, ow, -1)

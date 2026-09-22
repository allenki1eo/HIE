"""Camera-to-sRGB colour transforms from DNG metadata (DNG 1.4 spec, chapter 6).

The pipeline white-balances in camera space first (dividing by ``AsShotNeutral``)
and then applies a 3x3 matrix mapping white-balanced camera RGB to linear sRGB.
That matrix is derived as specified by the DNG spec:

1. Interpolate ``ColorMatrix1/2`` (and ``CameraCalibration1/2``) in inverse
   correlated colour temperature, iterating CCT from the neutral's chromaticity.
2. Use ``ForwardMatrix`` when present; otherwise invert the colour matrix and
   Bradford-adapt the scene white to D50.
3. Convert XYZ(D50) → linear sRGB (D65) and normalise rows so white stays white.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..raw.frame import CaptureMetadata
from .spaces import WHITE_D50, XYZ_D50_TO_SRGB

# EXIF LightSource codes → correlated colour temperature (K)
ILLUMINANT_CCT = {
    1: 5500.0, 2: 4150.0, 3: 2850.0, 4: 5500.0, 9: 5500.0, 10: 6500.0, 11: 7500.0, 12: 6430.0, 13: 5000.0,
    14: 4230.0, 15: 3450.0, 17: 2856.0, 18: 4874.0, 19: 6774.0, 20: 5503.0, 21: 6504.0, 22: 7504.0,
    23: 5003.0, 24: 3200.0,
}
_BRADFORD = np.array([[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]])


@dataclass
class ColorTransform:
    wb_gains: np.ndarray  # (3,) multipliers for camera R, G, B
    cam_to_srgb: np.ndarray  # (3, 3) white-balanced camera RGB → linear sRGB
    cct: float | None
    source: str


def xy_to_cct(xy: np.ndarray) -> float:
    """McCamy's (1992) cubic approximation, valid ≈ 2000–12500 K."""
    n = (xy[0] - 0.3320) / (0.1858 - xy[1])
    return float(449.0 * n**3 + 3525.0 * n**2 + 6823.3 * n + 5520.33)


def _xyz_to_xy(xyz: np.ndarray) -> np.ndarray:
    return xyz[:2] / max(xyz.sum(), 1e-12)


def _bradford(src_white: np.ndarray, dst_white: np.ndarray) -> np.ndarray:
    s = _BRADFORD @ src_white
    d = _BRADFORD @ dst_white
    return np.linalg.inv(_BRADFORD) @ np.diag(d / s) @ _BRADFORD


def _interp(m1, m2, cct: float, t1: float | None, t2: float | None):
    if m2 is None or t1 is None or t2 is None or t1 == t2:
        return m1
    w = (1.0 / cct - 1.0 / t2) / (1.0 / t1 - 1.0 / t2)
    w = float(np.clip(w, 0.0, 1.0))
    return w * m1 + (1.0 - w) * m2


def white_balance_gains(neutral: np.ndarray) -> np.ndarray:
    gains = 1.0 / np.asarray(neutral, dtype=np.float64)
    return gains / gains[1]


def dng_color_transform(meta: CaptureMetadata, *, iterations: int = 6) -> ColorTransform:
    if meta.color_matrix1 is None or meta.as_shot_neutral is None:
        raise ValueError("DNG colour needs ColorMatrix1 and AsShotNeutral")
    neutral = np.asarray(meta.as_shot_neutral, dtype=np.float64)
    t1 = ILLUMINANT_CCT.get(meta.calibration_illuminant1 or 0)
    t2 = ILLUMINANT_CCT.get(meta.calibration_illuminant2 or 0)
    ab = np.diag(meta.analog_balance) if meta.analog_balance is not None else np.eye(3)
    cc1 = meta.camera_calibration1 if meta.camera_calibration1 is not None else np.eye(3)
    cc2 = meta.camera_calibration2 if meta.camera_calibration2 is not None else np.eye(3)

    cct = 5000.0
    for _ in range(iterations):
        xyz_to_cam = ab @ _interp(cc1, cc2, cct, t1, t2) @ _interp(meta.color_matrix1, meta.color_matrix2, cct, t1, t2)
        white_xyz = np.linalg.solve(xyz_to_cam, neutral)
        cct = float(np.clip(xy_to_cct(_xyz_to_xy(white_xyz)), 2000.0, 12000.0))

    cc = _interp(cc1, cc2, cct, t1, t2)
    if meta.forward_matrix1 is not None:
        fm = _interp(meta.forward_matrix1, meta.forward_matrix2, cct, t1, t2)
        ref_neutral = np.linalg.solve(ab @ cc, neutral)
        cam_to_xyz = fm @ np.diag(1.0 / ref_neutral) @ np.linalg.inv(ab @ cc)
        source = "dng_forward_matrix"
    else:
        cam_to_xyz = _bradford(white_xyz / white_xyz[1], WHITE_D50) @ np.linalg.inv(xyz_to_cam)
        source = "dng_color_matrix"
    wb_cam_to_xyz = cam_to_xyz @ np.diag(neutral)
    m = XYZ_D50_TO_SRGB @ wb_cam_to_xyz
    m = m / m.sum(axis=1, keepdims=True)
    return ColorTransform(white_balance_gains(neutral), m, cct, source)


def identity_transform(neutral: np.ndarray | None = None) -> ColorTransform:
    gains = white_balance_gains(neutral) if neutral is not None else np.ones(3)
    return ColorTransform(gains, np.eye(3), None, "identity")

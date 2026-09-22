"""Colour-space primitives (sRGB / XYZ / CIELAB / YCbCr)."""

from __future__ import annotations

import numpy as np

# Linear sRGB (D65) <-> XYZ (D65), IEC 61966-2-1
SRGB_TO_XYZ_D65 = np.array(
    [[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]]
)
XYZ_D65_TO_SRGB = np.linalg.inv(SRGB_TO_XYZ_D65)
# XYZ (D50) -> linear sRGB (D65) with Bradford adaptation (Lindbloom)
XYZ_D50_TO_SRGB = np.array(
    [[3.1338561, -1.6168667, -0.4906146], [-0.9787684, 1.9161415, 0.0334540], [0.0719453, -0.2289914, 1.4052427]]
)
WHITE_D65 = np.array([0.95047, 1.0, 1.08883])
WHITE_D50 = np.array([0.96422, 1.0, 0.82521])
LUMA_709 = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def srgb_encode(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


def srgb_decode(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    return np.where(v <= 0.04045, v / 12.92, np.power((v + 0.055) / 1.055, 2.4)).astype(np.float32)


def luminance(rgb_linear: np.ndarray) -> np.ndarray:
    return (rgb_linear @ LUMA_709).astype(np.float32)


def apply_matrix(img: np.ndarray, m: np.ndarray) -> np.ndarray:
    return (img @ np.asarray(m, dtype=np.float32).T).astype(np.float32)


def xyz_to_lab(xyz: np.ndarray, white: np.ndarray = WHITE_D65) -> np.ndarray:
    t = xyz / white
    d = 6 / 29
    f = np.where(t > d**3, np.cbrt(t), t / (3 * d * d) + 4 / 29)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1)


def srgb_to_lab(srgb_display: np.ndarray) -> np.ndarray:
    """Display-referred sRGB in [0, 1] → CIELAB (D65)."""
    return xyz_to_lab(srgb_decode(srgb_display).astype(np.float64) @ SRGB_TO_XYZ_D65.T)


# Full-range BT.601 YCbCr on gamma-encoded values (JPEG convention)
_YCC = np.array([[0.299, 0.587, 0.114], [-0.168736, -0.331264, 0.5], [0.5, -0.418688, -0.081312]], np.float32)
_YCC_INV = np.linalg.inv(_YCC).astype(np.float32)


def rgb_to_ycbcr(rgb: np.ndarray) -> np.ndarray:
    return (rgb @ _YCC.T).astype(np.float32)


def ycbcr_to_rgb(ycc: np.ndarray) -> np.ndarray:
    return (ycc @ _YCC_INV.T).astype(np.float32)

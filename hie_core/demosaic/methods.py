"""Demosaicing.

* ``bilinear`` — per-channel bilinear interpolation (reference baseline).
* ``mhc`` — Malvar, He & Cutler (ICASSP 2004): gradient-corrected linear
  interpolation with 5x5 kernels; a strong, fast, artifact-light default.
* ``opencv_ea`` — OpenCV's edge-aware demosaic, for comparison.

Inputs are (H, W) mosaics in normalised linear units; outputs are (H, W, 3) RGB.
``cv2.BORDER_REFLECT_101`` preserves the CFA phase at image borders.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..raw.bayer import color_masks, plane_offsets

_B = cv2.BORDER_REFLECT_101

_G_AT_RB = np.array(
    [[0, 0, -1, 0, 0], [0, 0, 2, 0, 0], [-1, 2, 4, 2, -1], [0, 0, 2, 0, 0], [0, 0, -1, 0, 0]], np.float32
) / 8
_ROW = np.array(  # target colour lies on the same row as this green site
    [[0, 0, 0.5, 0, 0], [0, -1, 0, -1, 0], [-1, 4, 5, 4, -1], [0, -1, 0, -1, 0], [0, 0, 0.5, 0, 0]], np.float32
) / 8
_COL = _ROW.T.copy()
_DIAG = np.array(
    [[0, 0, -1.5, 0, 0], [0, 2, 0, 2, 0], [-1.5, 0, 6, 0, -1.5], [0, 2, 0, 2, 0], [0, 0, -1.5, 0, 0]], np.float32
) / 8


def _site_masks(shape: tuple[int, int], pattern: str) -> dict[str, np.ndarray]:
    h, w = shape
    masks = {}
    for name, (r, c) in plane_offsets(pattern).items():
        m = np.zeros((h, w), dtype=bool)
        m[r::2, c::2] = True
        masks[name] = m
    return masks


def demosaic_mhc(cfa: np.ndarray, pattern: str) -> np.ndarray:
    cfa = cfa.astype(np.float32)
    m = _site_masks(cfa.shape, pattern)
    g_rb = cv2.filter2D(cfa, -1, _G_AT_RB, borderType=_B)
    row = cv2.filter2D(cfa, -1, _ROW, borderType=_B)
    col = cv2.filter2D(cfa, -1, _COL, borderType=_B)
    diag = cv2.filter2D(cfa, -1, _DIAG, borderType=_B)

    r = np.where(m["R"], cfa, np.where(m["Gr"], row, np.where(m["Gb"], col, diag)))
    g = np.where(m["Gr"] | m["Gb"], cfa, g_rb)
    b = np.where(m["B"], cfa, np.where(m["Gb"], row, np.where(m["Gr"], col, diag)))
    return np.stack([r, g, b], axis=-1)


def demosaic_bilinear(cfa: np.ndarray, pattern: str) -> np.ndarray:
    cfa = cfa.astype(np.float32)
    masks = color_masks(cfa.shape, pattern)
    k_rb = np.array([[0.25, 0.5, 0.25], [0.5, 1.0, 0.5], [0.25, 0.5, 0.25]], np.float32)
    k_g = np.array([[0, 0.25, 0], [0.25, 1.0, 0.25], [0, 0.25, 0]], np.float32)
    out = []
    for ch, k in (("R", k_rb), ("G", k_g), ("B", k_rb)):
        out.append(cv2.filter2D(cfa * masks[ch], -1, k, borderType=_B))
    return np.stack(out, axis=-1)


# OpenCV names Bayer codes after the 2x2 block starting at the second row/column;
# this table was verified against synthetic mosaics in tests/unit/test_demosaic.py.
_OPENCV_EA = {
    "RGGB": cv2.COLOR_BayerBG2RGB_EA,
    "BGGR": cv2.COLOR_BayerRG2RGB_EA,
    "GRBG": cv2.COLOR_BayerGB2RGB_EA,
    "GBRG": cv2.COLOR_BayerGR2RGB_EA,
}


def demosaic_opencv_ea(cfa: np.ndarray, pattern: str) -> np.ndarray:
    lo, hi = -0.05, 1.5  # headroom for negative noise and lens-shading gain before 16-bit quantisation
    q = np.clip((cfa - lo) / (hi - lo), 0, 1) * 65535.0
    rgb = cv2.cvtColor(np.rint(q).astype(np.uint16), _OPENCV_EA[pattern]).astype(np.float32)
    return rgb / 65535.0 * (hi - lo) + lo


DEMOSAICS = {"mhc": demosaic_mhc, "bilinear": demosaic_bilinear, "opencv_ea": demosaic_opencv_ea}


def demosaic(cfa: np.ndarray, pattern: str, method: str = "mhc") -> np.ndarray:
    try:
        return DEMOSAICS[method](cfa, pattern)
    except KeyError as exc:
        raise ValueError(f"Unknown demosaic {method!r}; choose from {sorted(DEMOSAICS)}") from exc

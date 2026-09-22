"""Display-referred finishing: chroma denoising and restrained sharpening.

Both operate on full-range YCbCr of the sRGB-encoded image. The HIE principle
"natural > oversharpened" is reflected in the defaults: sharpening uses a small
radius and soft coring so noise-level detail is not amplified.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..color.spaces import rgb_to_ycbcr, ycbcr_to_rgb


@dataclass(frozen=True)
class FinishConfig:
    chroma_radius: int = 6  # guided-filter radius in pixels (0 disables)
    chroma_eps: float = 4e-4
    sharpen_amount: float = 0.45
    sharpen_sigma: float = 0.9
    sharpen_coring: float = 0.004  # detail amplitudes below this are attenuated (display units)


def guided_filter(guide: np.ndarray, src: np.ndarray, radius: int, eps: float) -> np.ndarray:
    """Grey-guide guided filter (He, Sun & Tang, ECCV 2010) with O(1) box filters."""
    k = (2 * radius + 1, 2 * radius + 1)
    box = lambda x: cv2.boxFilter(x, cv2.CV_32F, k, borderType=cv2.BORDER_REFLECT)  # noqa: E731
    mean_i, mean_p = box(guide), box(src)
    cov_ip = box(guide * src) - mean_i * mean_p
    var_i = box(guide * guide) - mean_i * mean_i
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    return box(a) * guide + box(b)


def chroma_denoise(ycc: np.ndarray, radius: int, eps: float) -> np.ndarray:
    if radius <= 0:
        return ycc
    y = ycc[..., 0]
    out = ycc.copy()
    for c in (1, 2):
        out[..., c] = guided_filter(y, ycc[..., c], radius, eps)
    return out


def sharpen_luma(ycc: np.ndarray, amount: float, sigma: float, coring: float) -> np.ndarray:
    if amount <= 0:
        return ycc
    y = ycc[..., 0]
    detail = y - cv2.GaussianBlur(y, (0, 0), sigma)
    d2 = detail * detail
    detail = detail * d2 / (d2 + coring * coring)
    out = ycc.copy()
    out[..., 0] = y + amount * detail
    return out


def finish(display_rgb: np.ndarray, cfg: FinishConfig = FinishConfig()) -> np.ndarray:
    ycc = rgb_to_ycbcr(display_rgb.astype(np.float32))
    ycc = chroma_denoise(ycc, cfg.chroma_radius, cfg.chroma_eps)
    ycc = sharpen_luma(ycc, cfg.sharpen_amount, cfg.sharpen_sigma, cfg.sharpen_coring)
    return np.clip(ycbcr_to_rgb(ycc), 0.0, 1.0)

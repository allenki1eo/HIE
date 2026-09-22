"""Per-pixel confidence maps for burst fusion.

Confidence is expressed in [0, 1] per alternate frame and pixel. The central
statistic is the *noise-normalised local residual*

    D²(x) = mean over a window and the 4 Bayer planes of (I_z - I_ref)² / (2 σ²(I_ref))

which is ≈ 1 where a frame agrees with the reference up to sensor noise and
grows where alignment failed or the scene moved. Robust per-pixel weighting of
this kind is established prior art (e.g. HDR+ and Super Res Zoom); see
``docs/prior-art.md``.
"""

from __future__ import annotations

import cv2
import numpy as np

from ..noise import NoiseModel


def local_mean(img: np.ndarray, window: int) -> np.ndarray:
    return cv2.blur(img.astype(np.float32), (window, window), borderType=cv2.BORDER_REFLECT)


def normalized_residual(ref: np.ndarray, alt: np.ndarray, noise: NoiseModel, window: int = 5) -> np.ndarray:
    """D² map (H, W): windowed mean of squared difference divided by its expected noise variance."""
    ref_smooth = np.stack([local_mean(ref[..., p], 3) for p in range(4)], axis=-1)
    var = noise.variance(ref_smooth)
    d2 = ((alt - ref) ** 2) / (2.0 * var + 1e-12)
    return local_mean(d2.mean(axis=-1), window)


def residual_confidence(d2: np.ndarray, tolerance: float = 0.5, softness: float = 0.75) -> np.ndarray:
    """Map D² to confidence: 1 while D² ≤ 1 + tolerance, then exponential fall-off."""
    excess = np.maximum(d2 - 1.0 - tolerance, 0.0)
    return np.exp(-excess / softness).astype(np.float32)


def saturation_confidence(planes: np.ndarray, threshold: float = 0.92, width: float = 0.06) -> np.ndarray:
    """1 below ``threshold`` of white on every plane, ramping to 0 at ``threshold + width``."""
    peak = planes.max(axis=-1)
    return np.clip((threshold + width - peak) / width, 0.0, 1.0).astype(np.float32)


def effective_frame_count(weights: np.ndarray) -> np.ndarray:
    """Kish effective sample size (Σw)² / Σw² for (N, H, W) weights."""
    s1 = weights.sum(axis=0)
    s2 = (weights * weights).sum(axis=0)
    return (s1 * s1 / np.maximum(s2, 1e-12)).astype(np.float32)

"""No-reference noise and artefact measurements for real bursts (no ground truth available)."""

from __future__ import annotations

import cv2
import numpy as np

from ..noise import NoiseModel
from ..raw.bayer import planes_to_gray

_IMMERKAER = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)


def immerkaer_sigma(img: np.ndarray, mask: np.ndarray | None = None) -> float:
    """Immerkær (1996) fast noise σ estimate; restrict to flat regions with ``mask``."""
    r = np.abs(cv2.filter2D(img.astype(np.float32), -1, _IMMERKAER, borderType=cv2.BORDER_REFLECT))
    r = r[mask] if mask is not None else r
    return float(np.sqrt(np.pi / 2.0) * r.mean() / 6.0)


def flat_mask(planes: np.ndarray, quantile: float = 0.3, border: int = 16) -> np.ndarray:
    """Low-gradient pixels of a (smoothed) plane image — where residual noise is measurable."""
    g = cv2.GaussianBlur(planes_to_gray(planes), (0, 0), 2.0)
    grad = np.hypot(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    mask = grad <= np.quantile(grad, quantile)
    mask[:border], mask[-border:], mask[:, :border], mask[:, -border:] = False, False, False, False
    return mask


def residual_noise(planes: np.ndarray, mask: np.ndarray) -> float:
    """Mean Immerkær σ over the four Bayer planes inside ``mask`` (normalised raw units)."""
    return float(np.mean([immerkaer_sigma(planes[..., p], mask) for p in range(4)]))


def reference_deviation_rate(
    merged: np.ndarray, reference: np.ndarray, noise: NoiseModel, *, sigma: float = 2.0, threshold: float = 5.0,
    border: int = 16,
) -> float:
    """Fraction of pixels where the low-passed merged image deviates from the low-passed reference
    by more than ``threshold`` standard deviations of the reference's own (low-passed) noise.

    A perfectly aligned static merge only differs from the reference by the reference's
    noise, so exceedances indicate *structured* deviations: ghosts, misalignment blur or
    lost detail. This is a proxy, not a ground-truth ghosting metric.
    """
    k = cv2.getGaussianKernel(int(6 * sigma) | 1, sigma)
    gain = float((k @ k.T).__pow__(2).sum())  # variance gain of the 2-D Gaussian for white noise
    d = planes_to_gray(merged) - planes_to_gray(reference)
    d = cv2.GaussianBlur(d, (0, 0), sigma)
    var = noise.variance(cv2.GaussianBlur(reference, (0, 0), sigma)).mean(axis=-1) / 4.0 * gain
    z = np.abs(d) / np.sqrt(var + 1e-12)
    z = z[border:-border, border:-border]
    return float((z > threshold).mean())

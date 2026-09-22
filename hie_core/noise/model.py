"""Poisson-Gaussian sensor noise model.

In normalised raw units (black = 0, white = 1) the per-pixel variance of a
linear sensor is well approximated by (Foi et al., 2008; DNG ``NoiseProfile``)::

    var(x) = S * x + O

where ``S`` scales signal-dependent shot noise and ``O`` is signal-independent
read noise. If a spatially varying gain ``g`` (e.g. lens shading) is applied
*after* capture, the variance of the gained value ``y = g * x`` becomes
``g * S * y + g**2 * O``.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..raw.bayer import planes_to_gray
from ..raw.frame import RawFrame


@dataclass(frozen=True)
class NoiseModel:
    shot: np.ndarray  # (4,) S per plane
    read: np.ndarray  # (4,) O per plane
    source: str = "manual"

    def __post_init__(self) -> None:
        object.__setattr__(self, "shot", np.broadcast_to(np.asarray(self.shot, dtype=np.float64), (4,)).copy())
        object.__setattr__(self, "read", np.broadcast_to(np.asarray(self.read, dtype=np.float64), (4,)).copy())

    def variance(self, planes: np.ndarray, gain: np.ndarray | None = None) -> np.ndarray:
        """Per-pixel variance for (…, 4) plane values; ``gain`` is an optional (…, 4) post-capture gain."""
        x = np.maximum(planes, 0.0)
        s = self.shot.astype(np.float32)
        o = self.read.astype(np.float32)
        if gain is None:
            return (s * x + o).astype(np.float32)
        return (gain * s * x + gain * gain * o).astype(np.float32)

    def std(self, planes: np.ndarray, gain: np.ndarray | None = None) -> np.ndarray:
        return np.sqrt(self.variance(planes, gain))

    def to_dict(self) -> dict:
        return {"shot": self.shot.tolist(), "read": self.read.tolist(), "source": self.source}

    # ------------------------------------------------------------------ constructors
    @classmethod
    def from_frame(cls, frame: RawFrame) -> "NoiseModel | None":
        params = frame.noise_params()
        if params is None:
            return None
        return cls(params[0], params[1], source="dng_noise_profile")

    @classmethod
    def estimate_from_burst(cls, frames: np.ndarray, *, bins: int = 24, flat_quantile: float = 0.3) -> "NoiseModel":
        """Fit (S, O) per plane from the temporal variance of an unaligned burst.

        Only pixels in flat regions (lowest ``flat_quantile`` of local gradient) are
        used, so hand-shake at edges does not inflate the variance. Per-intensity-bin
        medians are bias-corrected for the chi-square distribution of sample variances.
        """
        n = frames.shape[0]
        if n < 3:
            raise ValueError("Need at least 3 frames to estimate temporal noise")
        mean = frames.mean(axis=0)
        var = frames.var(axis=0, ddof=1)
        grad = _gradient_magnitude(planes_to_gray(mean))
        flat = grad <= np.quantile(grad, flat_quantile)
        k = n - 1
        median_to_mean = (1.0 - 2.0 / (9.0 * k)) ** 3  # Wilson-Hilferty median of chi2_k / k
        shot, read = np.zeros(4), np.zeros(4)
        for p in range(4):
            mu, v = mean[..., p][flat], var[..., p][flat] / median_to_mean
            shot[p], read[p] = _fit_affine_variance(mu, v, bins, use_median=True)
        return cls(shot, read, source=f"estimated_burst(n={n})")

    @classmethod
    def estimate_single(cls, planes: np.ndarray, *, bins: int = 24, flat_quantile: float = 0.3) -> "NoiseModel":
        """Fit (S, O) from a single frame with Immerkær's signal-cancelling Laplacian residual."""
        kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32) / 6.0  # residual var = var
        shot, read = np.zeros(4), np.zeros(4)
        grad = _gradient_magnitude(planes_to_gray(planes))
        flat = grad <= np.quantile(grad, flat_quantile)
        for p in range(4):
            plane = planes[..., p].astype(np.float32)
            resid = cv2.filter2D(plane, -1, kernel, borderType=cv2.BORDER_REFLECT)
            mu = cv2.blur(plane, (3, 3))
            # E[resid^2] = var for white noise with this normalisation (sum of squared taps = 36/36)
            shot[p], read[p] = _fit_affine_variance(mu[flat], (resid**2)[flat], bins, use_median=True, chi2_dof=1)
        return cls(shot, read, source="estimated_single")


def _gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    smooth = cv2.GaussianBlur(gray.astype(np.float32), (0, 0), 1.5)
    gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1)
    return np.sqrt(gx * gx + gy * gy)


def _fit_affine_variance(
    mu: np.ndarray, v: np.ndarray, bins: int, *, use_median: bool, chi2_dof: int | None = None
) -> tuple[float, float]:
    """Weighted least squares fit of v = S*mu + O over intensity bins (S, O >= 0)."""
    edges = np.unique(np.quantile(mu, np.linspace(0.0, 0.995, bins + 1)))
    xs, ys, ws = [], [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (mu >= lo) & (mu < hi)
        if sel.sum() < 64:
            continue
        stat = np.median(v[sel]) if use_median else v[sel].mean()
        if chi2_dof == 1:
            stat /= 0.4549  # median of chi2_1
        xs.append(np.median(mu[sel]))
        ys.append(stat)
        ws.append(np.sqrt(sel.sum()) / max(stat, 1e-12))
    if len(xs) < 2:
        raise ValueError("Not enough flat pixels to fit a noise model")
    x, y, w = map(np.asarray, (xs, ys, ws))
    a = np.stack([x, np.ones_like(x)], axis=1) * w[:, None]
    s, o = np.linalg.lstsq(a, y * w, rcond=None)[0]
    if s < 0:
        s, o = 0.0, float(np.average(y, weights=w))
    if o < 0:
        s, o = float(np.sum(w * w * x * y) / np.sum(w * w * x * x)), 0.0
    return float(s), float(o)

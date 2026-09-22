"""Full-reference fidelity metrics: PSNR, SSIM (Wang et al. 2004), MS-SSIM (Wang et al. 2003)."""

from __future__ import annotations

import cv2
import numpy as np

_MS_WEIGHTS = np.array([0.0448, 0.2856, 0.3001, 0.2363, 0.1333])


def psnr(x: np.ndarray, ref: np.ndarray, data_range: float = 1.0, mask: np.ndarray | None = None) -> float:
    d = (x.astype(np.float64) - ref.astype(np.float64)) ** 2
    if mask is not None:
        d = d[mask] if d.ndim == mask.ndim else d[mask, ...]
    mse = float(d.mean())
    return float("inf") if mse == 0 else 10.0 * np.log10(data_range**2 / mse)


def _ssim_maps(x: np.ndarray, y: np.ndarray, data_range: float) -> tuple[np.ndarray, np.ndarray]:
    c1, c2 = (0.01 * data_range) ** 2, (0.03 * data_range) ** 2
    blur = lambda a: cv2.GaussianBlur(a, (11, 11), 1.5, borderType=cv2.BORDER_REFLECT)  # noqa: E731
    mx, my = blur(x), blur(y)
    sxx = blur(x * x) - mx * mx
    syy = blur(y * y) - my * my
    sxy = blur(x * y) - mx * my
    cs = (2 * sxy + c2) / (sxx + syy + c2)
    lum = (2 * mx * my + c1) / (mx * mx + my * my + c1)
    return lum * cs, cs


def ssim(x: np.ndarray, ref: np.ndarray, data_range: float = 1.0, mask: np.ndarray | None = None) -> float:
    """Mean SSIM; multi-channel inputs are averaged over channels."""
    x = np.atleast_3d(x).astype(np.float64)
    ref = np.atleast_3d(ref).astype(np.float64)
    vals = []
    for c in range(x.shape[-1]):
        smap, _ = _ssim_maps(x[..., c], ref[..., c], data_range)
        vals.append(smap[mask].mean() if mask is not None else smap.mean())
    return float(np.mean(vals))


def ms_ssim(x: np.ndarray, ref: np.ndarray, data_range: float = 1.0) -> float:
    x = np.atleast_3d(x).astype(np.float64)
    ref = np.atleast_3d(ref).astype(np.float64)
    scores = []
    for c in range(x.shape[-1]):
        a, b = x[..., c], ref[..., c]
        mcs = []
        for level in range(len(_MS_WEIGHTS)):
            smap, cs = _ssim_maps(a, b, data_range)
            if level == len(_MS_WEIGHTS) - 1:
                mssim = max(smap.mean(), 1e-6)
            else:
                mcs.append(max(cs.mean(), 1e-6))
                a, b = cv2.resize(a, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), cv2.resize(
                    b, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        scores.append(np.prod(np.power(mcs, _MS_WEIGHTS[:-1])) * mssim ** _MS_WEIGHTS[-1])
    return float(np.mean(scores))


def detail_retention(x: np.ndarray, ref: np.ndarray, mask: np.ndarray | None = None, sigma: float = 1.0) -> float:
    """Fraction of the reference's fine-scale (band-pass) detail present in ``x``.

    ``E[bp(x)·bp(ref)] / E[bp(ref)²]`` over the most textured 30 % of ``mask``: noise in
    ``x`` is uncorrelated with the reference and cancels in expectation, while
    over-smoothing lowers the score below 1. Complements PSNR, which rewards smoothing.
    """
    def bandpass(a: np.ndarray) -> np.ndarray:
        a = np.atleast_3d(a).astype(np.float32)
        return np.stack([a[..., c] - cv2.GaussianBlur(a[..., c], (0, 0), sigma) for c in range(a.shape[-1])], -1)

    bx, br = bandpass(x), bandpass(ref)
    energy = (br * br).mean(axis=-1)
    region = energy >= np.quantile(energy[mask] if mask is not None else energy, 0.7)
    if mask is not None:
        region &= mask
    return float((bx * br).mean(axis=-1)[region].sum() / max(energy[region].sum(), 1e-12))

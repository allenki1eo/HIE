"""Frequency-domain merging and denoising on overlapping tiles.

``temporal_wiener_fusion`` reproduces the concept of the HDR+ pairwise temporal
merge (Hasinoff et al., 2016, §5): for each tile and each alternate frame z,

    T̃ = (1/N) Σ_z [ T_z(ω) + A_z(ω) (T_0(ω) - T_z(ω)) ],
    A_z(ω) = |D_z(ω)|² / (|D_z(ω)|² + k · 2 T² σ²),

with D_z = T_0 - T_z and σ² the tile's noise variance from the sensor model. The
factor 2T² is the expected |D|² of pure noise for an unnormalised T×T FFT, so
``k`` is a dimensionless robustness constant (the paper's ``c`` is defined under a
different normalisation and is not directly comparable).
"""

from __future__ import annotations

import numpy as np

from ..noise import NoiseModel
from .pixel import FusionResult
from .tiles import process_tiles


def temporal_wiener_fusion(
    frames: np.ndarray, ref_index: int, noise: NoiseModel, valid: np.ndarray | None = None,
    *, tile: int = 16, k: float = 1.0, **_: object,
) -> FusionResult:
    n = frames.shape[0]
    order = [ref_index] + [i for i in range(n) if i != ref_index]
    shot = noise.shot.astype(np.float32)[None, None, :]
    read = noise.read.astype(np.float32)[None, None, :]
    a_means: list[float] = []

    def merge(tiles: list[np.ndarray]) -> np.ndarray:
        ref = tiles[0]
        var = shot * np.maximum(ref.mean(axis=(-1, -2)), 0.0) + read  # (m, nx, C)
        noise_power = (k * 2.0 * tile * tile * var)[..., None, None]
        ref_f = np.fft.rfft2(ref)
        acc = ref_f.copy()
        for alt in tiles[1:]:
            alt_f = np.fft.rfft2(alt)
            d = ref_f - alt_f
            d2 = d.real**2 + d.imag**2
            a = d2 / (d2 + noise_power)
            a_means.append(float(a.mean()))
            acc += alt_f + a * d
        return np.fft.irfft2(acc / n, s=(tile, tile)).astype(np.float32)

    merged = process_tiles([frames[i] for i in order], tile, merge)
    return FusionResult(merged, None, {"mean_shrinkage": float(np.mean(a_means)) if a_means else 0.0, "k": k})


def spatial_wiener_denoise(
    planes: np.ndarray, variance: np.ndarray, *, tile: int = 16, strength: float = 1.0
) -> np.ndarray:
    """Empirical Wiener shrinkage per tile: G(ω) = |X|² / (|X|² + strength · T² σ²), DC preserved.

    ``variance`` is the per-pixel (H, W, 4) residual noise variance of ``planes``
    (e.g. σ²/N_eff after a merge), averaged per tile.
    """
    if strength <= 0:
        return planes

    def shrink(tiles: list[np.ndarray]) -> np.ndarray:
        x, v = tiles
        noise_power = (strength * tile * tile * v.mean(axis=(-1, -2)))[..., None, None]
        xf = np.fft.rfft2(x)
        p = xf.real**2 + xf.imag**2
        g = p / (p + noise_power)
        g[..., 0, 0] = 1.0
        return np.fft.irfft2(xf * g, s=(tile, tile)).astype(np.float32)

    return process_tiles([planes, variance.astype(np.float32)], tile, shrink)

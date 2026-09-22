"""Pixel-domain burst fusion baselines (brief §8, baselines 1-4 and EXP-005).

All functions take aligned frames ``(N, H, W, 4)`` in normalised linear Bayer-plane
units plus the reference index, and return a :class:`FusionResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from ..confidence import (
    effective_frame_count, normalized_residual, residual_confidence, saturation_confidence,
)
from ..noise import NoiseModel
from ..raw.bayer import planes_to_gray


@dataclass
class FusionResult:
    planes: np.ndarray  # (H, W, 4) merged
    n_eff: np.ndarray | None = None  # (H, W) effective number of merged frames
    info: dict[str, Any] = field(default_factory=dict)


def _valid_weights(frames: np.ndarray, ref_index: int, valid: np.ndarray | None) -> np.ndarray:
    w = np.ones(frames.shape[:3], dtype=np.float32) if valid is None else valid.astype(np.float32)
    w[ref_index] = 1.0
    return w


def mean_fusion(frames: np.ndarray, ref_index: int = 0, valid: np.ndarray | None = None, **_: Any) -> FusionResult:
    """Baseline 1: per-pixel average of the aligned frames."""
    w = _valid_weights(frames, ref_index, valid)
    merged = (frames * w[..., None]).sum(axis=0) / w.sum(axis=0)[..., None]
    return FusionResult(merged.astype(np.float32), effective_frame_count(w))


def median_fusion(frames: np.ndarray, ref_index: int = 0, valid: np.ndarray | None = None, **_: Any) -> FusionResult:
    """Baseline 2: per-pixel temporal median (robust to outliers, but noisier than the mean)."""
    stack = frames.copy()
    if valid is not None:
        invalid = ~valid.astype(bool)
        invalid[ref_index] = False
        stack[invalid] = np.nan
    merged = np.nanmedian(stack, axis=0)
    n = frames.shape[0] if valid is None else _valid_weights(frames, ref_index, valid).sum(axis=0)
    # asymptotic efficiency of the median vs the mean for Gaussian noise is 2/π
    n_eff = np.broadcast_to(np.asarray(n, dtype=np.float32) * (2.0 / np.pi), frames.shape[1:3])
    return FusionResult(merged.astype(np.float32), np.maximum(n_eff, 1.0).astype(np.float32))


def frame_sharpness(frames: np.ndarray, noise: NoiseModel | None = None) -> np.ndarray:
    """Per-frame sharpness: energy of a band-pass (Laplacian of Gaussian) response, noise-corrected."""
    scores = []
    for f in frames:
        g = cv2.GaussianBlur(planes_to_gray(f), (0, 0), 1.0)
        lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
        scores.append(float(np.mean(lap * lap)))
    s = np.asarray(scores)
    return s / s.max()


def weighted_fusion(
    frames: np.ndarray, ref_index: int = 0, valid: np.ndarray | None = None, *, sharpness_power: float = 2.0, **_: Any
) -> FusionResult:
    """Baseline 3: weights from global frame sharpness ("lucky imaging") and saturation proximity."""
    sharp = frame_sharpness(frames) ** sharpness_power
    w = _valid_weights(frames, ref_index, valid) * sharp[:, None, None].astype(np.float32)
    w *= np.stack([saturation_confidence(f) for f in frames])
    w[ref_index] = np.maximum(w[ref_index], 1e-3)
    merged = (frames * w[..., None]).sum(axis=0) / w.sum(axis=0)[..., None]
    return FusionResult(merged.astype(np.float32), effective_frame_count(w), {"frame_sharpness": sharp.tolist()})


def motion_aware_fusion(
    frames: np.ndarray, ref_index: int, noise: NoiseModel, valid: np.ndarray | None = None,
    *, shrink: float = 2.0, window: int = 5, **_: Any,
) -> FusionResult:
    """Baseline 4: pixel-domain temporal Wiener shrinkage toward the reference.

    Each alternate frame contributes ``Z + A (R - Z)`` with
    ``A = e / (e + shrink)`` and ``e = max(D² - 1, 0)`` the excess of the
    noise-normalised residual. Static, well-aligned regions (e ≈ 0) are averaged
    fully; moving regions fall back to the reference.
    """
    ref = frames[ref_index]
    acc = ref.astype(np.float32).copy()
    weights = [np.ones(ref.shape[:2], np.float32)]
    for z in range(frames.shape[0]):
        if z == ref_index:
            continue
        alt = frames[z]
        excess = np.maximum(normalized_residual(ref, alt, noise, window) - 1.0, 0.0)
        a = excess / (excess + shrink)
        if valid is not None:
            a = np.where(valid[z], a, 1.0)
        acc += alt + a[..., None] * (ref - alt)
        weights.append(1.0 - a)
    merged = acc / frames.shape[0]
    return FusionResult(merged.astype(np.float32), effective_frame_count(np.stack(weights)))


def confidence_fusion(
    frames: np.ndarray, ref_index: int, noise: NoiseModel, valid: np.ndarray | None = None,
    *, tolerance: float = 0.5, softness: float = 0.75, window: int = 5, use_sharpness: bool = True, **_: Any,
) -> FusionResult:
    """EXP-005: weighted mean with explicit per-pixel confidence.

    ``w_z(x) = C_residual · C_saturation · C_valid · s_z`` where ``s_z`` is the
    relative frame sharpness. The reference has weight 1. Returns the effective
    frame count so later stages can reason about residual uncertainty
    (σ²_merged ≈ σ² / N_eff).
    """
    ref = frames[ref_index]
    sharp = frame_sharpness(frames) if use_sharpness else np.ones(frames.shape[0])
    weights = np.zeros(frames.shape[:3], dtype=np.float32)
    residual_stats = []
    for z in range(frames.shape[0]):
        if z == ref_index:
            weights[z] = 1.0
            continue
        d2 = normalized_residual(ref, frames[z], noise, window)
        c = residual_confidence(d2, tolerance, softness) * saturation_confidence(frames[z])
        if valid is not None:
            c = c * valid[z]
        weights[z] = c * min(1.0, sharp[z] / max(sharp[ref_index], 1e-6))
        residual_stats.append(float(np.median(d2)))
    merged = (frames * weights[..., None]).sum(axis=0) / weights.sum(axis=0)[..., None]
    return FusionResult(
        merged.astype(np.float32), effective_frame_count(weights),
        {"median_d2": residual_stats, "frame_sharpness": sharp.tolist(), "mean_weight": float(weights.mean())},
    )

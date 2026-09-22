"""Tone mapping.

``local`` implements HDR+-style *synthetic exposure fusion* (Hasinoff et al.
2016, §6, building on Mertens et al. 2007): the linear image is rendered at
several virtual exposures between a highlight-preserving "short" gain and a
shadow-lifting "long" gain, and the renders are blended with a Laplacian pyramid
using well-exposedness weights. Fusion runs on luminance only; the resulting
per-pixel gain is applied to all three channels so hue and saturation are kept.

``fixed`` applies a known gain and the sRGB curve — used by benchmarks, where
content-adaptive tone mapping would confound the comparison of merge methods.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..color.spaces import luminance, srgb_decode, srgb_encode


@dataclass(frozen=True)
class ToneConfig:
    mode: str = "local"  # "local" | "global" | "fixed"
    fixed_gain: float = 1.0
    highlight_percentile: float = 99.7
    highlight_target: float = 0.92
    key_target: float = 0.20  # target geometric-mean luminance (linear) after the long exposure
    max_compression: float = 8.0  # max long/short gain ratio (≈ 3 EV of shadow lift)
    max_gain: float = 64.0
    exposures: int = 3
    well_exposed_sigma: float = 0.2
    contrast: float = 0.18  # strength of the final S-curve (0 = none)
    saturation: float = 1.08  # chroma scale applied in linear light after tone mapping
    black_point: float = 0.0015  # linear black clip after exposure


@dataclass
class ToneResult:
    display: np.ndarray  # (H, W, 3) display-referred sRGB in [0, 1]
    short_gain: float
    long_gain: float


def auto_gains(y: np.ndarray, cfg: ToneConfig) -> tuple[float, float]:
    """Choose short (highlights) and long (shadows) linear gains from luminance statistics."""
    y = np.maximum(y, 0.0)
    sample = y[::4, ::4]
    hi = float(np.percentile(sample, cfg.highlight_percentile))
    short = float(np.clip(cfg.highlight_target / max(hi, 1e-6), 1.0, cfg.max_gain))
    key = float(np.exp(np.mean(np.log(sample * short + 1e-4))))
    ratio = float(np.clip(cfg.key_target / max(key, 1e-6), 1.0, cfg.max_compression))
    return short, short * ratio


def _gauss_pyr(img: np.ndarray, levels: int) -> list[np.ndarray]:
    pyr = [img]
    for _ in range(levels - 1):
        pyr.append(cv2.pyrDown(pyr[-1]))
    return pyr


def _lap_pyr(img: np.ndarray, levels: int) -> list[np.ndarray]:
    g = _gauss_pyr(img, levels)
    lap = [g[i] - cv2.pyrUp(g[i + 1], dstsize=g[i].shape[1::-1]) for i in range(levels - 1)]
    return lap + [g[-1]]


def _collapse(lap: list[np.ndarray]) -> np.ndarray:
    img = lap[-1]
    for level in reversed(lap[:-1]):
        img = cv2.pyrUp(img, dstsize=level.shape[1::-1]) + level
    return img


def exposure_fusion(y: np.ndarray, gains: list[float], sigma: float) -> np.ndarray:
    """Blend sRGB-encoded renders of luminance ``y`` at ``gains``; returns display-referred luma."""
    levels = max(1, int(np.log2(min(y.shape))) - 4)
    renders = [srgb_encode(y * g) for g in gains]
    weights = [np.exp(-((r - 0.5) ** 2) / (2 * sigma * sigma)).astype(np.float32) + 1e-6 for r in renders]
    total = np.sum(weights, axis=0)
    fused = None
    for r, w in zip(renders, weights):
        wl = _gauss_pyr((w / total).astype(np.float32), levels)
        rl = _lap_pyr(r.astype(np.float32), levels)
        contrib = [a * b for a, b in zip(wl, rl)]
        fused = contrib if fused is None else [f + c for f, c in zip(fused, contrib)]
    return np.clip(_collapse(fused), 0.0, 1.0)


def s_curve(v: np.ndarray, strength: float) -> np.ndarray:
    """Mild contrast curve on display values that fixes 0 and 1."""
    if strength <= 0:
        return v
    return ((1 - strength) * v + strength * v * v * (3 - 2 * v)).astype(np.float32)


def tone_map(rgb_linear: np.ndarray, cfg: ToneConfig = ToneConfig()) -> ToneResult:
    rgb = np.maximum(rgb_linear, 0.0).astype(np.float32)
    y = luminance(rgb)
    if cfg.mode == "fixed":
        return ToneResult(srgb_encode(rgb * cfg.fixed_gain), cfg.fixed_gain, cfg.fixed_gain)

    short, long_ = auto_gains(y, cfg)
    if cfg.mode == "global" or long_ / short < 1.05:
        gains_y = np.full_like(y, short)
    else:
        n = max(2, cfg.exposures)
        gains = list(np.geomspace(short, long_, n))
        fused = exposure_fusion(y, gains, cfg.well_exposed_sigma)
        gains_y = srgb_decode(fused) / np.maximum(y, 1e-6)
        gains_y = np.minimum(gains_y, long_)  # never exceed the brightest synthetic exposure
    out = rgb * gains_y[..., None]
    out = np.maximum(out - cfg.black_point, 0.0) / (1.0 - cfg.black_point)
    y_out = luminance(out)[..., None]
    out = y_out + cfg.saturation * (out - y_out)
    out = _compress_gamut(out)
    display = s_curve(srgb_encode(out), cfg.contrast)
    return ToneResult(display, short, long_)


def _compress_gamut(rgb: np.ndarray) -> np.ndarray:
    """Pull out-of-range colours toward their luminance instead of hard-clipping each channel."""
    y = np.clip(luminance(rgb), 0.0, 1.0)[..., None]
    over = np.maximum(rgb.max(axis=-1, keepdims=True), 1.0)
    under = np.minimum(rgb.min(axis=-1, keepdims=True), 0.0)
    t_hi = np.where(over > 1.0, (1.0 - y) / np.maximum(over - y, 1e-6), 1.0)
    t_lo = np.where(under < 0.0, y / np.maximum(y - under, 1e-6), 1.0)
    t = np.clip(np.minimum(t_hi, t_lo), 0.0, 1.0)
    return np.clip(y + t * (rgb - y), 0.0, 1.0)

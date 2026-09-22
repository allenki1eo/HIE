"""Hierarchical tile-based alignment in the style of HDR+ (Hasinoff et al., SIGGRAPH Asia 2016, §4).

A Gaussian pyramid is built on the 2x2-averaged Bayer gray image. Tiles are
matched coarse-to-fine; each level searches a small window around a prior
displacement propagated from the coarser level. Sub-pixel displacements are
estimated at every level and carried (not rounded) to the next one. Propagation tests three
candidate priors (the enclosing coarse tile and its two nearest neighbours),
which avoids dragging a wrong displacement across object boundaries. The finest
level uses an L1 cost; a separable parabola fit of L2 costs gives sub-pixel
precision. Parameters are exposed rather than presented as the exact HDR+ tuning.

Noise-aware acceptance (optional, enabled when a :class:`NoiseModel` is given): a
tile only moves away from its propagated prior when the cost improvement exceeds
``significance`` standard deviations of the cost fluctuation that sensor noise
alone would produce at that pyramid level. At high SNR this never binds; at very
low SNR it stops fine levels from locking onto noise minima (see
docs/benchmark.md, failure analysis F1).
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..noise import NoiseModel
from .base import Alignment

# Noise statistics of a cv2.pyrDown pyramid built on white noise, measured empirically
# (4096² N(0,1) field). Only the first pyrDown sees white noise (variance ×0.0748); later
# levels average already-correlated noise and shrink it ≈ 4× per step. Correlation also
# inflates the variance of a tile's sum of squares relative to independent samples.
_PYR_VAR = np.array([1.0, 0.0748, 0.0152, 0.00363, 0.000899, 0.00023, 5.8e-05])
_PYR_SUMSQ_INFLATION = np.array([1.0, 1.71, 1.99, 2.0, 2.0, 2.0, 2.0])


@dataclass(frozen=True)
class TileAlignParams:
    # Five levels with ×2 steps (coarsest ×4): each level only has to correct the rounding
    # error of the previous one, which keeps searches small at low SNR (failure analysis F1).
    tile_sizes: tuple[int, ...] = (16, 16, 16, 16, 8)  # finest → coarsest
    factors: tuple[int, ...] = (1, 2, 2, 2, 4)  # downsampling relative to the previous level
    radii: tuple[int, ...] = (1, 2, 2, 2, 4)
    norms: tuple[str, ...] = ("l1", "l2", "l2", "l2", "l2")
    subpixel: bool = True
    significance: float = 3.0  # noise-aware acceptance threshold (σ of the noise-only cost)
    median_smooth: int = 0  # k×k median filter on each level's displacement field (0 = off)


def _downsample(img: np.ndarray, factor: int) -> np.ndarray:
    out = img
    for _ in range(int(np.log2(factor))):
        out = cv2.pyrDown(out)
    return out


def _gather(img: np.ndarray, ty: np.ndarray, tx: np.ndarray, tile: int, dy: np.ndarray, dx: np.ndarray) -> np.ndarray:
    """Gather (n, T, T) patches whose top-left corners are (ty + dy, tx + dx); edges are clamped."""
    h, w = img.shape
    ar = np.arange(tile)
    rows = np.clip(ty[:, None] + dy[:, None] + ar[None, :], 0, h - 1)
    cols = np.clip(tx[:, None] + dx[:, None] + ar[None, :], 0, w - 1)
    return img[rows[:, :, None], cols[:, None, :]]


def _cost(ref_tiles: np.ndarray, alt_tiles: np.ndarray, norm: str) -> np.ndarray:
    d = ref_tiles - alt_tiles
    return (np.abs(d) if norm == "l1" else d * d).sum(axis=(1, 2))


def _inside(shape: tuple[int, int], ty, tx, tile: int, dy, dx) -> np.ndarray:
    """True where the displaced tile keeps at least half of each side inside the image.

    Edge clamping replicates border pixels; a mostly-outside tile would be compared
    against a flat patch, which can spuriously beat an honest noisy match.
    """
    h, w = shape
    half = tile // 2
    y, x = ty + dy, tx + dx
    return (y >= -half) & (y + tile <= h + half) & (x >= -half) & (x + tile <= w + half)


class TileAligner:
    name = "hdrplus_tiles"

    def __init__(self, params: TileAlignParams | None = None, noise: NoiseModel | None = None):
        self.p = params or TileAlignParams()
        self.noise = noise

    def __call__(self, ref_gray: np.ndarray, alt_gray: np.ndarray) -> Alignment:
        p = self.p
        pyr_ref, pyr_alt = [ref_gray.astype(np.float32)], [alt_gray.astype(np.float32)]
        for lvl, f in enumerate(p.factors[1:], start=1):
            nxt = _downsample(pyr_ref[-1], f)
            if min(nxt.shape) < 2 * p.tile_sizes[lvl]:
                break  # a level must hold at least 2x2 tiles to be meaningful
            pyr_ref.append(nxt)
            pyr_alt.append(_downsample(pyr_alt[-1], f))
        levels = len(pyr_ref)

        level_records = []
        disp = None  # (ny, nx, 2) integer (dy, dx) at the current level
        coarse = None  # (stride, tile) of the previous (coarser) level
        n_pyrdowns = np.concatenate([[0], np.cumsum(np.log2(p.factors[1:]).astype(int))])
        for lvl in reversed(range(levels)):
            ref, alt = pyr_ref[lvl], pyr_alt[lvl]
            h, w = ref.shape
            tile = min(p.tile_sizes[lvl], h, w)
            stride = tile // 2 if lvl == 0 else tile
            ny, nx = -(-h // stride), -(-w // stride)
            gy, gx = np.meshgrid(np.arange(ny) * stride, np.arange(nx) * stride, indexing="ij")
            ty, tx = gy.ravel(), gx.ravel()
            zeros = np.zeros_like(ty)
            ref_tiles = _gather(ref, ty, tx, tile, zeros, zeros)

            if disp is None:
                prior = np.zeros((ty.size, 2), dtype=np.int64)
            else:
                prior = self._propagate(disp, coarse, p.factors[lvl + 1], ty, tx, tile, ref_tiles, alt)

            cost_std = self._noise_cost_std(ref_tiles, tile, p.norms[lvl], int(n_pyrdowns[lvl]))
            best, best_cost = self._search(
                ref_tiles, alt, ty, tx, tile, prior, p.radii[lvl], p.norms[lvl],
                None if cost_std is None else p.significance * cost_std,
            )
            sub = np.zeros(best.shape, dtype=np.float32)
            if p.subpixel:
                cost_std = self._noise_cost_std(ref_tiles, tile, "l2", int(n_pyrdowns[lvl]))
                min_curv = None if cost_std is None else p.significance * cost_std
                sub = self._subpixel(ref_tiles, alt, ty, tx, tile, best, min_curv)
            # fractional displacement is carried to the next level so priors are rounded only once
            disp = (best + sub).reshape(ny, nx, 2).astype(np.float32)
            if p.median_smooth > 1 and min(ny, nx) >= p.median_smooth:
                disp = np.stack([cv2.medianBlur(disp[..., c], p.median_smooth) for c in range(2)], axis=-1)
            coarse = (stride, tile)
            level_records.append({"level": lvl, "stride": stride, "tile": tile, "disp_dydx": disp.copy()})

        stride, tile = coarse
        tile_flow = disp  # (dy, dx), sub-pixel
        flow = _densify(tile_flow[..., ::-1], stride, tile, ref_gray.shape)
        info = {
            "tile_size": tile,
            "stride": stride,
            "tile_flow_dxdy": tile_flow[..., ::-1],
            "tile_cost": (best_cost / (tile * tile)).reshape(disp.shape[:2]),
            "levels": level_records,
        }
        return Alignment(flow, self.name, info)

    # ------------------------------------------------------------------ helpers
    def _noise_cost_std(self, ref_tiles: np.ndarray, tile: int, norm: str, n_down: int) -> np.ndarray | None:
        """Std of the difference between two tile matching costs under noise alone.

        Gray is the mean of 4 planes (variance /4) and ``n_down`` pyrDowns scale it by
        ``_PYR_VAR``. For per-pixel variance v the frame difference has variance 2v, so for
        independent pixels the L2 cost has std 2√2·v·T and the L1 cost T·sqrt(2v(1 - 2/π));
        correlation inflates both by sqrt(_PYR_SUMSQ_INFLATION). Returns None without a noise model.
        """
        if self.noise is None:
            return None
        n_down = min(n_down, len(_PYR_VAR) - 1)
        mean = np.maximum(ref_tiles.mean(axis=(1, 2)), 0.0)
        v = (float(self.noise.shot.mean()) * mean + float(self.noise.read.mean())) / 4.0 * _PYR_VAR[n_down]
        corr = _PYR_SUMSQ_INFLATION[n_down]
        # decisions compare two costs, so use the std of a *difference* of costs (×√2)
        if norm == "l2":
            return np.sqrt(2.0) * 2.0 * np.sqrt(2.0) * v * tile * np.sqrt(corr)
        return np.sqrt(2.0) * tile * np.sqrt(2.0 * v * (1.0 - 2.0 / np.pi) * corr)

    @staticmethod
    def _propagate(disp, coarse, factor, ty, tx, tile, ref_tiles, alt) -> np.ndarray:
        """Upsample coarse displacements, choosing the best of three candidate priors per tile."""
        c_stride, _ = coarse
        cny, cnx = disp.shape[:2]
        cy = (ty + tile / 2.0) / factor
        cx = (tx + tile / 2.0) / factor
        ci = np.clip((cy // c_stride).astype(np.int64), 0, cny - 1)
        cj = np.clip((cx // c_stride).astype(np.int64), 0, cnx - 1)
        ni = np.clip(np.where(cy - ci * c_stride < c_stride / 2, ci - 1, ci + 1), 0, cny - 1)
        nj = np.clip(np.where(cx - cj * c_stride < c_stride / 2, cj - 1, cj + 1), 0, cnx - 1)
        candidates = [np.rint(disp[i, j] * factor).astype(np.int64) for i, j in ((ci, cj), (ni, cj), (ci, nj))]
        costs = np.stack([
            np.where(_inside(alt.shape, ty, tx, tile, c[:, 0], c[:, 1]),
                     _cost(ref_tiles, _gather(alt, ty, tx, tile, c[:, 0], c[:, 1]), "l1"), np.inf)
            for c in candidates
        ], axis=0)
        costs[0] = np.where(np.isinf(costs).all(axis=0), 0.0, costs[0])  # keep the enclosing tile's prior
        choice = costs.argmin(axis=0)
        return np.stack(candidates, axis=0)[choice, np.arange(ty.size)]

    @staticmethod
    def _search(ref_tiles, alt, ty, tx, tile, prior, radius, norm, min_gain=None):
        best_cost = np.full(ty.size, np.inf, dtype=np.float64)
        best = prior.copy()
        prior_cost = None
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                dy, dx = prior[:, 0] + oy, prior[:, 1] + ox
                cost = _cost(ref_tiles, _gather(alt, ty, tx, tile, dy, dx), norm)
                if oy or ox:
                    cost = np.where(_inside(alt.shape, ty, tx, tile, dy, dx), cost, np.inf)
                if oy == 0 and ox == 0:
                    prior_cost = cost
                # prefer the smaller displacement on ties so flat tiles stay put
                better = cost < best_cost - 1e-9
                best_cost = np.where(better, cost, best_cost)
                best[better, 0], best[better, 1] = dy[better], dx[better]
        if min_gain is not None:
            keep = (prior_cost - best_cost) < min_gain  # improvement not distinguishable from noise
            best[keep] = prior[keep]
            best_cost = np.where(keep, prior_cost, best_cost)
        return best, best_cost

    @staticmethod
    def _subpixel(ref_tiles, alt, ty, tx, tile, disp, min_curvature=None) -> np.ndarray:
        c = {}
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                if oy and ox:
                    continue
                c[(oy, ox)] = _cost(ref_tiles, _gather(alt, ty, tx, tile, disp[:, 0] + oy, disp[:, 1] + ox), "l2")

        def vertex(cm, c0, cp):
            den = cm - 2 * c0 + cp
            with np.errstate(divide="ignore", invalid="ignore"):
                off = np.where(den > 1e-12, 0.5 * (cm - cp) / den, 0.0)
            return np.clip(off, -0.5, 0.5)

        sy = vertex(c[(-1, 0)], c[(0, 0)], c[(1, 0)])
        sx = vertex(c[(0, -1)], c[(0, 0)], c[(0, 1)])
        if min_curvature is not None:  # only trust a parabola whose curvature stands above noise
            sy = np.where(c[(-1, 0)] - 2 * c[(0, 0)] + c[(1, 0)] > min_curvature, sy, 0.0)
            sx = np.where(c[(0, -1)] - 2 * c[(0, 0)] + c[(0, 1)] > min_curvature, sx, 0.0)
        return np.stack([sy, sx], axis=-1).astype(np.float32)


def _densify(tile_flow_dxdy: np.ndarray, stride: int, tile: int, shape: tuple[int, int]) -> np.ndarray:
    """Bilinearly interpolate per-tile (dx, dy) defined at tile centres to every pixel."""
    h, w = shape
    centre = (tile - 1) / 2.0
    gx = ((np.arange(w, dtype=np.float32) - centre) / stride)[None, :].repeat(h, 0)
    gy = ((np.arange(h, dtype=np.float32) - centre) / stride)[:, None].repeat(w, 1)
    grid = np.ascontiguousarray(tile_flow_dxdy, dtype=np.float32)
    return cv2.remap(grid, gx, gy, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

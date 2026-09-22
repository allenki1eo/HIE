"""Overlapping-tile machinery for frequency-domain processing.

Tiles of size T are taken with stride T/2. A raised-cosine window
``w(x) = 1/2 - 1/2 cos(2π(x + 1/2) / T)`` applied once at synthesis sums exactly to
one under this overlap, so unmodified tiles reconstruct the input perfectly.
Processing is done in horizontal strips of tile rows to bound memory on
12-megapixel bursts.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def raised_cosine(tile: int) -> np.ndarray:
    x = np.arange(tile, dtype=np.float64)
    w1 = 0.5 - 0.5 * np.cos(2.0 * np.pi * (x + 0.5) / tile)
    return np.outer(w1, w1).astype(np.float32)


def pad_for_tiles(img: np.ndarray, tile: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Reflect-pad (H, W, C) by T/2 on each side and up to the tile grid; returns (padded, (top, left))."""
    s = tile // 2
    h, w = img.shape[:2]
    extra_h = (-(h + 2 * s - tile)) % s
    extra_w = (-(w + 2 * s - tile)) % s
    pad = [(s, s + extra_h), (s, s + extra_w)] + [(0, 0)] * (img.ndim - 2)
    return np.pad(img, pad, mode="reflect"), (s, s)


def tile_view(img: np.ndarray, tile: int) -> np.ndarray:
    """(ny, nx, C, T, T) strided view of a padded (H, W, C) image."""
    s = tile // 2
    return sliding_window_view(img, (tile, tile), axis=(0, 1))[::s, ::s]


def process_tiles(
    images: list[np.ndarray],
    tile: int,
    fn: Callable[[list[np.ndarray]], np.ndarray],
    *,
    rows_per_strip: int = 24,
) -> np.ndarray:
    """Run ``fn`` over aligned tiles of several same-shaped (H, W, C) images and overlap-add the result.

    ``fn`` receives a list of (m, nx, C, T, T) float32 tile stacks (one per input image)
    and returns processed (m, nx, C, T, T) tiles for the output.
    """
    h, w = images[0].shape[:2]
    padded = []
    for im in images:
        p, (top, left) = pad_for_tiles(im.astype(np.float32, copy=False), tile)
        padded.append(p)
    views = [tile_view(p, tile) for p in padded]
    ny, nx = views[0].shape[:2]
    s = tile // 2
    window = raised_cosine(tile)
    out = np.zeros(padded[0].shape, dtype=np.float32)
    for r0 in range(0, ny, rows_per_strip):
        r1 = min(ny, r0 + rows_per_strip)
        tiles = [np.ascontiguousarray(v[r0:r1]) for v in views]
        res = fn(tiles) * window
        _overlap_add(out, res, r0, s, tile)
    return out[top : top + h, left : left + w]


def _overlap_add(out: np.ndarray, tiles: np.ndarray, row0: int, stride: int, tile: int) -> None:
    """Add (m, nx, C, T, T) tiles into ``out``; tiles of equal parity do not overlap."""
    m, nx, c = tiles.shape[:3]
    for pi in (0, 1):
        for pj in (0, 1):
            sub = tiles[pi::2, pj::2]
            if sub.size == 0:
                continue
            my, mx = sub.shape[:2]
            block = sub.transpose(0, 3, 1, 4, 2).reshape(my * tile, mx * tile, c)
            y0 = (row0 + pi) * stride
            x0 = pj * stride
            out[y0 : y0 + my * tile, x0 : x0 + mx * tile] += block

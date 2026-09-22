"""Bayer mosaic utilities.

HIE works on Bayer data as four half-resolution *planes* in a canonical order::

    PLANES = ("R", "Gr", "Gb", "B")

``Gr`` is the green sample that shares a row with red, ``Gb`` the one sharing a
row with blue. This matches the channel order of the Google HDR+ lens-shading
maps and the Android ``LENS_SHADING_MAP`` convention, and it makes every
algorithm independent of which 2x2 CFA phase a sensor uses.
"""

from __future__ import annotations

import numpy as np

PLANES: tuple[str, str, str, str] = ("R", "Gr", "Gb", "B")
SUPPORTED_PATTERNS = ("RGGB", "BGGR", "GRBG", "GBRG")


def validate_pattern(pattern: str) -> str:
    pattern = pattern.upper()
    if pattern not in SUPPORTED_PATTERNS:
        raise ValueError(f"Unsupported CFA pattern {pattern!r}; expected one of {SUPPORTED_PATTERNS}")
    return pattern


def plane_offsets(pattern: str) -> dict[str, tuple[int, int]]:
    """Return the (row, col) offset inside the 2x2 CFA tile for each canonical plane."""
    pattern = validate_pattern(pattern)
    grid = [[pattern[0], pattern[1]], [pattern[2], pattern[3]]]
    offsets: dict[str, tuple[int, int]] = {}
    for r in range(2):
        for c in range(2):
            color = grid[r][c]
            if color == "R":
                offsets["R"] = (r, c)
            elif color == "B":
                offsets["B"] = (r, c)
            else:  # green: classify by the colour sharing its row
                row_other = grid[r][1 - c]
                offsets["Gr" if row_other == "R" else "Gb"] = (r, c)
    return offsets


def pattern_from_cfa_codes(codes: tuple[int, ...] | list[int] | bytes) -> str:
    """Convert a TIFF/EP ``CFAPattern`` (0=R, 1=G, 2=B) for a 2x2 repeat into a string."""
    names = {0: "R", 1: "G", 2: "B"}
    codes = list(codes)
    if len(codes) != 4 or any(c not in names for c in codes):
        raise ValueError(f"Only 2x2 RGB Bayer CFA patterns are supported, got {codes}")
    return validate_pattern("".join(names[c] for c in codes))


def even_crop(cfa: np.ndarray) -> np.ndarray:
    """Crop a mosaic to even dimensions so it tiles exactly into 2x2 CFA blocks."""
    h, w = cfa.shape[:2]
    return cfa[: h - h % 2, : w - w % 2]


def to_planes(cfa: np.ndarray, pattern: str) -> np.ndarray:
    """Split an (H, W) mosaic into an (H/2, W/2, 4) array in :data:`PLANES` order."""
    cfa = even_crop(cfa)
    offs = plane_offsets(pattern)
    return np.stack([cfa[offs[p][0] :: 2, offs[p][1] :: 2] for p in PLANES], axis=-1)


def from_planes(planes: np.ndarray, pattern: str) -> np.ndarray:
    """Inverse of :func:`to_planes`."""
    h2, w2, n = planes.shape
    if n != 4:
        raise ValueError("Expected 4 Bayer planes")
    cfa = np.empty((h2 * 2, w2 * 2), dtype=planes.dtype)
    for i, name in enumerate(PLANES):
        r, c = plane_offsets(pattern)[name]
        cfa[r::2, c::2] = planes[..., i]
    return cfa


def color_masks(shape: tuple[int, int], pattern: str) -> dict[str, np.ndarray]:
    """Boolean masks (H, W) selecting R, G and B sites of a mosaic."""
    h, w = shape
    offs = plane_offsets(pattern)
    masks = {k: np.zeros((h, w), dtype=bool) for k in ("R", "G", "B")}
    for name, (r, c) in offs.items():
        masks["G" if name.startswith("G") else name][r::2, c::2] = True
    return masks


def planes_to_gray(planes: np.ndarray) -> np.ndarray:
    """2x2 box average of the Bayer tile — the half-resolution luminance proxy HDR+ aligns on."""
    return planes.mean(axis=-1, dtype=np.float32)


def planes_to_rgb_half(planes: np.ndarray) -> np.ndarray:
    """Cheap half-resolution RGB (R, mean(G), B) — useful for previews and quick metrics."""
    return np.stack(
        [planes[..., 0], 0.5 * (planes[..., 1] + planes[..., 2]), planes[..., 3]], axis=-1
    ).astype(np.float32)

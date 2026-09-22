"""CIEDE2000 colour difference (Sharma, Wu & Dalal, Color Res. Appl. 2005)."""

from __future__ import annotations

import numpy as np

from ..color.spaces import srgb_to_lab


def ciede2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, np.float64), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, np.float64), -1, 0)
    c1, c2 = np.hypot(a1, b1), np.hypot(a2, b2)
    cbar7 = ((c1 + c2) / 2) ** 7
    g = 0.5 * (1 - np.sqrt(cbar7 / (cbar7 + 25.0**7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, c2p - c1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(c1p * c2p == 0, 0, dh)
    dHp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))
    Lbar, Cbar = (L1 + L2) / 2, (c1p + c2p) / 2
    hsum = h1p + h2p
    hbar = np.where(
        c1p * c2p == 0, hsum,
        np.where(np.abs(h1p - h2p) <= 180, hsum / 2, np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    t = (1 - 0.17 * np.cos(np.radians(hbar - 30)) + 0.24 * np.cos(np.radians(2 * hbar))
         + 0.32 * np.cos(np.radians(3 * hbar + 6)) - 0.20 * np.cos(np.radians(4 * hbar - 63)))
    d_theta = 30 * np.exp(-(((hbar - 275) / 25) ** 2))
    rc = 2 * np.sqrt(Cbar**7 / (Cbar**7 + 25.0**7))
    sl = 1 + 0.015 * (Lbar - 50) ** 2 / np.sqrt(20 + (Lbar - 50) ** 2)
    sc = 1 + 0.045 * Cbar
    sh = 1 + 0.015 * Cbar * t
    rt = -np.sin(np.radians(2 * d_theta)) * rc
    return np.sqrt((dLp / sl) ** 2 + (dCp / sc) ** 2 + (dHp / sh) ** 2 + rt * (dCp / sc) * (dHp / sh))


def delta_e_srgb(x: np.ndarray, ref: np.ndarray) -> float:
    """Mean CIEDE2000 between two display-referred sRGB images."""
    return float(ciede2000(srgb_to_lab(x), srgb_to_lab(ref)).mean())

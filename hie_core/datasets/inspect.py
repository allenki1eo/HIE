"""Burst inspection (brief task 5): dimensions, bit depth, CFA, levels, exposure, noise, colour."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..raw import RawFrame


def describe_frame(frame: RawFrame) -> dict[str, Any]:
    m = frame.meta
    planes = frame.planes()
    return {
        "file": Path(frame.source).name if frame.source else None,
        "size": f"{frame.shape[1]}x{frame.shape[0]}",
        "cfa": frame.pattern,
        "bits": m.bits_per_sample,
        "black": m.raw_black_level,
        "white": m.raw_white_level,
        "iso": m.iso,
        "exposure_s": m.exposure_time,
        "orientation": m.orientation,
        "clipped_%": round(100.0 * float((planes >= 0.999).any(axis=-1).mean()), 3),
        "mean_level": round(float(planes.mean()), 5),
        "noise_S_O": None if m.noise_profile is None else [float(f"{v:.3g}") for v in m.noise_profile[1]],
        "neutral": None if m.as_shot_neutral is None else [round(float(v), 4) for v in m.as_shot_neutral],
        "lens_shading": None if frame.lens_shading is None else list(frame.lens_shading.shape),
    }


def describe_burst(frames: list[RawFrame]) -> dict[str, Any]:
    rows = [describe_frame(f) for f in frames]
    first = frames[0].meta
    sig = [(f.meta.exposure_time or 0) * (f.meta.iso or 0) for f in frames]
    return {
        "frames": len(frames),
        "camera": f"{first.make} {first.model}",
        "size": rows[0]["size"],
        "cfa": rows[0]["cfa"],
        "exposure_consistent": bool(np.allclose(sig, sig[0], rtol=0.05)) if sig[0] else None,
        "per_frame": rows,
    }

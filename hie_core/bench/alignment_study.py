"""Failure analysis F1/F2: how much of the burst's detail is lost to alignment error and to warping?

For each synthetic *test* scene, every aligner is compared with **oracle alignment** (the exact
flow implied by the known synthetic camera motion). All variants use the same mean fusion, so
differences come only from alignment and from warp interpolation.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from ..alignment import TileAligner, make_aligner, warp
from ..datasets.synthetic import SyntheticBurst, generate_burst, scenarios
from ..fusion import mean_fusion
from ..io import jsonable, new_run_dir, write_record
from ..pipeline import prepare, preset
from ..raw import planes_to_gray
from .run import RESULTS
from .synthetic import evaluate


def oracle_flow(burst: SyntheticBurst, frame: int, shape: tuple[int, int]) -> np.ndarray:
    """Exact plane-domain flow for a synthetic frame, from its known affine camera motion."""
    ss = 2  # generator supersampling
    m = np.asarray(burst.info["transforms"][frame])
    qy, qx = np.mgrid[0 : shape[0], 0 : shape[1]].astype(np.float64)
    full = np.stack([2 * qx + 0.5, 2 * qy + 0.5], -1)  # centre of the 2x2 Bayer block
    hi = (full + 0.5) * ss - 0.5
    hi2 = hi @ m[:, :2].T + m[:, 2]
    q2 = ((hi2 + 0.5) / ss - 1.0) / 2.0
    return (q2 - np.stack([qx, qy], -1)).astype(np.float32)


VARIANTS = [
    ("tiles (noise-aware)", "hdrplus_tiles_noise", "cubic"),
    ("tiles (no noise model)", "hdrplus_tiles", "cubic"),
    ("tiles, nearest warp", "hdrplus_tiles_noise", "nearest"),
    ("DIS optical flow", "dis_flow", "cubic"),
    ("phase correlation", "phase_correlation", "cubic"),
    ("oracle, cubic warp", "oracle", "cubic"),
    ("oracle, bilinear warp", "oracle", "linear"),
    ("oracle, nearest warp", "oracle", "nearest"),
    ("no alignment", "none", "cubic"),
]


def run(scene_names: tuple[str, ...] = ("daylight_static", "indoor_handheld", "night_handheld", "large_shake")):
    run_dir = new_run_dir(RESULTS, "EXP-alignment-study", "test")
    rows: list[dict[str, Any]] = []
    for scene in scenarios("test"):
        if scene.name not in scene_names:
            continue
        burst = generate_burst(scene)
        b = prepare(burst.frames, preset("mean"), ref_index=0)
        grays = [planes_to_gray(p) for p in b.planes]
        shape = b.planes.shape[1:3]
        truth = [oracle_flow(burst, z, shape) for z in range(len(grays))]
        for label, method, interp in VARIANTS:
            aligner = None
            if method == "hdrplus_tiles_noise":
                aligner = TileAligner(noise=b.noise)
            elif method != "oracle":
                aligner = make_aligner(method)
            warped, valid, errs = b.planes.copy(), np.ones(b.planes.shape[:3], bool), []
            for z in range(1, len(grays)):
                flow = truth[z] if aligner is None else aligner(grays[0], grays[z]).flow
                errs.append(float(np.median(np.linalg.norm(flow - truth[z], axis=-1)[16:-16, 16:-16])))
                warped[z], valid[z] = warp(b.planes[z], flow, interp)
            m = evaluate(mean_fusion(warped, 0, valid).planes, burst)
            row = {"scenario": scene.name, "variant": label, "median_flow_error_px": float(np.median(errs)),
                   "psnr_raw": m["psnr_raw"], "detail_retention": m["detail_retention"]}
            rows.append(row)
            print(f"  {scene.name:16s} {label:24s} flow err {row['median_flow_error_px']:5.2f}px  "
                  f"psnr {row['psnr_raw']:6.2f}  detail {row['detail_retention']:.3f}", flush=True)
    (run_dir / "rows.json").write_text(json.dumps(jsonable(rows), indent=2))
    write_record(run_dir, {"experiment_id": "EXP-alignment-study", "split": "test", "variants": VARIANTS,
                           "fusion": "mean", "scenes": list(scene_names)})
    print(f"→ {run_dir}")
    return run_dir


if __name__ == "__main__":
    run()

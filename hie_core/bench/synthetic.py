"""EXP-00x on synthetic bursts with ground truth.

Raw-domain metrics compare merged Bayer planes with the noise-free reference.
Display-domain metrics render both through an identical *fixed* pipeline
(MHC demosaic, identity colour, fixed gain, sRGB curve, no finishing) so that
content-adaptive tone mapping cannot confound the comparison of merge methods.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from ..color import srgb_encode
from ..datasets.synthetic import SyntheticBurst, generate_burst, scenarios
from ..demosaic import demosaic
from ..metrics import delta_e_srgb, detail_retention, ms_ssim, psnr, ssim
from ..pipeline import PipelineConfig, align_burst, denoise, fuse, prepare, preset
from ..raw import from_planes

BORDER = 16


def run_raw_stages(burst: SyntheticBurst, cfg: PipelineConfig) -> tuple[np.ndarray, dict[str, Any]]:
    t0 = time.perf_counter()
    b = prepare(burst.frames, cfg, ref_index=0)
    if len(b.frames) > 1:
        warped, valid, _ = align_burst(b, cfg)
    else:
        warped, valid = b.planes, np.ones(b.planes.shape[:3], bool)
    t1 = time.perf_counter()
    fused = fuse(warped, valid, b, cfg)
    out = denoise(fused, b.noise, cfg.spatial_denoise)
    t2 = time.perf_counter()
    return out, {"align_s": t1 - t0, "merge_s": t2 - t1, "mean_n_eff": float(fused.n_eff.mean()) if fused.n_eff is not None else None}


def fixed_render(planes: np.ndarray, gain: float) -> np.ndarray:
    rgb = demosaic(from_planes(np.maximum(planes, 0), "BGGR"), "BGGR", "mhc")
    return srgb_encode(rgb * gain)


def evaluate(out: np.ndarray, burst: SyntheticBurst) -> dict[str, float]:
    gt = burst.gt_planes
    valid = np.zeros(gt.shape[:2], bool)
    valid[BORDER:-BORDER, BORDER:-BORDER] = True
    motion = valid & burst.motion_mask
    static = valid & ~burst.motion_mask
    gain = 0.9 / float(np.percentile(gt, 99.5))
    disp_gt, disp = fixed_render(gt, gain), fixed_render(out, gain)
    b2 = 2 * BORDER
    crop = (slice(b2, -b2), slice(b2, -b2))
    m = {
        "psnr_raw": psnr(out, gt, mask=valid),
        "psnr_raw_static": psnr(out, gt, mask=static),
        "psnr_raw_motion": psnr(out, gt, mask=motion) if motion.any() else float("nan"),
        "psnr_display": psnr(disp[crop], disp_gt[crop]),
        "ssim_display": ssim(disp[crop], disp_gt[crop]),
        "ms_ssim_display": ms_ssim(disp[crop], disp_gt[crop]),
        "delta_e2000": delta_e_srgb(disp[crop], disp_gt[crop]),
        "detail_retention": detail_retention(out, gt, static),
    }
    return m


def run(presets: list[str], split: str = "test", overrides: dict[str, dict] | None = None,
        scenario_names: list[str] | None = None, progress=None) -> list[dict[str, Any]]:
    rows = []
    for scene in scenarios(split):
        if scenario_names and scene.name not in scenario_names:
            continue
        burst = generate_burst(scene)
        for name in presets:
            cfg = preset(name, **(overrides or {}).get(name, {}))
            out, timing = run_raw_stages(burst, cfg)
            row = {"scenario": scene.name, "preset": name, **evaluate(out, burst), **timing}
            rows.append(row)
            if progress:
                progress(row)
    return rows

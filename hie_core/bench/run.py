"""Benchmark suites with reproducible, never-overwritten outputs.

* ``run_synthetic_suite`` — full-reference metrics on synthetic bursts (EXP-001…005).
* ``run_hdrplus_suite``  — no-reference metrics on real HDR+ bursts, agreement with the
  HDR+ merge, runtimes, and assets for the visual comparison report.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ..color import luminance
from ..datasets import HDRPlusDataset
from ..io import git_state, jsonable, new_run_dir, save_jpeg, write_record
from ..io.experiment import REPO_ROOT
from ..metrics import flat_mask, psnr, reference_deviation_rate, residual_noise
from ..pipeline import PipelineConfig, prepare, preset, process_burst, render
from . import synthetic

RESULTS = REPO_ROOT / "benchmarks" / "results"
SYNTHETIC_PRESETS = [
    "single", "single_denoised", "mean_noalign", "mean", "median", "weighted", "motion_aware",
    "flow_mean", "hdrplus_wiener", "confidence", "hie_v0.1",
]
HDRPLUS_PRESETS = SYNTHETIC_PRESETS
CROP = 320


def _summarise(rows: list[dict], keys: list[str], by: str = "preset") -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for name in dict.fromkeys(r[by] for r in rows):
        sel = [r for r in rows if r[by] == name]
        out[name] = {k: float(np.nanmean([r[k] for r in sel if r.get(k) is not None])) for k in keys}
    return out


def run_synthetic_suite(presets: list[str] | None = None, split: str = "test") -> Path:
    presets = presets or SYNTHETIC_PRESETS
    git = git_state()
    run = new_run_dir(RESULTS, "EXP-synthetic", split)
    rows = synthetic.run(presets, split, progress=lambda r: print(
        f"  {r['scenario']:16s} {r['preset']:16s} psnr {r['psnr_raw']:6.2f}  motion {r['psnr_raw_motion']:6.2f}"
        f"  detail {r['detail_retention']:.3f}  ssim {r['ssim_display']:.4f}", flush=True))
    keys = ["psnr_raw", "psnr_raw_static", "psnr_raw_motion", "psnr_display", "ssim_display", "ms_ssim_display",
            "delta_e2000", "detail_retention", "align_s", "merge_s"]
    (run / "rows.json").write_text(json.dumps(jsonable(rows), indent=2))
    summary = _summarise(rows, keys)
    (run / "summary.json").write_text(json.dumps(summary, indent=2))
    write_record(run, {"experiment_id": "EXP-synthetic", "split": split, "presets": presets,
                       "configs": {p: preset(p) for p in presets}, "dataset": "synthetic"}, git=git)
    print(f"→ {run}")
    return run


# ---------------------------------------------------------------------------- real bursts
def _fit_scale(x: np.ndarray, ref: np.ndarray, mask: np.ndarray) -> float:
    a, b = x[mask].astype(np.float64).ravel(), ref[mask].astype(np.float64).ravel()
    return float((a @ b) / max(a @ a, 1e-12))


def _downscale(img: np.ndarray, max_side: int | None) -> np.ndarray:
    if not max_side or max(img.shape[:2]) <= max_side:
        return img
    s = max_side / max(img.shape[:2])
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def choose_crops(clean: np.ndarray, disagreement: np.ndarray, size: int = CROP) -> dict[str, tuple[int, int]]:
    """Pick consistent crop origins (top, left) on the upright image by content criteria.

    ``clean`` should be the least noisy render: on a noisy single frame, noise itself has
    high gradient energy and the "detail" crop lands on empty sky (seen at ISO 2056).
    Texture is also measured after a small blur for the same reason.
    """
    y = cv2.GaussianBlur(luminance(clean.astype(np.float32)), (0, 0), 1.5)
    h, w = y.shape
    step = size // 2
    grad = np.hypot(cv2.Sobel(y, cv2.CV_32F, 1, 0), cv2.Sobel(y, cv2.CV_32F, 0, 1))
    boxes = [(t, l) for t in range(size, h - 2 * size, step) for l in range(size, w - 2 * size, step)]

    def stat(img, t, l):
        return float(img[t : t + size, l : l + size].mean())

    detail = max(boxes, key=lambda b: stat(grad, *b))
    mean_y = {b: stat(y, *b) for b in boxes}
    textured = [b for b in boxes if stat(grad, *b) > np.median([stat(grad, *bb) for bb in boxes])]
    shadows = min(textured or boxes, key=lambda b: mean_y[b] + (1.0 if mean_y[b] < 0.02 else 0.0))
    highlights = max(textured or boxes, key=lambda b: mean_y[b] - (1.0 if mean_y[b] > 0.97 else 0.0))
    disagree = max(boxes, key=lambda b: stat(disagreement, *b))
    crops = {"detail": detail, "shadows": shadows, "highlights": highlights, "disagreement": disagree}
    return crops


def final_alignment(final: np.ndarray | None, ours: np.ndarray) -> tuple[float | None, float | None]:
    """(shift in px, gradient correlation after the shift) between Google's final.jpg and our render.

    Translation alone is not enough: a digitally zoomed final.jpg can register near zero shift
    by chance, so the gradient-magnitude correlation after alignment must also be high.
    """
    if final is None or final.shape[:2] != ours.shape[:2]:
        return None, None
    scale = 512.0 / max(ours.shape[:2])

    def prep(img):
        y = cv2.resize(luminance(img.astype(np.float32)), None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        return np.hypot(cv2.Sobel(y, cv2.CV_32F, 1, 0), cv2.Sobel(y, cv2.CV_32F, 0, 1)).astype(np.float64)

    a, b = prep(ours), prep(final)
    (dx, dy), _ = cv2.phaseCorrelate(a, b, cv2.createHanningWindow(a.shape[::-1], cv2.CV_64F))
    shifted = cv2.warpAffine(b, np.float64([[1, 0, -dx], [0, 1, -dy]]), a.shape[::-1])
    m = 8
    corr = float(np.corrcoef(a[m:-m, m:-m].ravel(), shifted[m:-m, m:-m].ravel())[0, 1])
    return float(np.hypot(dx, dy) / scale), corr


FINAL_MAX_SHIFT_PX = 2.0
FINAL_MIN_CORR = 0.8


def run_hdrplus_suite(
    presets: list[str] | None = None, bursts: list[str] | None = None, archive: str = "20171106_subset",
    report: bool = True, max_side: int | None = 1600,
) -> Path:
    presets = presets or HDRPLUS_PRESETS
    git = git_state()
    ds = HDRPlusDataset(archive=archive)
    ids = bursts or ds.list_samples()
    if not ids:
        raise SystemExit("No local HDR+ bursts. Run `hie data download <burst ids>` first.")
    run = new_run_dir(RESULTS, "EXP-hdrplus", archive)
    rows: list[dict[str, Any]] = []
    for sid in ids:
        sample = ds.load_sample(sid)
        frames = sample.load_raw_frames()
        ref_idx = sample.reference_index
        burst_dir = run / sid
        burst_dir.mkdir()
        base = prepare(frames, preset("mean"), ref_index=ref_idx)
        ref_planes = base.planes[base.ref_index]
        mask = flat_mask(ref_planes)
        sigma_ref = residual_noise(ref_planes, mask)
        hdrplus = sample.load_intermediate()
        hp_planes = None
        if hdrplus is not None and hdrplus.shape == frames[0].shape:
            hp_planes = hdrplus.planes()
            hp_planes = hp_planes * _fit_scale(hp_planes, ref_planes, mask)
        displays: dict[str, np.ndarray] = {}
        print(f"== {sid}: {len(frames)} frames, ISO {frames[0].meta.iso}, reference {ref_idx}", flush=True)
        for name in presets:
            cfg = preset(name)
            t0 = time.perf_counter()
            result = process_burst(frames, cfg, ref_index=ref_idx)
            wall = time.perf_counter() - t0
            merged = result.merged
            row = {
                "burst": sid, "preset": name, "iso": frames[0].meta.iso, "frames_used": result.info["frames_used"],
                "noise_sigma": residual_noise(merged, mask),
                "noise_reduction_db": 20 * np.log10(sigma_ref / max(residual_noise(merged, mask), 1e-9)),
                "ref_deviation_rate": reference_deviation_rate(merged, ref_planes, base.noise),
                "psnr_vs_hdrplus_merge": psnr(merged, hp_planes, data_range=float(np.percentile(hp_planes, 99.9)),
                                              mask=np.pad(np.ones((merged.shape[0] - 64, merged.shape[1] - 64), bool), 32))
                if hp_planes is not None else None,
                "runtime_s": wall, **{f"t_{k}": v for k, v in result.timings.items()},
                "notes": result.info["notes"],
            }
            rows.append(row)
            displays[name] = result.display
            save_jpeg(burst_dir / f"{name}.jpg", _downscale(result.display, max_side), quality=88)
            print(f"  {name:16s} noise −{row['noise_reduction_db']:5.2f} dB  deviation {row['ref_deviation_rate']*100:5.2f}%"
                  f"  vs HDR+ merge {row['psnr_vs_hdrplus_merge'] or float('nan'):6.2f} dB  {wall:5.1f}s", flush=True)

        extra: dict[str, np.ndarray] = {}
        render_cfg: PipelineConfig = preset("hie_v0.1")
        if hp_planes is not None:
            extra["hdrplus_merge"], _ = render(hdrplus.planes(), base.reference, render_cfg)
        final = sample.load_final()
        final_shift, final_corr = final_alignment(final, displays[presets[0]])
        if final is not None:
            extra["hdrplus_final"] = final
        for name, img in extra.items():
            save_jpeg(burst_dir / f"{name}.jpg", _downscale(img, max_side), quality=88)

        # consistent crops on the upright full-resolution renders
        a, b = displays.get("mean", displays[presets[0]]), displays.get("confidence", displays[presets[-1]])
        disagreement = np.abs(luminance(a) - luminance(b))
        clean = next((displays[p] for p in ("hie_v0.1", "confidence", "mean") if p in displays), displays[presets[0]])
        crops = choose_crops(clean, disagreement)
        crop_dir = burst_dir / "crops"
        crop_dir.mkdir()
        sources = dict(displays)
        if "hdrplus_merge" in extra:
            sources["hdrplus_merge"] = extra["hdrplus_merge"]
        if final_shift is not None and final_shift < FINAL_MAX_SHIFT_PX and final_corr > FINAL_MIN_CORR:
            sources["hdrplus_final"] = final
        for cname, (t, l) in crops.items():
            for sname, img in sources.items():
                save_jpeg(crop_dir / f"{cname}__{sname}.jpg", img[t : t + CROP, l : l + CROP], quality=92)
        (burst_dir / "meta.json").write_text(json.dumps(jsonable({
            "burst": sid, "iso": frames[0].meta.iso, "exposure_time": frames[0].meta.exposure_time,
            "camera": f"{frames[0].meta.make} {frames[0].meta.model}", "frames": len(frames),
            "reference_frame": ref_idx, "crops": crops, "crop_size": CROP, "final_jpg_shift_px": final_shift, "final_jpg_gradient_corr": final_corr,
            "final_crops_included": "hdrplus_final" in sources, "noise_model": base.noise.to_dict(),
            "notes": base.notes,
        }), indent=2))

    keys = ["noise_reduction_db", "ref_deviation_rate", "psnr_vs_hdrplus_merge", "runtime_s"]
    (run / "rows.json").write_text(json.dumps(jsonable(rows), indent=2))
    (run / "summary.json").write_text(json.dumps(_summarise(rows, keys), indent=2))
    write_record(run, {"experiment_id": "EXP-hdrplus", "dataset": f"google-hdr-plus/{archive}", "bursts": ids,
                       "presets": presets, "configs": {p: preset(p) for p in presets}}, git=git)
    if report:
        from ..report.html import build_report
        build_report(run)
    print(f"→ {run}")
    return run

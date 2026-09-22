"""Stage-by-stage burst processing.

    RawFrames → prepare (normalise, reference, noise model)
              → align (gray, per alternate frame) → warp planes
              → fuse (N, H, W, 4 → H, W, 4 + N_eff)
              → spatial denoise (σ² / N_eff)
              → render (lens shading → WB → neutral highlights → demosaic → CCM → tone → finish → orientation)

Each stage is a public function so benchmarks can reuse or ablate stages.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..alignment import make_aligner, warp
from ..color import ColorTransform, apply_matrix, dng_color_transform, identity_transform, white_balance_gains
from ..demosaic import demosaic
from ..finish import finish
from ..fusion import FUSIONS, FusionResult, frame_sharpness, spatial_wiener_denoise
from ..io.images import apply_orientation
from ..noise import NoiseModel
from ..raw import RawFrame, from_planes, planes_to_gray, upsample_shading
from ..tone_mapping import tone_map
from .config import PipelineConfig


@dataclass
class BurstInput:
    planes: np.ndarray  # (N, H, W, 4)
    frames: list[RawFrame]
    ref_index: int
    noise: NoiseModel
    notes: list[str] = field(default_factory=list)

    @property
    def reference(self) -> RawFrame:
        return self.frames[self.ref_index]


@dataclass
class PipelineResult:
    display: np.ndarray  # (H, W, 3) sRGB [0, 1], upright
    merged: np.ndarray  # (H/2, W/2, 4) merged linear planes (before shading/WB)
    n_eff: np.ndarray | None
    timings: dict[str, float]
    info: dict[str, Any]


class _Timer:
    def __init__(self) -> None:
        self.t: dict[str, float] = {}

    def __call__(self, name: str):
        timer = self

        class _Ctx:
            def __enter__(self):
                self.start = time.perf_counter()

            def __exit__(self, *exc):
                timer.t[name] = timer.t.get(name, 0.0) + time.perf_counter() - self.start

        return _Ctx()


# ---------------------------------------------------------------------------- prepare
def exposure_signature(frame: RawFrame) -> float | None:
    m = frame.meta
    if m.exposure_time is None or m.iso is None:
        return None
    return m.exposure_time * m.iso


def select_reference(planes: np.ndarray, strategy: str, given: int | None = None) -> int:
    if strategy == "given":
        if given is None:
            raise ValueError("reference='given' requires ref_index")
        return given
    if strategy == "first":
        return 0
    if strategy == "sharpest_of_first_3":
        k = min(3, planes.shape[0])
        return int(np.argmax(frame_sharpness(planes[:k])))
    raise ValueError(f"Unknown reference strategy {strategy!r}")


def prepare(frames: list[RawFrame], cfg: PipelineConfig, ref_index: int | None = None) -> BurstInput:
    if not frames:
        raise ValueError("Empty burst")
    notes: list[str] = []
    shape, pattern = frames[0].shape, frames[0].pattern
    for i, f in enumerate(frames):
        if f.shape != shape or f.pattern != pattern:
            raise ValueError(f"Frame {i} has shape/pattern {f.shape}/{f.pattern}, expected {shape}/{pattern}")

    strategy = "given" if ref_index is not None else cfg.reference
    planes = np.stack([f.planes() for f in frames])
    ref = select_reference(planes, strategy, ref_index)

    keep = list(range(len(frames)))
    sig_ref = exposure_signature(frames[ref])
    if sig_ref is not None:
        mismatched = [
            i for i, f in enumerate(frames)
            if (s := exposure_signature(f)) is not None and abs(s / sig_ref - 1.0) > 0.05
        ]
        if mismatched:
            notes.append(f"frames with exposure differing from reference: {mismatched}")
            if cfg.exclude_mismatched_exposure:
                keep = [i for i in keep if i not in mismatched]
                notes.append(f"excluded frames {mismatched} (exclude_mismatched_exposure=True)")
    if cfg.max_frames is not None and len(keep) > cfg.max_frames:
        others = [i for i in keep if i != ref][: cfg.max_frames - 1]
        dropped = sorted(set(keep) - set(others) - {ref})
        keep = sorted([ref] + others)
        notes.append(f"max_frames={cfg.max_frames}: dropped frames {dropped}")
    if cfg.fusion is None:
        keep = [ref]
    frames = [frames[i] for i in keep]
    planes = planes[keep]
    ref = keep.index(ref)

    noise = NoiseModel.from_frame(frames[ref])
    if noise is None:
        noise = NoiseModel.estimate_from_burst(planes) if len(frames) >= 3 else NoiseModel.estimate_single(planes[ref])
        notes.append(f"noise model estimated ({noise.source}); no DNG NoiseProfile")
    return BurstInput(planes.astype(np.float32), frames, ref, noise, notes)


# ---------------------------------------------------------------------------- align + fuse
def align_burst(burst: BurstInput, cfg: PipelineConfig) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    n = burst.planes.shape[0]
    grays = [planes_to_gray(p) for p in burst.planes]
    aligner = make_aligner(cfg.aligner, noise=burst.noise) if cfg.aligner == "hdrplus_tiles" else make_aligner(cfg.aligner)
    warped = burst.planes.copy()
    valid = np.ones(burst.planes.shape[:3], dtype=bool)
    infos: list[dict] = []
    for z in range(n):
        if z == burst.ref_index:
            infos.append({"frame": z, "reference": True})
            continue
        al = aligner(grays[burst.ref_index], grays[z])
        warped[z], valid[z] = warp(burst.planes[z], al.flow, cfg.warp_interp)
        summary = {k: v for k, v in al.info.items() if not isinstance(v, np.ndarray)}
        infos.append({"frame": z, "method": al.method, "mean_flow_px": al.mean_displacement, **summary})
    return warped, valid, infos


def fuse(warped: np.ndarray, valid: np.ndarray, burst: BurstInput, cfg: PipelineConfig) -> FusionResult:
    if cfg.fusion is None:
        ref = warped[burst.ref_index]
        return FusionResult(ref, np.ones(ref.shape[:2], np.float32))
    fn = FUSIONS[cfg.fusion]
    return fn(warped, burst.ref_index, noise=burst.noise, valid=valid, **cfg.fusion_params)


def denoise(result: FusionResult, noise: NoiseModel, strength: float) -> np.ndarray:
    if strength <= 0:
        return result.planes
    n_eff = result.n_eff if result.n_eff is not None else np.ones(result.planes.shape[:2], np.float32)
    var = noise.variance(result.planes) / np.maximum(n_eff, 1.0)[..., None]
    return spatial_wiener_denoise(result.planes, var, strength=strength)


# ---------------------------------------------------------------------------- render
def color_transform(frame: RawFrame, mode: str) -> ColorTransform:
    neutral = frame.meta.as_shot_neutral
    if mode == "identity" or neutral is None:
        return identity_transform(neutral)
    if mode == "dng" and frame.meta.color_matrix1 is None:
        ct = identity_transform(neutral)
        ct.source = "identity_no_color_matrix"  # recorded in render info, not hidden
        return ct
    if mode == "sidecar":
        m = frame.meta.extras.get("rgb2rgb")
        if m is None:
            raise ValueError("color='sidecar' requires an HDR+ rgb2rgb.txt matrix")
        return ColorTransform(white_balance_gains(neutral), np.asarray(m).reshape(3, 3), None, "hdrplus_rgb2rgb")
    return dng_color_transform(frame.meta)


def render(planes: np.ndarray, ref: RawFrame, cfg: PipelineConfig) -> tuple[np.ndarray, dict[str, Any]]:
    """Merged linear planes → upright display-referred sRGB."""
    h2, w2 = planes.shape[:2]
    gain = np.ones((h2, w2, 4), np.float32)
    if cfg.lens_shading and ref.lens_shading is not None:
        gain = upsample_shading(ref.lens_shading, (h2, w2))
    ct = color_transform(ref, cfg.color)
    wb = np.array([ct.wb_gains[0], ct.wb_gains[1], ct.wb_gains[1], ct.wb_gains[2]], np.float32)
    total_gain = gain * wb
    p = planes * total_gain
    # Sensor white after shading+WB differs per channel; clipping all channels to the lowest
    # keeps saturated highlights neutral instead of magenta.
    p = np.minimum(p, total_gain.min(axis=-1, keepdims=True))
    rgb = demosaic(from_planes(p, ref.pattern), ref.pattern, cfg.demosaic)
    linear = apply_matrix(rgb, ct.cam_to_srgb)
    tone = tone_map(linear, cfg.tone)
    display = finish(tone.display, cfg.finish) if cfg.finish is not None else tone.display
    display = apply_orientation(display, ref.meta.orientation)
    info = {
        "color_source": ct.source, "cct": ct.cct, "wb_gains": ct.wb_gains.tolist(),
        "cam_to_srgb": ct.cam_to_srgb.tolist(), "short_gain": tone.short_gain, "long_gain": tone.long_gain,
    }
    return display, info


# ---------------------------------------------------------------------------- orchestration
def process_burst(frames: list[RawFrame], cfg: PipelineConfig, ref_index: int | None = None) -> PipelineResult:
    timer = _Timer()
    with timer("prepare"):
        burst = prepare(frames, cfg, ref_index)
    with timer("align"):
        if len(burst.frames) > 1:
            warped, valid, align_info = align_burst(burst, cfg)
        else:
            warped, valid, align_info = burst.planes, np.ones(burst.planes.shape[:3], bool), []
    with timer("fuse"):
        fused = fuse(warped, valid, burst, cfg)
    with timer("denoise"):
        merged = denoise(fused, burst.noise, cfg.spatial_denoise)
    with timer("render"):
        display, render_info = render(merged, burst.reference, cfg)
    timer.t["total"] = sum(timer.t.values())
    info = {
        "config": cfg.name,
        "frames_used": len(burst.frames),
        "reference_index_in_used": burst.ref_index,
        "reference_source": burst.reference.source,
        "noise_model": burst.noise.to_dict(),
        "notes": burst.notes,
        "alignment": align_info,
        "fusion": fused.info,
        "mean_n_eff": float(fused.n_eff.mean()) if fused.n_eff is not None else None,
        "render": render_info,
    }
    return PipelineResult(display, merged, fused.n_eff, timer.t, info)

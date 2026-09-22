"""Pipeline configuration and the named algorithm presets used in experiments."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from ..finish import FinishConfig
from ..tone_mapping import ToneConfig


@dataclass(frozen=True)
class PipelineConfig:
    name: str = "hie_v0.1"
    reference: str = "sharpest_of_first_3"  # "first" | "sharpest_of_first_3" | "given"
    max_frames: int | None = None
    exclude_mismatched_exposure: bool = True  # drop (and record) frames whose exposure differs from the reference
    aligner: str = "hdrplus_tiles"
    warp_interp: str = "cubic"  # "nearest" | "linear" | "cubic"
    fusion: str | None = "confidence"  # None → single frame
    fusion_params: dict[str, Any] = field(default_factory=dict)
    spatial_denoise: float = 0.0  # Wiener strength on the merged raw (0 = off)
    lens_shading: bool = True
    demosaic: str = "mhc"
    color: str = "dng"  # "dng" | "sidecar" (HDR+ rgb2rgb.txt) | "identity"
    tone: ToneConfig = ToneConfig()
    finish: FinishConfig | None = FinishConfig()

    def with_(self, **changes: Any) -> "PipelineConfig":
        return replace(self, **changes)


_BASE = PipelineConfig()

PRESETS: dict[str, PipelineConfig] = {
    # EXP-001: single RAW frame through the same rendering as everything else
    "single": _BASE.with_(name="single", aligner="none", fusion=None),
    # single frame + the same spatial denoiser HIE uses: separates "burst" gains from "denoiser" gains
    "single_denoised": _BASE.with_(name="single_denoised", aligner="none", fusion=None, spatial_denoise=1.0),
    # EXP-002 and its no-alignment ablation
    "mean_noalign": _BASE.with_(name="mean_noalign", aligner="none", fusion="mean"),
    "mean": _BASE.with_(name="mean", fusion="mean"),
    # EXP-003
    "median": _BASE.with_(name="median", fusion="median"),
    # Baseline 3 / 4
    "weighted": _BASE.with_(name="weighted", fusion="weighted"),
    "motion_aware": _BASE.with_(name="motion_aware", fusion="motion_aware"),
    # EXP-004: dense optical flow alignment + mean / + confidence
    "flow_mean": _BASE.with_(name="flow_mean", aligner="dis_flow", fusion="mean"),
    "flow_confidence": _BASE.with_(name="flow_confidence", aligner="dis_flow", fusion="confidence"),
    # Reproduction of the HDR+ frequency-domain temporal merge (integer tile offsets → nearest warp)
    "hdrplus_wiener": _BASE.with_(name="hdrplus_wiener", fusion="temporal_wiener", warp_interp="nearest",
                                  fusion_params={"k": 8.0}),
    # EXP-005: confidence-weighted fusion
    "confidence": _BASE.with_(name="confidence", fusion="confidence"),
    # HIE v0.1: confidence fusion + N_eff-aware spatial Wiener denoise
    "hie_v0.1": _BASE.with_(name="hie_v0.1", fusion="confidence", spatial_denoise=1.0),
}


def preset(name: str, **overrides: Any) -> PipelineConfig:
    try:
        cfg = PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown preset {name!r}; choose from {sorted(PRESETS)}") from exc
    return cfg.with_(**overrides) if overrides else cfg

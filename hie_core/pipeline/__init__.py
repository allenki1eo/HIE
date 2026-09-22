"""End-to-end processing pipeline and named presets."""

from .config import PRESETS, PipelineConfig, preset
from .core import (
    BurstInput, PipelineResult, align_burst, color_transform, denoise, fuse, prepare, process_burst, render,
    select_reference,
)

__all__ = [
    "PRESETS", "BurstInput", "PipelineConfig", "PipelineResult", "align_burst", "color_transform", "denoise",
    "fuse", "prepare", "preset", "process_burst", "render", "select_reference",
]

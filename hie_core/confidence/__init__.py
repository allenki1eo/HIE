"""Per-pixel confidence / uncertainty representation (research direction #3)."""

from .maps import (
    effective_frame_count, local_mean, normalized_residual, residual_confidence, saturation_confidence,
)

__all__ = [
    "effective_frame_count", "local_mean", "normalized_residual", "residual_confidence", "saturation_confidence",
]

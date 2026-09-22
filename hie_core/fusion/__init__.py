"""Burst fusion methods."""

from .pixel import (
    FusionResult, confidence_fusion, frame_sharpness, mean_fusion, median_fusion, motion_aware_fusion,
    weighted_fusion,
)
from .wiener import spatial_wiener_denoise, temporal_wiener_fusion

FUSIONS = {
    "mean": mean_fusion,
    "median": median_fusion,
    "weighted": weighted_fusion,
    "motion_aware": motion_aware_fusion,
    "confidence": confidence_fusion,
    "temporal_wiener": temporal_wiener_fusion,
}

__all__ = [
    "FUSIONS", "FusionResult", "confidence_fusion", "frame_sharpness", "mean_fusion", "median_fusion",
    "motion_aware_fusion", "spatial_wiener_denoise", "temporal_wiener_fusion", "weighted_fusion",
]

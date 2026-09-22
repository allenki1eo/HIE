"""RAW input: DNG decoding, Bayer plane handling and lens-shading metadata."""

from .bayer import PLANES, from_planes, planes_to_gray, planes_to_rgb_half, to_planes
from .dng import DngError, read_dng
from .frame import CaptureMetadata, RawFrame, upsample_shading

__all__ = [
    "PLANES", "CaptureMetadata", "DngError", "RawFrame", "from_planes", "planes_to_gray",
    "planes_to_rgb_half", "read_dng", "to_planes", "upsample_shading",
]

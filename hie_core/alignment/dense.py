"""Dense optical flow alignment (DIS, Kroeger et al., ECCV 2016, via OpenCV)."""

from __future__ import annotations

import cv2
import numpy as np

from .base import Alignment, to_uint8_for_matching

_PRESETS = {
    "ultrafast": cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST,
    "fast": cv2.DISOPTICAL_FLOW_PRESET_FAST,
    "medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM,
}


class DISFlowAligner:
    name = "dis_flow"

    def __init__(self, preset: str = "medium", denoise_sigma: float = 1.0):
        self.preset = preset
        self.denoise_sigma = denoise_sigma

    def __call__(self, ref_gray: np.ndarray, alt_gray: np.ndarray) -> Alignment:
        dis = cv2.DISOpticalFlow_create(_PRESETS[self.preset])
        ref8 = to_uint8_for_matching(ref_gray, denoise_sigma=self.denoise_sigma)
        alt8 = to_uint8_for_matching(alt_gray, denoise_sigma=self.denoise_sigma)
        flow = dis.calc(ref8, alt8, None)
        return Alignment(flow.astype(np.float32), self.name, {"preset": self.preset})

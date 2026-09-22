"""Global (whole-frame) alignment: FFT phase correlation and feature-based homography."""

from __future__ import annotations

import cv2
import numpy as np

from .base import Alignment, base_grid, to_uint8_for_matching


class PhaseCorrelationAligner:
    """Global sub-pixel translation by FFT phase correlation (Kuglin & Hines, 1975)."""

    name = "phase_correlation"

    def __call__(self, ref_gray: np.ndarray, alt_gray: np.ndarray) -> Alignment:
        ref = np.sqrt(np.maximum(ref_gray, 0)).astype(np.float64)
        alt = np.sqrt(np.maximum(alt_gray, 0)).astype(np.float64)
        window = cv2.createHanningWindow(ref.shape[::-1], cv2.CV_64F)
        (dx, dy), response = cv2.phaseCorrelate(ref, alt, window)
        flow = np.empty((*ref_gray.shape, 2), dtype=np.float32)
        flow[..., 0], flow[..., 1] = dx, dy
        return Alignment(flow, self.name, {"shift": (float(dx), float(dy)), "response": float(response)})


class FeatureHomographyAligner:
    """ORB keypoints + RANSAC homography (global projective model)."""

    name = "feature_homography"

    def __init__(self, n_features: int = 6000, ransac_threshold: float = 1.5, min_inliers: int = 30):
        self.n_features = n_features
        self.ransac_threshold = ransac_threshold
        self.min_inliers = min_inliers

    def __call__(self, ref_gray: np.ndarray, alt_gray: np.ndarray) -> Alignment:
        orb = cv2.ORB_create(nfeatures=self.n_features, fastThreshold=5)
        ref8 = to_uint8_for_matching(ref_gray, denoise_sigma=1.0)
        alt8 = to_uint8_for_matching(alt_gray, denoise_sigma=1.0)
        k1, d1 = orb.detectAndCompute(ref8, None)
        k2, d2 = orb.detectAndCompute(alt8, None)
        info: dict = {"keypoints": (len(k1), len(k2))}
        if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
            return self._fallback(ref_gray.shape, info, "too few keypoints")
        matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
        if len(matches) < 8:
            return self._fallback(ref_gray.shape, info, "too few matches")
        src = np.float32([k1[m.queryIdx].pt for m in matches])
        dst = np.float32([k2[m.trainIdx].pt for m in matches])
        hom, inliers = cv2.findHomography(src, dst, cv2.RANSAC, self.ransac_threshold)
        n_in = int(inliers.sum()) if inliers is not None else 0
        info.update(matches=len(matches), inliers=n_in)
        if hom is None or n_in < self.min_inliers:
            return self._fallback(ref_gray.shape, info, "homography rejected")
        xs, ys = base_grid(ref_gray.shape)
        pts = np.stack([xs, ys, np.ones_like(xs)], axis=-1) @ hom.T.astype(np.float32)
        flow = np.stack([pts[..., 0] / pts[..., 2] - xs, pts[..., 1] / pts[..., 2] - ys], axis=-1)
        info["homography"] = hom.tolist()
        return Alignment(flow.astype(np.float32), self.name, info)

    def _fallback(self, shape: tuple[int, int], info: dict, reason: str) -> Alignment:
        info["fallback"] = reason  # recorded, not hidden: identity alignment was used
        return Alignment(np.zeros((*shape, 2), np.float32), self.name, info)

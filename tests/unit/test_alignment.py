import cv2
import numpy as np
import pytest

from hie_core.alignment import TileAligner, make_aligner, warp
from hie_core.noise import NoiseModel


def _pair(rng, shift=(3.4, -2.7), noise=0.004, shape=(320, 400)):
    base = cv2.GaussianBlur(rng.random(shape).astype(np.float32), (0, 0), 2.0)
    base = (base - base.min()) / (base.max() - base.min()) * 0.5 + 0.05
    m = np.float32([[1, 0, shift[0]], [0, 1, shift[1]]])
    alt = cv2.warpAffine(base, m, shape[::-1], flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    add = lambda im: (im + rng.normal(0, noise, im.shape)).astype(np.float32)  # noqa: E731
    return base, add(base), add(alt)


@pytest.mark.parametrize("name", ["phase_correlation", "hdrplus_tiles", "dis_flow", "feature_homography"])
def test_aligners_recover_translation(name, rng):
    clean, ref, alt = _pair(rng)
    flow = make_aligner(name)(ref, alt).flow[40:-40, 40:-40].reshape(-1, 2)
    assert np.allclose(np.median(flow, 0), (3.4, -2.7), atol=0.35)


def test_warp_undoes_shift(rng):
    clean, ref, alt = _pair(rng, noise=0.0)
    flow = np.zeros((*ref.shape, 2), np.float32)
    flow[..., 0], flow[..., 1] = 3.4, -2.7
    warped, valid = warp(alt, flow, "cubic")
    assert np.abs(warped - clean)[20:-20, 20:-20].mean() < 2e-3
    assert not valid[:, -1].all()  # samples past the right edge are flagged


def test_noise_aware_tiles_do_not_move_on_pure_noise(rng):
    ref = rng.normal(0.1, 0.05, (256, 256)).astype(np.float32)
    alt = rng.normal(0.1, 0.05, (256, 256)).astype(np.float32)
    noise = NoiseModel(0.0, 0.05**2 * 4)  # gray = mean of 4 planes → variance / 4
    flow = TileAligner(noise=noise)(ref, alt).flow
    assert np.median(np.abs(flow)) < 0.5

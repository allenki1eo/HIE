import numpy as np
import pytest

from hie_core.demosaic import demosaic
from hie_core.metrics import detail_retention, psnr, ssim
from hie_core.raw.bayer import plane_offsets


def _mosaic(rgb, pattern):
    cfa = np.empty(rgb.shape[:2], np.float32)
    ch = {"R": 0, "Gr": 1, "Gb": 1, "B": 2}
    for name, (r, c) in plane_offsets(pattern).items():
        cfa[r::2, c::2] = rgb[r::2, c::2, ch[name]]
    return cfa


@pytest.mark.parametrize("method", ["mhc", "bilinear", "opencv_ea"])
@pytest.mark.parametrize("pattern", ["RGGB", "BGGR", "GRBG", "GBRG"])
def test_flat_colour_is_reproduced(method, pattern):
    rgb = np.broadcast_to(np.array([0.7, 0.4, 0.15], np.float32), (32, 32, 3)).copy()
    out = demosaic(_mosaic(rgb, pattern), pattern, method)
    assert np.allclose(out[4:-4, 4:-4], rgb[4:-4, 4:-4], atol=2e-3)


def test_mhc_beats_bilinear_on_correlated_detail():
    """MHC exploits inter-channel correlation, as found in natural images."""
    yy, xx = np.mgrid[0:128, 0:128].astype(np.float32)
    lum = 0.5 + 0.35 * np.sin(xx / 1.9) * np.cos(yy / 2.3)
    rgb = np.stack([0.8 * lum + 0.1, lum, 0.55 * lum + 0.05], -1)
    cfa = _mosaic(rgb, "BGGR")
    crop = (slice(8, -8), slice(8, -8))
    assert psnr(demosaic(cfa, "BGGR", "mhc")[crop], rgb[crop]) > psnr(demosaic(cfa, "BGGR", "bilinear")[crop], rgb[crop])


def test_metric_identities(rng):
    x = rng.random((64, 64, 3)).astype(np.float32)
    assert psnr(x, x) == float("inf")
    assert abs(ssim(x, x) - 1.0) < 1e-6
    assert abs(detail_retention(x, x) - 1.0) < 1e-6
    assert detail_retention(np.full_like(x, x.mean()), x) < 0.05

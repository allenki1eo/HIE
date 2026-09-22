import numpy as np
import pytest

from hie_core.fusion import FUSIONS, spatial_wiener_denoise
from hie_core.fusion.tiles import process_tiles, raised_cosine
from hie_core.noise import NoiseModel

NOISE = NoiseModel(1e-3, 1e-5)


def _burst(rng, n=8, moving=False):
    clean = np.full((96, 128, 4), 0.2, np.float32)
    clean[:, 64:] = 0.4
    frames = []
    for i in range(n):
        f = clean.copy()
        if moving and i > 0:
            f[40:56, 8 + 8 * i : 24 + 8 * i] = 0.9  # object appears only in alternate frames
        frames.append(f + rng.normal(0, np.sqrt(NOISE.variance(f))).astype(np.float32))
    return clean, np.stack(frames)


def test_raised_cosine_partition_of_unity():
    w = raised_cosine(16)
    total = np.zeros((32, 32))
    for dy in (0, 8, 16):
        for dx in (0, 8, 16):
            total[dy : dy + 16, dx : dx + 16] += w
    assert np.allclose(total[8:24, 8:24], 1.0)


def test_tile_identity_reconstruction(rng):
    x = rng.random((50, 77, 4)).astype(np.float32)
    assert np.abs(process_tiles([x], 16, lambda t: t[0]) - x).max() < 1e-5


@pytest.mark.parametrize("name", sorted(FUSIONS))
def test_fusions_reduce_noise_on_static_scenes(name, rng):
    clean, frames = _burst(rng)
    out = FUSIONS[name](frames, 0, noise=NOISE, valid=None).planes
    assert (out - clean).std() < 0.75 * (frames[0] - clean).std()


@pytest.mark.parametrize("name", ["motion_aware", "confidence", "temporal_wiener"])
def test_robust_fusions_reject_moving_objects(name, rng):
    clean, frames = _burst(rng, moving=True)
    robust = FUSIONS[name](frames, 0, noise=NOISE, valid=None).planes
    naive = FUSIONS["mean"](frames, 0, noise=NOISE, valid=None).planes
    region = (slice(40, 56), slice(16, 80))
    assert np.abs(robust[region] - clean[region]).mean() < 0.5 * np.abs(naive[region] - clean[region]).mean()


def test_spatial_wiener_reduces_noise_and_keeps_mean(rng):
    clean, frames = _burst(rng, n=1)
    var = NOISE.variance(frames[0])
    out = spatial_wiener_denoise(frames[0], var, strength=1.0)
    assert (out - clean).std() < 0.7 * (frames[0] - clean).std()
    assert abs(out.mean() - frames[0].mean()) < 1e-3

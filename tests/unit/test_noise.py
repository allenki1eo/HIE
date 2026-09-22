import numpy as np

from hie_core.noise import NoiseModel


def _poisson_gaussian(clean, s, o, rng, n):
    return np.stack([rng.poisson(clean / s) * s + rng.normal(0, np.sqrt(o), clean.shape) for _ in range(n)]).astype(np.float32)


def _ramp(h=256, w=256):
    ramp = np.linspace(0.01, 0.6, w, dtype=np.float32)[None, :].repeat(h, 0)
    return np.stack([ramp] * 4, -1)


def test_variance_and_gain():
    m = NoiseModel(1e-3, 1e-5)
    x = np.full((1, 1, 4), 0.2, np.float32)
    assert np.allclose(m.variance(x), 1e-3 * 0.2 + 1e-5)
    g = np.full_like(x, 2.0)
    assert np.allclose(m.variance(2 * x, gain=g), 2 * 1e-3 * 0.4 + 4 * 1e-5)


def test_estimate_from_burst_recovers_parameters(rng):
    s, o = 8e-4, 2e-5
    frames = _poisson_gaussian(_ramp(), s, o, rng, 8)
    est = NoiseModel.estimate_from_burst(frames)
    assert np.allclose(est.shot, s, rtol=0.15)
    assert np.allclose(est.read, o, rtol=0.5, atol=5e-6)


def test_estimate_single_is_in_the_right_range(rng):
    s, o = 8e-4, 2e-5
    frame = _poisson_gaussian(_ramp(), s, o, rng, 1)[0]
    est = NoiseModel.estimate_single(frame)
    sd_true = np.sqrt(s * 0.3 + o)
    sd_est = np.sqrt(est.shot.mean() * 0.3 + est.read.mean())
    assert abs(sd_est / sd_true - 1) < 0.2

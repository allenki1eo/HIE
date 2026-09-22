import numpy as np

from hie_core.color import dng_color_transform, srgb_decode, srgb_encode, xy_to_cct
from hie_core.metrics import ciede2000
from hie_core.raw import CaptureMetadata
from hie_core.tone_mapping import ToneConfig, tone_map

# Pixel ("sailfish") matrices from an HDR+ burst DNG
CM1 = np.array([[0.7527, -0.2068, -0.091], [-0.5955, 1.431, 0.1737], [-0.2481, 0.3391, 0.5873]])
CM2 = np.array([[1.0676, -0.3149, -0.2765], [-0.553, 1.6283, -0.1152], [-0.0614, 0.1997, 0.5991]])


def _meta(neutral=(0.496, 1.0, 0.614)):
    return CaptureMetadata(as_shot_neutral=np.array(neutral), color_matrix1=CM1, color_matrix2=CM2,
                           calibration_illuminant1=21, calibration_illuminant2=17)


def test_white_stays_white():
    ct = dng_color_transform(_meta())
    assert np.allclose(ct.cam_to_srgb @ np.ones(3), 1.0)
    assert np.isclose(ct.wb_gains[1], 1.0)


def test_cct_of_standard_illuminants():
    assert abs(xy_to_cct(np.array([0.31271, 0.32902])) - 6504) < 60  # D65
    assert abs(xy_to_cct(np.array([0.44757, 0.40745])) - 2856) < 60  # illuminant A


def test_srgb_roundtrip():
    x = np.linspace(0, 1, 1001, dtype=np.float32)
    assert np.abs(srgb_decode(srgb_encode(x)) - x).max() < 1e-5


def test_ciede2000_reference_pairs():
    # Sharma, Wu & Dalal (2005), test data pairs 1, 2, 3 and 7
    pairs = [((50, 2.6772, -79.7751), (50, 0, -82.7485), 2.0425), ((50, 3.1571, -77.2803), (50, 0, -82.7485), 2.8615),
             ((50, 2.8361, -74.02), (50, 0, -82.7485), 3.4412), ((50, 0, 0), (50, -1, 2), 2.3669)]
    for a, b, expected in pairs:
        assert abs(float(ciede2000(np.array(a), np.array(b))) - expected) < 1e-3


def test_tone_map_is_monotone_and_bounded(rng):
    ramp = np.linspace(0.0005, 0.3, 256, dtype=np.float32)[None, :, None].repeat(64, 0).repeat(3, 2)
    out = tone_map(ramp, ToneConfig()).display
    assert out.min() >= 0 and out.max() <= 1
    assert np.all(np.diff(out[32, :, 1]) >= -1e-3)

import numpy as np
import pytest

from hie_core.datasets import generate_burst, scenarios
from hie_core.pipeline import PRESETS, preset, process_burst


@pytest.fixture(scope="module")
def burst():
    return generate_burst(scenarios("test")[3])  # night_motion


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_preset_renders(name, burst):
    result = process_burst(burst.frames, preset(name), ref_index=0)
    assert result.display.shape == (768, 1024, 3)
    assert 0.0 <= result.display.min() and result.display.max() <= 1.0
    assert np.isfinite(result.merged).all()
    expected = 1 if PRESETS[name].fusion is None else len(burst.frames)
    assert result.info["frames_used"] == expected


@pytest.mark.realdata
def test_hdrplus_burst_loads_all_frames(hdrplus_sample):
    frames = hdrplus_sample.load_raw_frames()
    assert len(frames) == len(hdrplus_sample.frame_paths)  # nothing dropped silently
    assert all(f.pattern == frames[0].pattern for f in frames)
    assert frames[0].lens_shading is not None and frames[0].lens_shading.shape[-1] == 4


@pytest.mark.realdata
def test_hdrplus_burst_processes(hdrplus_sample):
    frames = hdrplus_sample.load_raw_frames()[:3]
    result = process_burst(frames, preset("confidence"), ref_index=0)
    assert result.display.ndim == 3 and result.info["frames_used"] == 3

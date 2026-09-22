"""Guards the headline synthetic results (seeded). Thresholds sit a few tenths of a dB below
the values recorded in docs/benchmark.md so that an accidental regression fails loudly."""

import numpy as np
import pytest

from hie_core.bench.synthetic import evaluate, run_raw_stages
from hie_core.datasets import generate_burst, scenarios
from hie_core.pipeline import preset

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def results():
    wanted = {"night_handheld", "daylight_motion"}
    out = {}
    for sc in scenarios("test"):
        if sc.name in wanted:
            b = generate_burst(sc)
            out[sc.name] = {p: evaluate(run_raw_stages(b, preset(p))[0], b)
                            for p in ("single", "mean", "confidence", "hie_v0.1")}
    return out


def test_burst_beats_single_frame_at_night(results):
    r = results["night_handheld"]
    assert r["mean"]["psnr_raw"] > r["single"]["psnr_raw"] + 8.0
    assert r["hie_v0.1"]["psnr_raw"] > r["confidence"]["psnr_raw"] + 2.0


def test_confidence_fusion_prevents_ghosting(results):
    r = results["daylight_motion"]
    assert r["confidence"]["psnr_raw_motion"] > r["mean"]["psnr_raw_motion"] + 15.0
    assert r["confidence"]["psnr_raw"] > r["single"]["psnr_raw"] + 4.0


def test_detail_is_retained_in_good_light(results):
    assert results["daylight_motion"]["hie_v0.1"]["detail_retention"] > 0.95
    assert np.isfinite(results["night_handheld"]["hie_v0.1"]["detail_retention"])

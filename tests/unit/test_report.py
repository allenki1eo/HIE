import json

import numpy as np
from PIL import Image

from hie_core.report.html import SOURCES, build_report


def _img(path, value, size=(32, 32)):
    Image.fromarray(np.full((*size, 3), value, np.uint8)).save(path)


def test_report_builds_from_a_run_directory(tmp_path):
    run = tmp_path / "EXP-hdrplus" / "run"
    burst = run / "b1"
    (burst / "crops").mkdir(parents=True)
    presets = ["single", "mean", "hie_v0.1"]
    for p in presets:
        _img(burst / f"{p}.jpg", 100, (40, 60))
        for kind in ("detail", "shadows", "highlights", "disagreement"):
            _img(burst / "crops" / f"{kind}__{p}.jpg", 50)
    (burst / "meta.json").write_text(json.dumps({
        "burst": "b1", "iso": 100, "exposure_time": 0.01, "camera": "google test", "frames": 3,
        "reference_frame": 0, "crops": {}, "notes": [], "final_crops_included": False,
    }))
    rows = [{"burst": "b1", "preset": p, "noise_reduction_db": i, "ref_deviation_rate": 0.01,
             "psnr_vs_hdrplus_merge": None, "runtime_s": 1.0} for i, p in enumerate(presets)]
    (run / "rows.json").write_text(json.dumps(rows))
    (run / "experiment.json").write_text(json.dumps({"commit": "abc123", "dirty": False, "timestamp": "2026-01-01"}))

    page = build_report(run, findings=["A finding."]).read_text()
    assert "<title>HIE Baseline Bench</title>" in page
    assert "A finding." in page and "/*__DATA__*/" not in page
    data = json.loads(page.split("const DATA = ", 1)[1].split(";\nconst SRC", 1)[0])
    assert data["bursts"][0]["sources"] == presets  # order follows SOURCES, missing ones skipped
    sprite = Image.open(run / "report" / data["bursts"][0]["sprites"]["detail"])
    assert sprite.size == (32 * len(presets), 32)
    assert {s for s, _, _ in SOURCES} >= set(presets)

import json

from hie_core.report.markdown import real_table


def test_real_table_formats_missing_values(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({
        "mean": {"noise_reduction_db": 9.4, "ref_deviation_rate": 0.025, "psnr_vs_hdrplus_merge": None, "runtime_s": 24.9},
    }))
    table = real_table(tmp_path)
    assert "| Mean | 9.40 | 2.50 % | — | 24.9 |" in table

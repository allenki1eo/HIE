"""Markdown tables generated from run directories, so committed numbers are never hand-copied."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .html import SOURCES

LABEL = {s: label for s, label, _ in SOURCES}


def _fmt(v, d=2, pct=False):
    if v is None:
        return "—"
    return f"{v * 100:.{d}f} %" if pct else f"{v:.{d}f}"


def real_table(run: Path) -> str:
    s = json.loads((run / "summary.json").read_text())
    out = ["| Method | Noise removed (dB) ↑ | Reference deviation ↓ | Agreement with Google merge (dB) | Runtime (s) |",
           "|---|--:|--:|--:|--:|"]
    for p, v in s.items():
        out.append(f"| {LABEL.get(p, p)} | {_fmt(v['noise_reduction_db'])} | {_fmt(v['ref_deviation_rate'], 2, True)} "
                   f"| {_fmt(v['psnr_vs_hdrplus_merge'])} | {_fmt(v['runtime_s'], 1)} |")
    return "\n".join(out)


def synthetic_tables(run: Path) -> tuple[str, str]:
    s = json.loads((run / "summary.json").read_text())
    rows = json.loads((run / "rows.json").read_text())
    out = ["| Method | PSNR raw ↑ | PSNR motion region ↑ | Detail retained ↑ | SSIM ↑ | MS-SSIM ↑ | ΔE2000 ↓ |",
           "|---|--:|--:|--:|--:|--:|--:|"]
    for p, v in s.items():
        out.append(f"| {LABEL.get(p, p)} | {_fmt(v['psnr_raw'])} | {_fmt(v['psnr_raw_motion'])} | {_fmt(v['detail_retention'], 3)} "
                   f"| {_fmt(v['ssim_display'], 4)} | {_fmt(v['ms_ssim_display'], 4)} | {_fmt(v['delta_e2000'])} |")
    scenes = list(dict.fromkeys(r["scenario"] for r in rows))
    per = ["| Method | " + " | ".join(scenes) + " |", "|---|" + "--:|" * len(scenes)]
    for p in s:
        cells = []
        for sc in scenes:
            r = next(r for r in rows if r["scenario"] == sc and r["preset"] == p)
            cells.append(f"{r['psnr_raw']:.2f} / {r['detail_retention']:.2f}")
        per.append(f"| {LABEL.get(p, p)} | " + " | ".join(cells) + " |")
    return "\n".join(out), "\n".join(per) + "\n\nCells: PSNR (dB) / detail retained."


def alignment_table(run: Path, scene: str = "night_handheld") -> str:
    rows = [r for r in json.loads((run / "rows.json").read_text()) if r["scenario"] == scene]
    out = ["| Alignment (mean fusion) | Median flow error (px) | PSNR (dB) | Detail retained |", "|---|--:|--:|--:|"]
    for r in rows:
        out.append(f"| {r['variant']} | {r['median_flow_error_px']:.2f} | {r['psnr_raw']:.2f} | {r['detail_retention']:.3f} |")
    return "\n".join(out)


def export(hdrplus: Path, synthetic: Path, alignment: Path, dest: Path) -> dict[str, str]:
    """Copy run summaries into ``dest`` and return the generated tables."""
    dest.mkdir(parents=True, exist_ok=True)
    for name, run in (("hdrplus", hdrplus), ("synthetic", synthetic), ("alignment", alignment)):
        for f in ("summary.json", "rows.json", "experiment.json"):
            if (run / f).exists():
                shutil.copy(run / f, dest / f"{name}__{f}")
    synth, per_scene = synthetic_tables(synthetic)
    tables = {"REAL": real_table(hdrplus), "SYNTH": synth, "SYNTHSCENE": per_scene,
              "ALIGN": alignment_table(alignment), "ALIGN_ALL": "\n\n".join(
                  f"**{sc}**\n\n" + alignment_table(alignment, sc)
                  for sc in dict.fromkeys(r["scenario"] for r in json.loads((alignment / "rows.json").read_text())))}
    runs = ["| Run | What | Commit |", "|---|---|---|"]
    for name, run in (("EXP-hdrplus", hdrplus), ("EXP-synthetic", synthetic), ("EXP-alignment-study", alignment)):
        rec = json.loads((run / "experiment.json").read_text())
        runs.append(f"| `{run.parent.name}/{run.name}` | {name} | `{(rec.get('commit') or '')[:10]}`"
                    f"{' (dirty)' if rec.get('dirty') else ''} |")
    tables["RUNS"] = "\n".join(runs)
    (dest / "tables.md").write_text("\n\n".join(f"## {k}\n\n{v}" for k, v in tables.items()))
    return tables

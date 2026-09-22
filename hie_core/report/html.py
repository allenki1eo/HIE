"""Build the interactive comparison report for an EXP-hdrplus run.

Output: ``<run>/report/index.html`` plus ``assets/`` (per-burst crop sprite sheets and
full-frame thumbnails). The page follows ISO 3664's idea of a neutral surround: images
sit on an unbiased grey so the surround does not tint colour judgements.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SOURCES: list[tuple[str, str, str]] = [
    ("single", "Single frame", "EXP-001 · reference frame only"),
    ("single_denoised", "Single + denoise", "reference + the same spatial denoiser"),
    ("mean_noalign", "Mean, no align", "ablation: no alignment"),
    ("mean", "Mean", "EXP-002 · tile alignment + average"),
    ("median", "Median", "EXP-003 · per-pixel median"),
    ("weighted", "Sharpness-weighted", "baseline 3"),
    ("motion_aware", "Motion-aware", "baseline 4 · pixel Wiener"),
    ("flow_mean", "Optical-flow mean", "EXP-004 · DIS flow + average"),
    ("hdrplus_wiener", "HDR+ merge (repro.)", "Hasinoff 2016 temporal Wiener"),
    ("confidence", "Confidence", "EXP-005 · per-pixel confidence"),
    ("hie_v0.1", "HIE v0.1", "confidence + N_eff spatial denoise"),
    ("hdrplus_merge", "Google merge · HIE finish", "Google merged.dng, our rendering"),
    ("hdrplus_final", "Google HDR+ final", "Google's own finishing"),
]
CROP_KINDS = [("detail", "Detail"), ("shadows", "Shadows"), ("highlights", "Highlights"),
              ("disagreement", "Where methods disagree")]
THUMBS = ["single", "hie_v0.1", "hdrplus_merge", "hdrplus_final"]


def _sprite(paths: list[Path], out: Path) -> None:
    tiles = [Image.open(p).convert("RGB") for p in paths]
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * len(tiles), h))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * w, 0))
    sheet.save(out, quality=86, optimize=True, progressive=True)


def _thumb(src: Path, out: Path, width: int = 900) -> None:
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(out, quality=84, optimize=True, progressive=True)


def _final_is_aligned(burst_dir: Path) -> bool:
    from ..bench.run import FINAL_MAX_SHIFT_PX, FINAL_MIN_CORR, final_alignment
    from ..io.images import load_image

    ours, final = burst_dir / "single.jpg", burst_dir / "hdrplus_final.jpg"
    if not (ours.exists() and final.exists()):
        return False
    a, b = load_image(ours), load_image(final)
    shift, corr = final_alignment(b, a)
    if shift is None:
        return False
    full_scale = 4048 / max(a.shape[:2])  # thumbnails are downscaled; compare in full-resolution pixels
    return shift * full_scale < FINAL_MAX_SHIFT_PX * 2 and corr > FINAL_MIN_CORR


def _clean(obj: Any) -> Any:
    """Replace NaN/inf with None recursively so the embedded data is valid JSON."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    return obj


def _latest(root: Path, experiment: str) -> Path | None:
    runs = sorted((root / experiment).glob("*/summary.json")) if (root / experiment).exists() else []
    return runs[-1].parent if runs else None


def build_report(run: str | Path, synthetic_run: str | Path | None = None,
                 findings: list[str] | None = None) -> Path:
    run = Path(run)
    out = run / "report"
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    rows = json.loads((run / "rows.json").read_text())
    record = json.loads((run / "experiment.json").read_text())
    synthetic_run = Path(synthetic_run) if synthetic_run else _latest(run.parents[1], "EXP-synthetic")
    synth = json.loads((synthetic_run / "summary.json").read_text()) if synthetic_run else {}

    bursts: list[dict[str, Any]] = []
    for burst_dir in sorted(p for p in run.iterdir() if p.is_dir() and (p / "meta.json").exists()):
        meta = json.loads((burst_dir / "meta.json").read_text())
        bid = meta["burst"]
        crop_dir = burst_dir / "crops"
        available = [s for s, _, _ in SOURCES if (crop_dir / f"detail__{s}.jpg").exists()]
        final_ok = _final_is_aligned(burst_dir)
        if not final_ok and "hdrplus_final" in available:  # second guard, on the saved full-frame renders
            available.remove("hdrplus_final")
        sprites = {}
        for kind, _ in CROP_KINDS:
            name = f"{bid}__{kind}.jpg"
            _sprite([crop_dir / f"{kind}__{s}.jpg" for s in available], assets / name)
            sprites[kind] = f"assets/{name}"
        thumbs = {}
        for s in THUMBS:
            if (burst_dir / f"{s}.jpg").exists():
                name = f"{bid}__thumb__{s}.jpg"
                _thumb(burst_dir / f"{s}.jpg", assets / name)
                thumbs[s] = f"assets/{name}"
        metrics = {r["preset"]: {k: r[k] for k in ("noise_reduction_db", "ref_deviation_rate",
                                                   "psnr_vs_hdrplus_merge", "runtime_s")}
                   for r in rows if r["burst"] == bid}
        bursts.append({
            "id": bid, "camera": meta["camera"], "iso": meta["iso"], "exposure": meta["exposure_time"],
            "frames": meta["frames"], "reference": meta["reference_frame"], "notes": meta.get("notes", []),
            "noise": meta.get("noise_model", {}).get("source"), "final_aligned": final_ok,
            "sources": available, "sprites": sprites, "thumbs": thumbs, "metrics": metrics,
        })
    bursts.sort(key=lambda b: b["iso"] or 0)

    presets = list(dict.fromkeys(r["preset"] for r in rows))

    def mean_or_none(values: list) -> float | None:
        vals = [v for v in values if v is not None and np.isfinite(v)]
        return float(np.mean(vals)) if vals else None

    real = {p: {k: mean_or_none([r[k] for r in rows if r["preset"] == p])
                for k in ("noise_reduction_db", "ref_deviation_rate", "psnr_vs_hdrplus_merge", "runtime_s")}
            for p in presets}
    data = {
        "sources": [{"id": s, "label": l, "note": n} for s, l, n in SOURCES],
        "crops": [{"id": k, "label": l} for k, l in CROP_KINDS],
        "bursts": bursts, "real": real, "synthetic": synth, "presets": presets,
        "commit": (record.get("commit") or "")[:10], "dirty": record.get("dirty"),
        "date": record.get("timestamp", "")[:10],
        "synthetic_commit": (json.loads((synthetic_run / "experiment.json").read_text()).get("commit") or "")[:10]
        if synthetic_run else None,
    }
    page = TEMPLATE.replace("/*__DATA__*/null", json.dumps(_clean(data), allow_nan=False)).replace(
        "<!--__FINDINGS__-->", "".join(f"<li>{f}</li>" for f in (findings or [])))
    (out / "index.html").write_text(page)
    print(f"report → {out / 'index.html'}")
    return out / "index.html"


TEMPLATE = (Path(__file__).with_name("template.html")).read_text() if Path(__file__).with_name("template.html").exists() else ""

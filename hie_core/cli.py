"""``hie`` command-line interface.

    hie data list                         remote bursts in the HDR+ archive
    hie data download ID [ID …]           mirror bursts + HDR+ results (MD5-verified)
    hie data local                        bursts available locally
    hie inspect PATH|BURST_ID             dimensions, bit depth, CFA, levels, noise, colour
    hie process PATH|BURST_ID -p hie_v0.1 render a burst (writes a new run directory)
    hie bench synthetic                   EXP-001…005 on synthetic ground truth
    hie bench hdrplus                     baselines on local HDR+ bursts (+ visual report)
    hie bench alignment                   failure analysis: aligners vs oracle alignment
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .datasets import HDRPlusDataset, download_bursts, list_remote_bursts, load_dng_folder
from .datasets.inspect import describe_burst
from .io import new_run_dir, save_jpeg, save_tiff16, write_record
from .io.experiment import REPO_ROOT
from .pipeline import PRESETS, preset, process_burst

RESULTS = REPO_ROOT / "benchmarks" / "results"


def _load(target: str, archive: str):
    """Resolve a DNG folder path or an HDR+ burst id to (frames, reference index, description)."""
    path = Path(target)
    if path.exists():
        frames, meta = load_dng_folder(path)
        return frames, None, {"source": str(path), **meta}
    ds = HDRPlusDataset(archive=archive)
    sample = ds.load_sample(target)
    return sample.load_raw_frames(), sample.reference_index, {"source": f"hdrplus:{archive}:{target}"}


def cmd_data(args: argparse.Namespace) -> int:
    if args.action == "list":
        ids = list_remote_bursts(args.archive)
        print("\n".join(ids))
        print(f"# {len(ids)} bursts in {args.archive}", file=sys.stderr)
    elif args.action == "download":
        download_bursts(args.ids, archive=args.archive)
    elif args.action == "local":
        print("\n".join(HDRPlusDataset(archive=args.archive).list_samples()))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    frames, ref, info = _load(args.target, args.archive)
    desc = describe_burst(frames)
    if args.json:
        print(json.dumps({"reference_frame": ref, **info, **desc}, indent=2))
        return 0
    print(f"{info['source']}\n  {desc['frames']} frames · {desc['camera']} · {desc['size']} · CFA {desc['cfa']}"
          f" · exposure consistent: {desc['exposure_consistent']} · HDR+ reference frame: {ref}")
    cols = ["file", "bits", "black", "white", "iso", "exposure_s", "mean_level", "clipped_%", "noise_S_O", "neutral"]
    for row in desc["per_frame"]:
        print("  " + "  ".join(f"{c}={row[c]}" for c in cols))
    if args.preview:
        result = process_burst(frames[:1], preset("single"))
        save_jpeg(args.preview, result.display, quality=90)
        print(f"  preview → {args.preview}")
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    frames, ref, info = _load(args.target, args.archive)
    cfg = preset(args.preset)
    result = process_burst(frames, cfg, ref_index=ref if args.use_dataset_reference else None)
    run = new_run_dir(args.out or RESULTS, "process", f"{Path(args.target).name}_{cfg.name}")
    save_jpeg(run / "output.jpg", result.display)
    if args.tiff:
        save_tiff16(run / "output.tiff", result.display)
    write_record(run, {"algorithm": cfg.name, "config": cfg, "input": info, "frame_count": len(frames),
                       "timings_s": result.timings, "info": result.info})
    print(f"{cfg.name}: {result.info['frames_used']} frames, {result.timings['total']:.1f}s → {run}")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    if args.suite == "alignment":
        from .bench.alignment_study import run
        run()
    elif args.suite == "synthetic":
        from .bench.run import run_synthetic_suite
        run_synthetic_suite(args.presets, split=args.split)
    else:
        from .bench.run import run_hdrplus_suite
        run_hdrplus_suite(args.presets, bursts=args.bursts, archive=args.archive, report=not args.no_report,
                          max_side=args.max_side)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="hie", description="Hanson Image Engine research CLI")
    p.add_argument("--archive", default="20171106_subset", help="HDR+ archive (default: curated subset)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("data", help="HDR+ dataset access")
    d.add_argument("action", choices=["list", "download", "local"])
    d.add_argument("ids", nargs="*")
    d.set_defaults(fn=cmd_data)

    i = sub.add_parser("inspect", help="inspect a burst")
    i.add_argument("target")
    i.add_argument("--json", action="store_true")
    i.add_argument("--preview", help="write a single-frame preview JPEG")
    i.set_defaults(fn=cmd_inspect)

    r = sub.add_parser("process", help="render a burst")
    r.add_argument("target")
    r.add_argument("-p", "--preset", default="hie_v0.1", choices=sorted(PRESETS))
    r.add_argument("--out")
    r.add_argument("--tiff", action="store_true", help="also write a 16-bit TIFF")
    r.add_argument("--use-dataset-reference", action="store_true", help="use HDR+ reference_frame.txt")
    r.set_defaults(fn=cmd_process)

    b = sub.add_parser("bench", help="run a benchmark suite")
    b.add_argument("suite", choices=["synthetic", "hdrplus", "alignment"])
    b.add_argument("--presets", nargs="+", default=None)
    b.add_argument("--split", default="test", choices=["test", "tune"])
    b.add_argument("--bursts", nargs="*", default=None)
    b.add_argument("--max-side", type=int, default=None, help="downscale renders for the visual report")
    b.add_argument("--no-report", action="store_true")
    b.set_defaults(fn=cmd_bench)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())

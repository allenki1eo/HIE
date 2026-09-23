"""Validate and describe Hanson Camera Lab experiment packages (brief §21).

A package is a never-overwritten folder::

    experiment_0001/
      experiment.json
      metadata.json            per-frame CaptureResult
      raw/frame_000.dng …
      motion/sensors.csv       optional gyro + accelerometer
      stock/reference.jpg      optional hardware-ISP JPEG of the same scene
      hie/                     on-device or workstation HIE output (``output.jpg``)

The loader in :mod:`hie_core.datasets.folder` already reads ``raw/*.dng``.
This module checks the layout and sidecars without silently dropping frames.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

from .folder import find_dngs

SCHEMA = "hie.camera_lab.package/v1"
PACKAGE_NAME = re.compile(r"^experiment_\d{4,}$")
MOTION_HEADER = ("t_ns", "sensor", "x", "y", "z", "accuracy")


class PackageError(ValueError):
    """The folder is not a Camera Lab package, or it is incomplete."""


def is_package_dir(path: str | Path) -> bool:
    path = Path(path)
    return path.is_dir() and (path / "experiment.json").is_file()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise PackageError(f"invalid JSON in {path}: {exc}") from exc


def load_motion_csv(path: str | Path) -> list[dict[str, Any]]:
    """Read ``motion/sensors.csv``. Empty file (header only) is valid."""
    path = Path(path)
    if not path.is_file():
        raise PackageError(f"missing motion log {path}")
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise PackageError(f"{path} has no header")
        missing = [c for c in MOTION_HEADER if c not in reader.fieldnames]
        if missing:
            raise PackageError(f"{path} missing columns {missing}; have {reader.fieldnames}")
        rows: list[dict[str, Any]] = []
        for i, row in enumerate(reader, start=2):
            try:
                rows.append({
                    "t_ns": int(row["t_ns"]),
                    "sensor": row["sensor"],
                    "x": float(row["x"]),
                    "y": float(row["y"]),
                    "z": float(row["z"]),
                    "accuracy": int(row["accuracy"]) if row.get("accuracy") not in (None, "") else None,
                })
            except (TypeError, ValueError) as exc:
                raise PackageError(f"{path} line {i}: {exc}") from exc
    return rows


def _require_keys(obj: dict, keys: list[str], where: str) -> list[str]:
    return [f"{where}: missing {k}" for k in keys if k not in obj]


def validate_package(path: str | Path, *, require_dngs: bool = True) -> dict[str, Any]:
    """Inspect a package. Raises :class:`PackageError` on structural failure.

    Frame exclusions are never silent: missing DNGs relative to ``metadata.json``
    are listed in ``problems`` and, when ``require_dngs`` is true, raise.
    """
    path = Path(path)
    problems: list[str] = []
    notes: list[str] = []
    if not path.is_dir():
        raise PackageError(f"not a directory: {path}")
    if not PACKAGE_NAME.match(path.name):
        notes.append(f"directory name {path.name!r} is not experiment_NNNN (accepted, recorded)")

    exp_path = path / "experiment.json"
    if not exp_path.is_file():
        raise PackageError(f"missing {exp_path}")
    experiment = load_json(exp_path)
    if not isinstance(experiment, dict):
        raise PackageError("experiment.json must be an object")
    problems.extend(_require_keys(experiment, ["schema", "device", "capture_policy"], "experiment.json"))
    if experiment.get("schema") not in (None, SCHEMA):
        notes.append(f"schema {experiment.get('schema')!r} != {SCHEMA}")

    meta: dict[str, Any] = {}
    meta_path = path / "metadata.json"
    if meta_path.is_file():
        loaded = load_json(meta_path)
        if not isinstance(loaded, dict):
            raise PackageError("metadata.json must be an object")
        meta = loaded
    else:
        notes.append("no metadata.json")

    dngs: list[Path] = []
    raw_dir = path / "raw"
    if raw_dir.is_dir():
        try:
            dngs = find_dngs(path)
        except FileNotFoundError as exc:
            problems.append(str(exc))
    elif require_dngs:
        problems.append(f"missing raw/ under {path}")
    else:
        notes.append("no raw/ directory")

    declared = []
    frames_meta = meta.get("frames")
    if isinstance(frames_meta, list):
        for i, fr in enumerate(frames_meta):
            if not isinstance(fr, dict):
                problems.append(f"metadata.frames[{i}] is not an object")
                continue
            rel = fr.get("file")
            if rel:
                declared.append(rel)
                if not (path / rel).is_file():
                    problems.append(f"declared frame missing: {rel}")
            else:
                problems.append(f"metadata.frames[{i}] has no file")
        found_names = {p.name for p in dngs}
        declared_names = {Path(r).name for r in declared}
        extra = sorted(found_names - declared_names)
        missing = sorted(declared_names - found_names)
        if extra:
            problems.append(f"DNG files not listed in metadata.json: {extra}")
        if missing:
            problems.append(f"metadata lists DNGs that are not on disk: {missing}")
    elif dngs:
        notes.append(f"{len(dngs)} DNGs present but metadata.json has no frames list")

    motion_rows = 0
    motion_path = path / "motion" / "sensors.csv"
    if motion_path.is_file():
        motion_rows = len(load_motion_csv(motion_path))
    else:
        notes.append("no motion/sensors.csv")

    stock = path / "stock" / "reference.jpg"
    if not stock.is_file():
        notes.append("no stock/reference.jpg")

    if require_dngs and problems:
        raise PackageError("; ".join(problems))

    return {
        "path": str(path),
        "schema": experiment.get("schema"),
        "device": experiment.get("device"),
        "app": experiment.get("app"),
        "capture_policy": experiment.get("capture_policy"),
        "dng_count": len(dngs),
        "dngs": [p.name for p in dngs],
        "declared_frames": declared,
        "motion_samples": motion_rows,
        "has_stock_jpeg": stock.is_file(),
        "has_hie_jpeg": (path / "hie" / "output.jpg").is_file(),
        "has_metadata": meta_path.is_file(),
        "notes": notes,
        "problems": problems,
        "ok": not problems,
    }

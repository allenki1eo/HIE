import csv
import json
from pathlib import Path

import pytest

from hie_core.datasets.package import PACKAGE_NAME, PackageError, load_motion_csv, validate_package


def _write_motion(path: Path, rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["t_ns", "sensor", "x", "y", "z", "accuracy"])
        w.writerows(rows)


def _package(tmp: Path, name: str = "experiment_0001") -> Path:
    root = tmp / name
    (root / "raw").mkdir(parents=True)
    (root / "stock").mkdir()
    (root / "motion").mkdir()
    (root / "experiment.json").write_text(json.dumps({
        "schema": "hie.camera_lab.package/v1",
        "device": {"manufacturer": "Google", "model": "Pixel 6", "android_sdk": 33},
        "app": {"name": "Hanson Camera Lab", "version": "0.1.0"},
        "capture_policy": {"mode": "burst", "frame_count": 2, "ae_lock": True, "awb_lock": True},
    }))
    (root / "metadata.json").write_text(json.dumps({
        "frames": [
            {"file": "raw/frame_000.dng", "sensor_timestamp_ns": 1, "sensitivity": 100},
            {"file": "raw/frame_001.dng", "sensor_timestamp_ns": 2, "sensitivity": 100},
        ]
    }))
    (root / "raw" / "frame_000.dng").write_bytes(b"dng0")
    (root / "raw" / "frame_001.dng").write_bytes(b"dng1")
    (root / "stock" / "reference.jpg").write_bytes(b"jpeg")
    _write_motion(root / "motion" / "sensors.csv", [
        (10, "gyro", 0.1, 0.0, -0.2, 3),
        (11, "accel", 0.0, 9.8, 0.1, 3),
    ])
    return root


def test_package_name_pattern():
    assert PACKAGE_NAME.match("experiment_0001")
    assert PACKAGE_NAME.match("experiment_0042")
    assert not PACKAGE_NAME.match("exp_1")
    assert not PACKAGE_NAME.match("experiment_1")


def test_validate_complete_package(tmp_path):
    root = _package(tmp_path)
    info = validate_package(root, require_dngs=False)
    assert info["ok"]
    assert info["dng_count"] == 2
    assert info["motion_samples"] == 2
    assert info["has_stock_jpeg"]
    assert not info["has_hie_jpeg"]
    assert info["problems"] == []


def test_validate_records_on_device_hie_jpeg(tmp_path):
    root = _package(tmp_path)
    (root / "hie").mkdir()
    (root / "hie" / "output.jpg").write_bytes(b"hie-jpeg")
    info = validate_package(root, require_dngs=False)
    assert info["has_hie_jpeg"]


def test_declared_frame_missing_is_an_error(tmp_path):
    root = _package(tmp_path)
    (root / "raw" / "frame_001.dng").unlink()
    with pytest.raises(PackageError, match="missing"):
        validate_package(root, require_dngs=True)
    info = validate_package(root, require_dngs=False)
    assert not info["ok"]
    assert any("missing" in p for p in info["problems"])


def test_undeclared_dng_is_an_error(tmp_path):
    root = _package(tmp_path)
    (root / "raw" / "frame_002.dng").write_bytes(b"extra")
    info = validate_package(root, require_dngs=False)
    assert any("not listed" in p for p in info["problems"])


def test_motion_csv_requires_header(tmp_path):
    path = tmp_path / "sensors.csv"
    path.write_text("1,gyro,0,0,0,3\n")
    with pytest.raises(PackageError, match="missing columns"):
        load_motion_csv(path)


def test_motion_csv_bad_row(tmp_path):
    path = tmp_path / "sensors.csv"
    _write_motion(path, [("not-an-int", "gyro", 0, 0, 0, 3)])
    with pytest.raises(PackageError, match="line 2"):
        load_motion_csv(path)


def test_missing_experiment_json(tmp_path):
    d = tmp_path / "experiment_0001"
    d.mkdir()
    with pytest.raises(PackageError, match="experiment.json"):
        validate_package(d, require_dngs=False)

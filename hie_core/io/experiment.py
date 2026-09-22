"""Reproducible experiment records (brief §21, §25).

Every run writes into a fresh directory that is never overwritten, together with
an ``experiment.json`` recording the git commit, a dirty-tree flag, parameters
and environment, so results can be traced back to exact code.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .. import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]


def git_state() -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = run("status", "--porcelain")
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None}


def environment() -> dict[str, Any]:
    import cv2
    import rawpy
    import scipy

    return {
        "hie_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "opencv": cv2.__version__,
        "rawpy": rawpy.__version__,
    }


def jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist() if obj.size <= 64 else f"<array {obj.shape} {obj.dtype}>"
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def new_run_dir(root: str | Path, experiment_id: str, label: str | None = None) -> Path:
    """Create ``root/<experiment_id>/<UTC timestamp>[_label]``; refuses to reuse an existing directory."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}_{label}" if label else stamp
    path = Path(root) / experiment_id / name
    path.mkdir(parents=True, exist_ok=False)
    return path


def write_record(run_dir: Path, record: dict[str, Any]) -> Path:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **git_state(),
        "environment": environment(),
        **record,
    }
    out = run_dir / "experiment.json"
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    out.write_text(json.dumps(jsonable(record), indent=2))
    return out

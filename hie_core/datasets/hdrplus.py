"""Google HDR+ Burst Photography Dataset (Hasinoff et al., SIGGRAPH Asia 2016).

Layout, as inspected in the public bucket ``gs://hdrplusdata`` (see
datasets/google-hdr-plus/README.md)::

    <archive>/bursts/<burst_id>/payload_N###.dng           input frames
                               lens_shading_map_N###.tiff   (h, w, 4) gains, order R, Gr, Gb, B
                               rgb2rgb.txt                  3x3 WB-camera → linear sRGB
                               timing.txt                   (optional)
    <archive>/results_YYYYMMDD/<burst_id>/merged.dng        HDR+ align+merge output
                                          final.jpg         HDR+ finished output
                                          reference_frame.txt

The local mirror keeps exactly this layout so provenance is unambiguous. Files are
never modified. Frames are discovered by pattern and a missing or unreadable frame
raises an error — nothing is dropped silently.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np
import tifffile

from ..io.images import load_image
from ..raw import RawFrame, read_dng

BUCKET = "hdrplusdata"
API = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o"
MEDIA = f"https://storage.googleapis.com/{BUCKET}/"
DEFAULT_ARCHIVE = "20171106_subset"
DEFAULT_RESULTS = "results_20171023"
_FRAME_RE = re.compile(r"payload_N(\d+)\.dng$")
REPO_ROOT = Path(__file__).resolve().parents[2]


def default_root() -> Path:
    return Path(os.environ.get("HIE_HDRPLUS_ROOT", REPO_ROOT / "datasets" / "google-hdr-plus"))


class DatasetError(RuntimeError):
    pass


@dataclass
class BurstSample:
    sample_id: str
    burst_dir: Path
    result_dir: Path | None
    frame_paths: list[Path]
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def reference_index(self) -> int | None:
        return self.metadata.get("reference_frame")

    def load_raw_frames(self, *, sidecar_shading: bool = True) -> list[RawFrame]:
        frames = []
        for path in self.frame_paths:
            try:
                frame = read_dng(path)
            except Exception as exc:  # surface which frame failed — never skip it
                raise DatasetError(f"{self.sample_id}: failed to read {path.name}: {exc}") from exc
            idx = int(_FRAME_RE.search(path.name).group(1))
            lsc = self.burst_dir / f"lens_shading_map_N{idx:03d}.tiff"
            if sidecar_shading and frame.lens_shading is None and lsc.exists():
                frame.lens_shading = _read_shading_map(lsc)
            if "rgb2rgb" in self.metadata:
                frame.meta.extras["rgb2rgb"] = self.metadata["rgb2rgb"]
            frame.meta.extras["frame_index"] = idx
            frames.append(frame)
        return frames

    def load_intermediate(self) -> RawFrame | None:
        """HDR+ ``merged.dng`` (aligned+merged raw, higher precision) if downloaded."""
        path = self.result_dir / "merged.dng" if self.result_dir else None
        return read_dng(path) if path and path.exists() else None

    def load_final(self) -> np.ndarray | None:
        """HDR+ ``final.jpg`` as float RGB, if downloaded."""
        path = self.result_dir / "final.jpg" if self.result_dir else None
        return load_image(path) if path and path.exists() else None


def _read_shading_map(path: Path) -> np.ndarray | None:
    m = tifffile.imread(path).astype(np.float32)
    # 293 of the oldest bursts originally had corrupted 3-channel maps (fixed 2020-12-15);
    # refuse anything that is not the documented 4-channel layout.
    return m if m.ndim == 3 and m.shape[-1] == 4 else None


class HDRPlusDataset:
    def __init__(self, root: str | Path | None = None, archive: str = DEFAULT_ARCHIVE, results: str = DEFAULT_RESULTS):
        self.root = Path(root) if root else default_root()
        self.archive = archive
        self.results = results

    @property
    def bursts_dir(self) -> Path:
        return self.root / self.archive / "bursts"

    def list_samples(self) -> list[str]:
        if not self.bursts_dir.exists():
            return []
        return sorted(p.name for p in self.bursts_dir.iterdir() if p.is_dir())

    def __iter__(self) -> Iterator[BurstSample]:
        for sid in self.list_samples():
            yield self.load_sample(sid)

    def load_sample(self, sample_id: str) -> BurstSample:
        burst_dir = self.bursts_dir / sample_id
        if not burst_dir.is_dir():
            raise DatasetError(f"Burst {sample_id} not found under {self.bursts_dir}")
        indexed = sorted((int(m.group(1)), p) for p in burst_dir.iterdir() if (m := _FRAME_RE.search(p.name)))
        if not indexed:
            raise DatasetError(f"{sample_id}: no payload_N###.dng frames")
        indices = [i for i, _ in indexed]
        meta: dict[str, Any] = {"frame_indices": indices}
        if indices != list(range(len(indices))):
            meta["warning_non_contiguous_frames"] = indices
        rgb2rgb = burst_dir / "rgb2rgb.txt"
        if rgb2rgb.exists():
            meta["rgb2rgb"] = np.loadtxt(rgb2rgb).reshape(3, 3).tolist()
        timing = burst_dir / "timing.txt"
        if timing.exists():
            meta["timing"] = timing.read_text().strip()
        result_dir = self.root / self.archive / self.results / sample_id
        if result_dir.is_dir():
            ref = result_dir / "reference_frame.txt"
            if ref.exists():
                meta["reference_frame"] = int(ref.read_text().strip())
        else:
            result_dir = None
        return BurstSample(sample_id, burst_dir, result_dir, [p for _, p in indexed], meta)


# ---------------------------------------------------------------------------- download
def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def list_remote(prefix: str, delimiter: str | None = "/") -> tuple[list[str], list[dict]]:
    """List (sub-prefixes, objects) under ``prefix`` in the public bucket."""
    prefixes: list[str] = []
    items: list[dict] = []
    token = None
    while True:
        q = {"prefix": prefix, "maxResults": "1000"}
        if delimiter:
            q["delimiter"] = delimiter
        if token:
            q["pageToken"] = token
        page = _get_json(f"{API}?{urllib.parse.urlencode(q)}")
        prefixes += page.get("prefixes", [])
        items += page.get("items", [])
        token = page.get("nextPageToken")
        if not token:
            return prefixes, items


def list_remote_bursts(archive: str = DEFAULT_ARCHIVE) -> list[str]:
    prefixes, _ = list_remote(f"{archive}/bursts/")
    return sorted(p.rstrip("/").split("/")[-1] for p in prefixes)


def _md5_b64(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def download_bursts(
    burst_ids: list[str],
    root: str | Path | None = None,
    archive: str = DEFAULT_ARCHIVE,
    results: tuple[str, ...] = (DEFAULT_RESULTS,),
    progress: Callable[[str], None] = print,
) -> Path:
    """Mirror bursts (and their HDR+ results) into ``root`` with MD5 verification.

    Appends one entry per file to ``<root>/manifest.jsonl`` (source URL, size, MD5,
    download time) so the exact dataset version used by an experiment is recorded.
    """
    root = Path(root) if root else default_root()
    manifest = root / "manifest.jsonl"
    root.mkdir(parents=True, exist_ok=True)
    for bid in burst_ids:
        for sub in ("bursts", *results):
            _, items = list_remote(f"{archive}/{sub}/{bid}/", delimiter=None)
            if not items:
                progress(f"  ! {archive}/{sub}/{bid}: nothing found")
            for obj in items:
                dest = root / obj["name"]
                if dest.exists() and _md5_b64(dest) == obj["md5Hash"]:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_suffix(dest.suffix + ".part")
                urllib.request.urlretrieve(MEDIA + urllib.parse.quote(obj["name"]), tmp)
                if _md5_b64(tmp) != obj["md5Hash"]:
                    tmp.unlink(missing_ok=True)
                    raise DatasetError(f"MD5 mismatch for {obj['name']}")
                tmp.rename(dest)
                with open(manifest, "a") as mf:
                    mf.write(json.dumps({
                        "object": obj["name"], "size": int(obj["size"]), "md5": obj["md5Hash"],
                        "generation": obj.get("generation"), "url": MEDIA + obj["name"],
                        "downloaded": datetime.now(timezone.utc).isoformat(),
                    }) + "\n")
        progress(f"  ✓ {bid}")
    return root

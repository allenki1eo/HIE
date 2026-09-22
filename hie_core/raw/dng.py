"""DNG reading with exact metadata.

Pixel data is decoded by LibRaw (``rawpy``) because DNGs are commonly
lossless-JPEG compressed. Metadata is read directly from the TIFF IFDs with
``tifffile`` because LibRaw rounds fractional black levels (e.g. 63.75 → 63 on
the HDR+ dataset) and does not expose ``NoiseProfile`` or ``OpcodeList2``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import rawpy
import tifffile

from .bayer import pattern_from_cfa_codes, plane_offsets
from .frame import CaptureMetadata, RawFrame
from .opcodes import gain_maps_to_plane_shading, parse_opcode_list

_RATIONAL_TYPES = {5, 10}  # RATIONAL, SRATIONAL
CFA_PHOTOMETRIC = 32803


class DngError(RuntimeError):
    pass


def _tag_value(tag: tifffile.TiffTag) -> Any:
    """Decode a tag value, turning flat (num, den, num, den, …) rationals into floats."""
    value = tag.value
    if int(tag.dtype) in _RATIONAL_TYPES:
        arr = np.asarray(value, dtype=np.float64).reshape(-1, 2)
        with np.errstate(divide="ignore", invalid="ignore"):
            vals = np.where(arr[:, 1] != 0, arr[:, 0] / arr[:, 1], 0.0)
        return vals if vals.size > 1 else float(vals[0])
    return value


def _find_raw_page(tif: tifffile.TiffFile) -> tifffile.TiffPage:
    """Locate the full-resolution CFA IFD (it may live in IFD0 or in a SubIFD)."""
    candidates: list[tifffile.TiffPage] = []
    for page in tif.pages:
        candidates.append(page)
        candidates.extend(getattr(page, "pages", None) or [])
    for page in candidates:
        if page.photometric == CFA_PHOTOMETRIC and page.subfiletype == 0:
            return page
    raise DngError("No full-resolution CFA image (PhotometricInterpretation=32803) found")


class _Tags:
    """Look up a tag in the raw IFD first, then IFD0, then the EXIF IFD."""

    def __init__(self, raw_page: tifffile.TiffPage, ifd0: tifffile.TiffPage):
        self.raw = raw_page.tags
        self.ifd0 = ifd0.tags
        exif = ifd0.tags.get("ExifTag")
        self.exif: dict[str, Any] = exif.value if exif is not None and isinstance(exif.value, dict) else {}

    def get(self, name: str, default: Any = None) -> Any:
        for tags in (self.raw, self.ifd0):
            tag = tags.get(name)
            if tag is not None:
                return _tag_value(tag)
        return default

    def exif_get(self, name: str) -> Any:
        """EXIF value, falling back to the main IFDs (TIFF/EP DNGs such as Nexus 5 store them there)."""
        if name not in self.exif:
            return self.get(name)
        v = self.exif.get(name)
        if isinstance(v, tuple) and len(v) == 2 and name in ("ExposureTime", "FNumber", "FocalLength"):
            return v[0] / v[1] if v[1] else None
        if isinstance(v, tuple) and len(v) == 1:
            return v[0]
        return v


def _matrix(v: Any, shape: tuple[int, int]) -> np.ndarray | None:
    if v is None:
        return None
    arr = np.asarray(v, dtype=np.float64).ravel()
    if arr.size != shape[0] * shape[1]:
        return None
    return arr.reshape(shape)


def _vector(v: Any, n: int = 3) -> np.ndarray | None:
    if v is None:
        return None
    arr = np.atleast_1d(np.asarray(v, dtype=np.float64)).ravel()
    return arr[:n] if arr.size >= n else None


def _black_level_params(tags: _Tags) -> dict[str, Any]:
    """Collect black-level tags (must run while the TIFF file is open)."""
    rep = tags.get("BlackLevelRepeatDim", (1, 1))
    rep_r, rep_c = (int(rep[0]), int(rep[1])) if np.ndim(rep) else (1, 1)
    values = np.atleast_1d(np.asarray(tags.get("BlackLevel", 0.0), dtype=np.float64)).ravel()
    dh, dv = tags.get("BlackLevelDeltaH"), tags.get("BlackLevelDeltaV")
    return {
        "repeat": (rep_r, rep_c),
        "values": values,
        "delta_h": None if dh is None else np.asarray(dh, dtype=np.float64),
        "delta_v": None if dv is None else np.asarray(dv, dtype=np.float64),
    }


def _black_level_map(params: dict[str, Any], h: int, w: int) -> np.ndarray:
    """Per-pixel black level (H, W) from BlackLevel, its repeat pattern and row/column deltas."""
    rep_r, rep_c = params["repeat"]
    bl = params["values"]
    tile = bl[: rep_r * rep_c].reshape(rep_r, rep_c) if bl.size >= rep_r * rep_c else np.full((rep_r, rep_c), bl[0])
    black = np.tile(tile, (h // rep_r + 1, w // rep_c + 1))[:h, :w]
    if params["delta_h"] is not None:  # one value per column
        black = black + params["delta_h"][None, :w]
    if params["delta_v"] is not None:  # one value per row
        black = black + params["delta_v"][:h, None]
    return black


def read_dng(path: str | Path, *, apply_gain_map: bool = True) -> RawFrame:
    """Read a Bayer DNG into a normalised :class:`RawFrame`.

    ``apply_gain_map`` controls whether a GainMap in ``OpcodeList2`` is attached as
    the frame's lens-shading map (it is never baked into the pixel data here).
    """
    path = Path(path)
    with tifffile.TiffFile(path) as tif:
        raw_page = _find_raw_page(tif)
        tags = _Tags(raw_page, tif.pages[0])

        cfa_dim = tags.get("CFARepeatPatternDim", (2, 2))
        if tuple(int(x) for x in cfa_dim) != (2, 2):
            raise DngError(f"{path.name}: only 2x2 Bayer CFAs are supported (got {cfa_dim})")
        cfa_codes = raw_page.tags["CFAPattern"].value
        pattern = pattern_from_cfa_codes(tuple(cfa_codes))
        white = float(np.atleast_1d(tags.get("WhiteLevel", 2 ** int(np.atleast_1d(raw_page.bitspersample)[0]) - 1))[0])
        linearization = tags.get("LinearizationTable")
        opcode_blob = tags.get("OpcodeList2")
        black_params = _black_level_params(tags)

        meta = CaptureMetadata(
            make=tags.get("Make"),
            model=tags.get("Model"),
            unique_camera_model=tags.get("UniqueCameraModel"),
            datetime=tags.get("DateTime"),
            iso=_scalar(tags.exif_get("ISOSpeedRatings") or tags.exif_get("PhotographicSensitivity")),
            exposure_time=_scalar(tags.exif_get("ExposureTime")),
            f_number=_scalar(tags.exif_get("FNumber")),
            focal_length=_scalar(tags.exif_get("FocalLength")),
            orientation=int(tags.get("Orientation", 1) or 1),
            bits_per_sample=int(np.atleast_1d(raw_page.bitspersample)[0]),
            raw_white_level=white,
            as_shot_neutral=_vector(tags.get("AsShotNeutral")),
            color_matrix1=_matrix(tags.get("ColorMatrix1"), (3, 3)),
            color_matrix2=_matrix(tags.get("ColorMatrix2"), (3, 3)),
            camera_calibration1=_matrix(tags.get("CameraCalibration1"), (3, 3)),
            camera_calibration2=_matrix(tags.get("CameraCalibration2"), (3, 3)),
            forward_matrix1=_matrix(tags.get("ForwardMatrix1"), (3, 3)),
            forward_matrix2=_matrix(tags.get("ForwardMatrix2"), (3, 3)),
            analog_balance=_vector(tags.get("AnalogBalance")),
            calibration_illuminant1=_int_or_none(tags.get("CalibrationIlluminant1")),
            calibration_illuminant2=_int_or_none(tags.get("CalibrationIlluminant2")),
            baseline_exposure=_scalar(tags.get("BaselineExposure")),
            noise_profile=_noise_profile(tags.get("NoiseProfile"), tags.get("CFAPlaneColor")),
        )
        meta.extras["dng_version"] = list(tags.get("DNGVersion", ()) or ())

    # Pixel data via LibRaw; raw_image_visible is the ActiveArea crop, which is the
    # origin DNG uses for CFAPattern and BlackLevel repeats.
    with rawpy.imread(str(path)) as r:
        raw = np.asarray(r.raw_image_visible, dtype=np.float64)
        libraw_pattern = _libraw_pattern(r)
    if libraw_pattern is not None and libraw_pattern != pattern:
        raise DngError(f"{path.name}: CFA pattern mismatch between DNG tag ({pattern}) and LibRaw ({libraw_pattern})")
    h, w = raw.shape
    h, w = h - h % 2, w - w % 2
    raw = raw[:h, :w]

    if linearization is not None:
        table = np.asarray(linearization, dtype=np.float64)
        raw = table[np.clip(raw.astype(np.int64), 0, table.size - 1)]
    black = _black_level_map(black_params, h, w)
    meta.raw_black_level = [float(x) for x in black_params["values"]]
    cfa = ((raw - black) / (white - black)).astype(np.float32)

    lens_shading = None
    if opcode_blob is not None:
        ops = parse_opcode_list(bytes(opcode_blob))
        if ops.unsupported:
            meta.extras["unapplied_opcode_ids"] = ops.unsupported
        if apply_gain_map and ops.gain_maps:
            lens_shading = gain_maps_to_plane_shading(ops.gain_maps, (h, w), plane_offsets(pattern))
            if lens_shading is None:
                meta.extras["unapplied_gain_map"] = "non-Bayer-phase GainMap layout"

    return RawFrame(cfa=cfa, pattern=pattern, meta=meta, lens_shading=lens_shading, source=str(path))


def _libraw_pattern(r: rawpy.RawPy) -> str | None:
    try:
        desc = r.color_desc.decode()
        pat = r.raw_pattern
        letters = "".join(desc[pat[i, j]] for i in range(2) for j in range(2))
        return letters if set(letters) <= set("RGB") else None
    except Exception:  # LibRaw metadata is only a cross-check
        return None


def _scalar(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(np.atleast_1d(np.asarray(v, dtype=np.float64))[0])
    except (TypeError, ValueError):
        return None


def _int_or_none(v: Any) -> int | None:
    return None if v is None else int(np.atleast_1d(v)[0])


def _noise_profile(v: Any, plane_color: Any) -> np.ndarray | None:
    """NoiseProfile → (3, 2) array ordered R, G, B."""
    if v is None:
        return None
    arr = np.asarray(v, dtype=np.float64).reshape(-1, 2)
    if arr.shape[0] == 1:
        return np.repeat(arr, 3, axis=0)
    order = list(bytes(plane_color)) if plane_color is not None else [0, 1, 2]
    out = np.empty((3, 2))
    for i, color in enumerate(order[: arr.shape[0]]):
        out[color] = arr[i]
    return out

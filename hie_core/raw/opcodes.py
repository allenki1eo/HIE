"""DNG opcode-list parsing (DNG 1.4 spec, chapter 7).

Only the ``GainMap`` opcode (ID 9) is interpreted: Android's ``DngCreator`` and
the Google HDR+ ``merged.dng`` files store lens-shading/vignetting correction in
``OpcodeList2`` as one GainMap per Bayer phase. Other opcodes are reported, never
silently dropped, so callers can decide whether ignoring them is acceptable.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

import numpy as np

GAIN_MAP_ID = 9


@dataclass(frozen=True)
class GainMap:
    top: int
    left: int
    bottom: int
    right: int
    plane: int
    planes: int
    row_pitch: int
    col_pitch: int
    map_points_v: int
    map_points_h: int
    map_spacing_v: float
    map_spacing_h: float
    map_origin_v: float
    map_origin_h: float
    map_planes: int
    gains: np.ndarray  # (map_points_v, map_points_h, map_planes) float32


@dataclass
class OpcodeList:
    gain_maps: list[GainMap] = field(default_factory=list)
    unsupported: list[int] = field(default_factory=list)  # opcode IDs that were not applied


def parse_opcode_list(blob: bytes) -> OpcodeList:
    """Parse a big-endian DNG opcode list blob."""
    result = OpcodeList()
    (count,) = struct.unpack_from(">I", blob, 0)
    pos = 4
    for _ in range(count):
        opcode_id, _version, _flags, nbytes = struct.unpack_from(">IIII", blob, pos)
        pos += 16
        params = blob[pos : pos + nbytes]
        pos += nbytes
        if opcode_id == GAIN_MAP_ID:
            result.gain_maps.append(_parse_gain_map(params))
        else:
            result.unsupported.append(opcode_id)
    return result


def _parse_gain_map(p: bytes) -> GainMap:
    top, left, bottom, right, plane, planes, row_pitch, col_pitch, pv, ph = struct.unpack_from(">10I", p, 0)
    sv, sh, ov, oh = struct.unpack_from(">4d", p, 40)
    (map_planes,) = struct.unpack_from(">I", p, 72)
    n = pv * ph * map_planes
    gains = np.frombuffer(p, dtype=">f4", count=n, offset=76).astype(np.float32).reshape(pv, ph, map_planes)
    return GainMap(top, left, bottom, right, plane, planes, row_pitch, col_pitch, pv, ph, sv, sh, ov, oh, map_planes, gains)


def encode_gain_map(g: GainMap) -> bytes:
    """Serialise a GainMap (used by tests and by synthetic DNG experiments)."""
    head = struct.pack(
        ">10I4dI", g.top, g.left, g.bottom, g.right, g.plane, g.planes, g.row_pitch, g.col_pitch,
        g.map_points_v, g.map_points_h, g.map_spacing_v, g.map_spacing_h, g.map_origin_v, g.map_origin_h, g.map_planes,
    )
    return head + g.gains.astype(">f4").tobytes()


def encode_opcode_list(gain_maps: list[GainMap]) -> bytes:
    out = struct.pack(">I", len(gain_maps))
    for g in gain_maps:
        params = encode_gain_map(g)
        out += struct.pack(">IIII", GAIN_MAP_ID, 0x01030000, 0, len(params)) + params
    return out


def gain_maps_to_plane_shading(
    gain_maps: list[GainMap], image_shape: tuple[int, int], plane_offsets: dict[str, tuple[int, int]]
) -> np.ndarray | None:
    """Convert per-phase GainMaps into an (h, w, 4) map in canonical plane order.

    Each GainMap selecting one Bayer phase (row/col pitch 2) is assigned to the
    plane whose CFA offset matches its (top, left) phase. The map grid is
    resampled so all four planes share one grid (the first map's grid), which is
    what :func:`hie_core.raw.frame.upsample_shading` expects.
    Returns ``None`` when the maps do not describe a per-phase Bayer shading map.
    """
    from .bayer import PLANES

    if not gain_maps:
        return None
    by_phase: dict[tuple[int, int], GainMap] = {}
    for g in gain_maps:
        if g.row_pitch != 2 or g.col_pitch != 2 or g.map_planes != 1:
            return None
        by_phase[(g.top % 2, g.left % 2)] = g
    if len(by_phase) != 4:
        return None
    ref = next(iter(by_phase.values()))
    out = np.empty((ref.map_points_v, ref.map_points_h, 4), dtype=np.float32)
    for i, name in enumerate(PLANES):
        g = by_phase[plane_offsets[name]]
        if g.gains.shape[:2] != ref.gains.shape[:2]:
            return None
        out[..., i] = g.gains[..., 0]
    return out

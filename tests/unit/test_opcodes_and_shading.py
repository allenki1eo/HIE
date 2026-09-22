import numpy as np

from hie_core.raw import upsample_shading
from hie_core.raw.bayer import plane_offsets
from hie_core.raw.opcodes import GainMap, encode_opcode_list, gain_maps_to_plane_shading, parse_opcode_list


def _gm(top, left, value):
    gains = np.full((3, 4, 1), value, np.float32)
    return GainMap(top, left, 100, 100, 0, 1, 2, 2, 3, 4, 0.5, 1 / 3, 0.0, 0.0, 1, gains)


def test_gain_map_roundtrip_and_plane_assignment():
    maps = [_gm(0, 0, 1.0), _gm(0, 1, 2.0), _gm(1, 0, 3.0), _gm(1, 1, 4.0)]
    parsed = parse_opcode_list(encode_opcode_list(maps))
    assert not parsed.unsupported and len(parsed.gain_maps) == 4
    assert np.allclose(parsed.gain_maps[1].gains, 2.0)
    shading = gain_maps_to_plane_shading(parsed.gain_maps, (100, 100), plane_offsets("BGGR"))
    # BGGR: B at (0,0) → value 1, Gb at (0,1) → 2, Gr at (1,0) → 3, R at (1,1) → 4
    assert shading.shape == (3, 4, 4)
    assert np.allclose(shading[0, 0], [4.0, 3.0, 2.0, 1.0])


def test_shading_upsample_is_corner_aligned():
    grid = np.zeros((2, 2, 1), np.float32)
    grid[1, 1, 0] = 1.0
    up = upsample_shading(grid, (5, 5))[..., 0]
    assert up[0, 0] == 0.0 and np.isclose(up[-1, -1], 1.0) and np.isclose(up[2, 2], 0.25)

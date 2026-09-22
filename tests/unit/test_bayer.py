import numpy as np
import pytest

from hie_core.raw.bayer import (
    PLANES, from_planes, pattern_from_cfa_codes, plane_offsets, planes_to_gray, to_planes,
)


@pytest.mark.parametrize("pattern", ["RGGB", "BGGR", "GRBG", "GBRG"])
def test_planes_roundtrip(pattern, rng):
    cfa = rng.random((10, 14)).astype(np.float32)
    assert np.array_equal(from_planes(to_planes(cfa, pattern), pattern), cfa)


@pytest.mark.parametrize("pattern", ["RGGB", "BGGR", "GRBG", "GBRG"])
def test_plane_semantics(pattern):
    """Gr must share its row with R, Gb with B, whatever the CFA phase."""
    offs = plane_offsets(pattern)
    assert offs["Gr"][0] == offs["R"][0]
    assert offs["Gb"][0] == offs["B"][0]
    assert len(set(offs.values())) == 4


def test_cfa_codes():
    assert pattern_from_cfa_codes([2, 1, 1, 0]) == "BGGR"
    assert pattern_from_cfa_codes(b"\x00\x01\x01\x02") == "RGGB"
    with pytest.raises(ValueError):
        pattern_from_cfa_codes([0, 0, 1, 2])


def test_odd_dimensions_are_cropped():
    assert to_planes(np.zeros((7, 9), np.float32), "RGGB").shape == (3, 4, 4)


def test_gray_is_box_average():
    planes = np.stack([np.full((2, 2), v, np.float32) for v in (1, 2, 3, 6)], -1)
    assert np.allclose(planes_to_gray(planes), 3.0)
    assert PLANES == ("R", "Gr", "Gb", "B")

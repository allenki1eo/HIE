"""Frame alignment. Every aligner maps (ref_gray, alt_gray) → :class:`Alignment` with a dense flow."""

from .base import Alignment, identity_flow, warp
from .dense import DISFlowAligner
from .global_methods import FeatureHomographyAligner, PhaseCorrelationAligner
from .tiles import TileAligner, TileAlignParams


class NoAlign:
    """Identity alignment — the ablation baseline that shows what alignment buys."""

    name = "none"

    def __call__(self, ref_gray, alt_gray) -> Alignment:
        return Alignment(identity_flow(ref_gray.shape), self.name)


ALIGNERS = {
    "none": NoAlign,
    "phase_correlation": PhaseCorrelationAligner,
    "feature_homography": FeatureHomographyAligner,
    "hdrplus_tiles": TileAligner,
    "dis_flow": DISFlowAligner,
}


def make_aligner(name: str, **kwargs):
    try:
        return ALIGNERS[name](**kwargs)
    except KeyError as exc:
        raise ValueError(f"Unknown aligner {name!r}; choose from {sorted(ALIGNERS)}") from exc


__all__ = [
    "ALIGNERS", "Alignment", "DISFlowAligner", "FeatureHomographyAligner", "NoAlign",
    "PhaseCorrelationAligner", "TileAligner", "TileAlignParams", "identity_flow", "make_aligner", "warp",
]

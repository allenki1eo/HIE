"""Hanson Image Engine (HIE) — computational photography research engine.

The package is organised by pipeline stage (see ``docs/architecture.md``)::

    raw → noise → alignment → fusion → confidence → demosaic → color →
    tone_mapping → finish

Everything operates on float32 arrays in a *normalised linear* domain where
0 is the black level and 1 is the sensor white level, so noise models from the
DNG ``NoiseProfile`` tag apply directly.
"""

__version__ = "0.1.0"

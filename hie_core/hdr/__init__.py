"""HDR / exposure reconstruction.

v0.1 handles dynamic range with a single exposure: highlight clipping is made
neutral in :func:`hie_core.pipeline.render.clip_highlights_neutral` and shadows are
lifted by synthetic exposure fusion in :mod:`hie_core.tone_mapping`.
Multi-exposure bracketing is planned for v0.4 (see docs/research-plan.md).
"""

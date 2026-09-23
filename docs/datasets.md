# Datasets

| Dataset | Role | Ground truth | Status |
|---|---|---|---|
| Google HDR+ Burst Photography (CC BY-SA) | real bursts from six phone models, plus Google's own merge and final output | none; Google's merge is a *reference system*, not truth | 12 bursts used; see [datasets/google-hdr-plus](../datasets/google-hdr-plus/README.md) |
| Synthetic bursts (`hie_core.datasets.synthetic`) | exact ground truth for merge quality, ghosting and detail | exact | 6 scenes × 2 disjoint splits (`tune`, `test`) |
| Pixel 6 / Camera Lab packages | any Android phone the app runs on (Pixel 6 is the first target); real CaptureResult + gyro | none; compared with the stock JPEG | layout defined; Hanson Camera Lab writes these packages. Validate with `hie package validate` |
| BurstSR (Bhat et al. 2021) | phone bursts with DSLR ground truth, for super-resolution | yes (DSLR) | candidate for v0.5; not downloaded |

## Synthetic burst protocol

1. A band-limited scene in camera-linear RGB: a procedural chart (gradients, multi-scale texture, a Siemens star, text strokes, colour patches, a deep-shadow patch, a near-white patch) or any supplied image. It is rendered at 2× and area-downsampled.
2. Per-frame hand-shake: a Gaussian translation (σ = `shake_px`) plus a small rotation. Frame 0 is the reference.
3. An optional textured disc moving independently across frames. Its footprint, mapped into reference coordinates, forms the **motion mask**.
4. BGGR mosaic, then Poisson shot noise and Gaussian read noise with `S = S0·k`, `O = O0·k²`. Here S0 and O0 come from a real ISO-51 Pixel NoiseProfile.
5. 10-bit quantisation with black level 64, clipping at white.

| Scene | Exposure | Gain k | Shake σ | Other |
|---|---|---|---|---|
| daylight_static | 0.6 | 1 | 1.5 px | |
| indoor_handheld | 0.15 | 8 | 3 px | 0.25° rotation |
| night_handheld | 0.03 | 32 | 3 px | 0.25° rotation; pixel SNR ≈ 0.3 |
| night_motion | 0.03 | 32 | 2 px | moving object |
| daylight_motion | 0.6 | 1 | 1.5 px | fast moving object (18 px/frame) |
| large_shake | 0.3 | 4 | 12 px | 0.6° rotation |

**Leakage rule (brief §29).** The `tune` split uses different noise seeds (1000+) *and* a different chart seed from `test`. Every parameter in `hie_core/pipeline/config.py` was chosen on `tune` only. The same rule applies to any learned component: split by burst or scene, never by frame.

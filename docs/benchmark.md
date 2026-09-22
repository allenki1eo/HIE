# Benchmark: HIE v0.1 baselines

All numbers come from run directories created by `hie bench …`. The tables below are generated from
those runs' JSON files and are copied into [benchmarks/reports/](../benchmarks/reports/). Each run
records its commit in `experiment.json`.

| Run | What | Commit |
|---|---|---|
| `EXP-hdrplus/20260922T184236Z_20171106_subset` | EXP-hdrplus | `4257d78c63` |
| `EXP-synthetic/20260922T184103Z_test` | EXP-synthetic | `4257d78c63` |
| `EXP-alignment-study/20260922T193815Z_test` | EXP-alignment-study | `4257d78c63` |

## Real bursts: Google HDR+ dataset (12 bursts, ISO 50–2056)

Reference frames are HDR+'s own (`reference_frame.txt`), so outputs are comparable with Google's merge.
Means over bursts:

| Method | Noise removed (dB) ↑ | Reference deviation ↓ | Agreement with Google merge (dB) | Runtime (s) |
|---|--:|--:|--:|--:|
| Single frame | 0.00 | 0.00 % | 44.48 | 9.6 |
| Single + denoise | 5.22 | 0.00 % | 47.03 | 12.8 |
| Mean, no align | 8.33 | 22.89 % | 33.31 | 13.8 |
| Mean | 9.40 | 2.53 % | 43.56 | 24.9 |
| Median | 7.52 | 2.59 % | 42.81 | 30.4 |
| Sharpness-weighted | 9.39 | 2.54 % | 43.03 | 26.4 |
| Motion-aware | 9.28 | 0.48 % | 48.89 | 26.9 |
| Optical-flow mean | 10.98 | 2.33 % | 43.30 | 14.6 |
| HDR+ merge (repro.) | 7.67 | 0.03 % | 50.25 | 33.2 |
| Confidence | 9.35 | 0.50 % | 48.15 | 27.7 |
| HIE v0.1 | 14.76 | 0.50 % | 48.49 | 30.8 |

Burst `0127_20161107_171749_524` is excluded from the agreement column: its input frames are
4048×3044 but Google's `merged.dng` is 4048×3036 (cropped), so the grids do not correspond. The other
metrics include all 12 bursts. The interactive crop comparison for this run is published as a private
report (link in the pull request); `hie report` rebuilds it locally.

**How to read it.**
- *Noise removed* is measured in flat regions against the reference frame. It can exceed the ideal
  10·log10(N) for N frames (8.5 dB for 7 frames), because sub-pixel warping also low-passes a little.
- *Reference deviation* counts pixels whose low-passed merge differs from the low-passed reference
  by more than 5σ. It flags ghosts, misalignment blur and lost detail.
- *Agreement with Google merge* is similarity to one production system, **not quality**.
- *Runtime* is single-process Python on a 4-core cloud VM, per 12 MP burst. These are research
  reference numbers, not phone numbers.

## Synthetic bursts: exact ground truth (test split)

| Method | PSNR raw ↑ | PSNR motion region ↑ | Detail retained ↑ | SSIM ↑ | MS-SSIM ↑ | ΔE2000 ↓ |
|---|--:|--:|--:|--:|--:|--:|
| Single frame | 36.73 | 35.11 | 0.977 | 0.5054 | 0.6408 | 13.54 |
| Single + denoise | 39.95 | 37.92 | 0.848 | 0.5576 | 0.6742 | 12.27 |
| Mean, no align | 33.82 | 27.30 | 0.349 | 0.5603 | 0.6632 | 11.29 |
| Mean | 41.45 | 30.28 | 0.840 | 0.6260 | 0.7272 | 10.02 |
| Median | 40.61 | 29.52 | 0.853 | 0.6133 | 0.7163 | 10.69 |
| Sharpness-weighted | 41.44 | 30.25 | 0.840 | 0.6260 | 0.7271 | 10.02 |
| Motion-aware | 44.62 | 41.30 | 0.862 | 0.6282 | 0.7283 | 9.95 |
| Optical-flow mean | 41.42 | 31.85 | 0.824 | 0.6322 | 0.7281 | 9.77 |
| HDR+ merge (repro.) | 43.31 | 39.53 | 0.868 | 0.6111 | 0.7172 | 10.55 |
| Confidence | 44.62 | 41.79 | 0.863 | 0.6284 | 0.7284 | 9.94 |
| HIE v0.1 | 46.95 | 44.04 | 0.811 | 0.6601 | 0.7604 | 7.81 |

Per-scene PSNR (raw, dB) and detail retention:

| Method | daylight_static | indoor_handheld | night_handheld | night_motion | daylight_motion | large_shake |
|---|--:|--:|--:|--:|--:|--:|
| Single frame | 44.49 / 1.00 | 37.12 / 1.00 | 27.07 / 0.94 | 27.10 / 0.92 | 44.52 / 1.00 | 40.05 / 1.00 |
| Single + denoise | 46.46 / 0.99 | 40.73 / 0.94 | 31.54 / 0.60 | 31.59 / 0.58 | 46.43 / 1.00 | 42.96 / 0.98 |
| Mean, no align | 33.09 / 0.61 | 38.51 / 0.16 | 36.02 / 0.17 | 36.02 / 0.29 | 30.84 / 0.73 | 28.45 / 0.14 |
| Mean | 44.71 / 0.94 | 46.23 / 0.94 | 36.30 / 0.64 | 36.40 / 0.63 | 37.67 / 0.95 | 47.39 / 0.94 |
| Median | 44.52 / 0.96 | 45.07 / 0.94 | 34.79 / 0.65 | 34.92 / 0.65 | 37.55 / 0.96 | 46.79 / 0.95 |
| Sharpness-weighted | 44.67 / 0.94 | 46.23 / 0.94 | 36.30 / 0.64 | 36.40 / 0.63 | 37.62 / 0.95 | 47.38 / 0.94 |
| Motion-aware | 50.22 / 0.99 | 46.23 / 0.95 | 36.29 / 0.65 | 36.39 / 0.63 | 50.22 / 0.99 | 48.33 / 0.97 |
| Optical-flow mean | 42.87 / 0.92 | 46.36 / 0.91 | 37.10 / 0.64 | 37.11 / 0.63 | 38.70 / 0.92 | 46.36 / 0.92 |
| HDR+ merge (repro.) | 49.11 / 0.99 | 44.76 / 0.94 | 35.12 / 0.67 | 35.15 / 0.65 | 48.95 / 0.99 | 46.80 / 0.97 |
| Confidence | 50.23 / 1.00 | 46.25 / 0.94 | 36.30 / 0.64 | 36.40 / 0.63 | 50.29 / 1.00 | 48.28 / 0.97 |
| HIE v0.1 | 50.81 / 1.00 | 48.88 / 0.92 | 40.73 / 0.50 | 40.86 / 0.49 | 50.84 / 1.00 | 49.58 / 0.96 |

Cells: PSNR (dB) / detail retained.

## Findings

1. **Alignment is non-negotiable.** Without it, mean fusion deviates from the reference on 22.9 % of
   pixels on real bursts. It keeps only 0.14–0.29 of the detail on synthetic handheld scenes.
2. **Robust weighting matters more than the choice of aligner.** Tile, flow and median merges all
   deviate on about 2.3–2.6 % of real pixels. Confidence and motion-aware weighting bring this to about
   0.5 %, and the HDR+ Wiener reproduction to 0.03 %. On synthetic moving objects, confidence fusion
   holds 47.3 dB in the motion region, against 24.3 dB for mean fusion.
3. **In daylight, plain averaging barely helps** (44.7 vs 44.5 dB single frame). Residual
   misalignment dominates when noise is low. Confidence weighting reaches 50.2 dB.
4. **The median is never the best merge.** It is always noisier than the mean (expected efficiency
   2/π) and no more robust than proper confidence weighting.
5. **HDR+ trade-off reproduced.** The frequency-domain Wiener merge is the most faithful to the
   reference (lowest deviation, closest to Google's merge at 50.3 dB) but removes about 1.7 dB less
   noise than confidence fusion. Our independent tuning sweep chose the same robustness factor
   (k = 8) that the HDR+ paper reports.
6. **HIE v0.1's spatial denoising is the largest single gain.** It adds about 5.4 dB of noise removal on
   real bursts and 2.3 dB PSNR on synthetic scenes, at no extra deviation. At night it costs detail:
   retention falls from 0.645 to 0.500. This is a real trade-off, not a free win.
7. **Under identical finishing, HIE's merge is as sharp as Google's merge.** Google's `final.jpg` looks
   crisper and more saturated because of its finishing (sharpening, contrast, colour), not its merge.

## Failure analysis

**F1. Alignment collapses at very low SNR.** This is the dominant failure. On the synthetic night scene
(pixel SNR ≈ 0.3), all estimated alignments leave a large detail gap to oracle alignment with the
*same* merge:

| Alignment (mean fusion) | Median flow error (px) | PSNR (dB) | Detail retained |
|---|--:|--:|--:|
| tiles (noise-aware) | 1.35 | 36.30 | 0.645 |
| tiles (no noise model) | 3.89 | 37.08 | 0.596 |
| tiles, nearest warp | 1.35 | 36.05 | 0.612 |
| DIS optical flow | 2.24 | 37.10 | 0.643 |
| phase correlation | 0.81 | 36.95 | 0.698 |
| oracle, cubic warp | 0.00 | 37.32 | 0.882 |
| oracle, bilinear warp | 0.00 | 39.12 | 0.746 |
| oracle, nearest warp | 0.00 | 36.10 | 0.833 |
| no alignment | 1.84 | 36.02 | 0.172 |

With perfect alignment the same merge keeps 0.882 of the detail. The default tiles keep 0.645,
and *global* phase correlation, at 0.698, beats every local method here, because at this SNR a
whole-frame model averages over far more pixels than a 16-pixel tile. Global models fail on the
large-rotation scene, though: phase correlation keeps 0.508 of detail there, against 0.940 for tiles
(full per-scene tables in [benchmarks/reports/v0.1/tables.md](../benchmarks/reports/v0.1/tables.md)).
Neither purely local nor purely global alignment is right, which is the motivation for H1.

Diagnosis: the finer pyramid levels lock onto noise minima. Three fixes help and are now defaults.
They are carrying sub-pixel displacement between levels (which HDR+ also does at coarse scales),
five ×2 pyramid steps instead of ×4 jumps, and a noise-aware acceptance test. They raised night detail
retention from about 0.45 to about 0.62–0.65 in the tuning split. Without the noise model, the
same tiles reach 0.596 on the test split. The remaining gap is the gap H1 targets.

**F2. PSNR rewards blur.** Bilinear warping gives the *highest* PSNR under oracle alignment but the
lowest detail retention. Warp interpolation low-passes noise, and PSNR counts that as a win. HIE
therefore reports detail retention next to PSNR and uses cubic warping.

**F3. Moving foliage.** Burst 0155 (wind-blown leaves, ISO 50) keeps the highest residual deviation even
after confidence weighting (3.5 %). Many small, non-rigid motions defeat 16-pixel tiles. Robust
weighting falls back to the reference in those areas, so the merge is locally no better than one frame.

**F4. Low-frequency noise at very high ISO.** At ISO 2056 the merged sky shows blotchy low-frequency
luminance noise, in HIE and in Google's merge alike. HDR+ switches to 32×32 tiles for very dark scenes.
HIE v0.1 does not do that yet.

## Negative results (kept on purpose)

- **Noise-aware acceptance alone did not help detail.** With the original ×4 pyramid steps it
  lowered flow error but *reduced* night detail, because the prior it protected was itself wrong. It
  only helped once sub-pixel displacements were carried between levels.
- **Median-filtering the tile flow field** lowered flow error but cost motion-region PSNR (about −1.6 dB on
  daylight_motion) and night detail. It is off by default.
- **Larger tiles (32 px) at the finest level** and **Gaussian pre-filtering** of the alignment image did
  not close the night gap on their own.
- **The single-image noise estimator** underestimates the profile on some bursts (up to about 40 %
  against the DNG NoiseProfile at ISO 755). The DNG profile is preferred whenever present.

## Reproducibility check

The real-data suite was run twice, from commits `169e94f` and `4257d78`, which differ only in crop
selection. All quality metrics were identical to four decimals for all 11 methods; only runtimes differed
(by under 5 %). The first run's `experiment.json` recorded the commit at write time rather than at start,
a provenance bug that is now fixed: records capture the commit when a run starts (`git_captured_at`).
The three runs cited above started at `807290c` (synthetic) and `4257d78` (real-data and alignment study).
`807290c` and `4257d78` differ only in report crop selection, which the synthetic suite does not use, so
`4257d78` describes the code that produced every number here.

## Validation of the implementation

- CIEDE2000 reproduces the published Sharma et al. test pairs to 4 decimals.
- The DNG-derived colour matrix is close to Google's `rgb2rgb.txt` (max element difference 0.15, with
  Google's more saturated).
- The GainMap opcode parser reproduces the sidecar lens-shading peak gain (4.397) on `merged.dng`.
- The tile machinery reconstructs its input exactly (max error 1e-7), and the raised-cosine window sums to 1.
- The estimated noise models agree with DNG NoiseProfiles within about 10–25 % on most bursts.

## Not yet measured

LPIPS and DISTS, phone-side latency and power and thermal behaviour, semantic crops (faces, text),
and the IPOL HDR+ implementation as an independent cross-check of `hdrplus_wiener`.

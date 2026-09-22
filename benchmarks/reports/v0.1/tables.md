## REAL

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

## SYNTH

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

## SYNTHSCENE

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

## ALIGN

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

## ALIGN_ALL

**daylight_static**

| Alignment (mean fusion) | Median flow error (px) | PSNR (dB) | Detail retained |
|---|--:|--:|--:|
| tiles (noise-aware) | 0.29 | 44.71 | 0.944 |
| tiles (no noise model) | 0.50 | 44.71 | 0.944 |
| tiles, nearest warp | 0.29 | 42.11 | 0.912 |
| DIS optical flow | 0.27 | 42.87 | 0.920 |
| phase correlation | 0.26 | 38.54 | 0.870 |
| oracle, cubic warp | 0.00 | 43.54 | 0.919 |
| oracle, bilinear warp | 0.00 | 40.22 | 0.775 |
| oracle, nearest warp | 0.00 | 41.12 | 0.872 |
| no alignment | 0.81 | 33.09 | 0.613 |

**indoor_handheld**

| Alignment (mean fusion) | Median flow error (px) | PSNR (dB) | Detail retained |
|---|--:|--:|--:|
| tiles (noise-aware) | 0.46 | 46.23 | 0.940 |
| tiles (no noise model) | 0.68 | 46.62 | 0.942 |
| tiles, nearest warp | 0.46 | 45.48 | 0.911 |
| DIS optical flow | 0.52 | 46.36 | 0.910 |
| phase correlation | 0.54 | 45.99 | 0.872 |
| oracle, cubic warp | 0.00 | 46.82 | 0.934 |
| oracle, bilinear warp | 0.00 | 47.63 | 0.803 |
| oracle, nearest warp | 0.00 | 45.37 | 0.901 |
| no alignment | 1.77 | 38.51 | 0.159 |

**night_handheld**

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

**large_shake**

| Alignment (mean fusion) | Median flow error (px) | PSNR (dB) | Detail retained |
|---|--:|--:|--:|
| tiles (noise-aware) | 0.35 | 47.39 | 0.940 |
| tiles (no noise model) | 0.53 | 47.53 | 0.941 |
| tiles, nearest warp | 0.35 | 45.69 | 0.909 |
| DIS optical flow | 0.36 | 46.36 | 0.919 |
| phase correlation | 2.11 | 33.31 | 0.508 |
| oracle, cubic warp | 0.00 | 47.44 | 0.930 |
| oracle, bilinear warp | 0.00 | 45.72 | 0.791 |
| oracle, nearest warp | 0.00 | 44.89 | 0.883 |
| no alignment | 7.33 | 28.45 | 0.138 |

## RUNS

| Run | What | Commit |
|---|---|---|
| `EXP-hdrplus/20260922T184236Z_20171106_subset` | EXP-hdrplus | `4257d78c63` |
| `EXP-synthetic/20260922T184103Z_test` | EXP-synthetic | `4257d78c63` |
| `EXP-alignment-study/20260922T193815Z_test` | EXP-alignment-study | `4257d78c63` |
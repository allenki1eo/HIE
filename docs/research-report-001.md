# Research report 001: approval gate

**Status: waiting for human approval.** Per brief §39 task 12, no allegedly novel algorithm will be
implemented until the owner approves a direction below.

## 1. What was built and measured

HIE v0.1 reproduces the established burst pipeline and ten baselines. Each was measured on 12 real
Google HDR+ bursts (ISO 50–2056, four device generations) and on 6 synthetic scenes with exact
ground truth. The numbers are in [benchmark.md](benchmark.md) and the visual comparison is in the HTML report.

## 2. Literature findings (summary)

Full detail is in [literature-review.md](literature-review.md) and [prior-art.md](prior-art.md).

- **HDR+ (2016)** already provides the full classical pipeline: constant-exposure raw bursts, pyramid tile
  alignment, frequency-domain robust merge, noise-model-driven spatial denoising and synthetic exposure fusion.
- **Night Sight (2019)** already adapts capture to motion (motion metering with optical flow, future-motion
  prediction and gyro), uses per-tile mismatch maps, and raises spatial denoising where merging was limited.
- **Super Res Zoom (2019)** already uses a per-pixel robustness mask, increases denoising in inverse
  proportion to merged frames, and does 2× multi-frame SR.
- A patent (US 9,313,420) describes incrementally adding frames to maximise summed SNR.

**Consequence:** research directions #1 (adaptive capture), #3 (pixel confidence), #5 (gyro, partly)
and #7 (SR) are not novel as stated in the brief. HIE v0.1 itself contains nothing new: its tuned
parameters and its N_eff-aware denoising re-derive published choices.

## 3. Identified gap (measured, not assumed)

**F1: burst alignment collapses at very low SNR, and it is the bottleneck.** On synthetic night scenes
(pixel SNR ≈ 0.3) the same mean fusion keeps:

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

With perfect (oracle) alignment, the same merge keeps 0.882 of the detail. The best estimated method
keeps 0.698, and it is *global* phase correlation, which then fails on large rotations (0.508 against
0.940 for tiles on the large-shake scene).

The merge is not the limit. The loss comes from per-frame, per-tile alignment against a *single noisy reference frame*.
Night Sight reports "slight modifications to improve performance in low light" without details, so
the published record does not say how production systems handle this.

## 4. Hypothesis (H1)

> At low SNR, aligning every frame to an *intermediate merged estimate* instead of the noisy reference
> frame, and fusing each tile's local match with a burst-level camera-motion model in proportion to
> how informative that match is, recovers a substantial part of the oracle-alignment detail. It does
> this without increasing ghosting in moving regions.

## 5. Proposed algorithm (provisional name: uncertainty-weighted iterative burst alignment)

1. **Initial merge.** `M⁰ = confidence_fusion(align(frames → reference))`, with per-pixel `N_eff⁰`.
2. **Re-align to the merge.** For frame z and tile t, minimise the noise-normalised cost against `Mᵏ`
   instead of the reference:
   `C_zt(d) = Σ_x (Mᵏ(x) − I_z(x + d))² / (σ²_z(x) + σ²(x)/N_effᵏ(x))`.
   To avoid the reference frame's own noise biasing the match, frame z is excluded from `Mᵏ`
   (leave-one-out merge) when it contributed.
3. **Information-weighted motion prior.** Fit a per-frame global motion model `g_z` (homography, or a
   gyro-predicted rotation on Pixel 6) to all tiles by weighted least squares, with weights `H_zt`
   (the local curvature, i.e. the Fisher information of `C_zt` at its minimum). Combine the local and
   global estimates:
   `d_zt = (H_zt + Λ)⁻¹ (H_zt d̂_zt + Λ g_z(t))`,
   where Λ is the prior precision. Informative tiles keep their own motion (parallax, moving objects);
   uninformative tiles follow the camera.
4. **Re-merge** with the existing confidence fusion. Repeat steps 2–4 K times (K = 1–2) or until
   the median |Δd| is below 0.05 px.

**Closest prior art that must be searched before any claim:** iterative "align-to-mean" registration
in multi-frame super-resolution and astronomy stacking; Bayesian / variational flow with global
priors; gyro-regularised alignment in industry patents; Lucas-Kanade Reloaded (joint learned alignment).
**The combination may well exist.** H1 is proposed as an experiment, not as a contribution.

## 6. Experiment design

| Item | Plan |
|---|---|
| Baselines | current tiles, DIS flow, phase correlation, oracle alignment (upper bound), HDR+ merge reproduction |
| Ablations | (a) re-align to merge only · (b) motion prior only · (c) both · K ∈ {1, 2} · leave-one-out on/off |
| Synthetic | test split plus new scenes at exposures 0.02–0.06 with moving objects. Primary metric: detail retention on the static region. Guard: motion-region PSNR |
| Real | the four HDR+ bursts at ISO ≥ 755, plus Pixel 6 night bursts once the capture app exists. Metrics: residual noise, reference deviation, visual crops |
| Success | close ≥ 50 % of the night detail gap between current tiles and oracle; ≤ 0.1 dB loss on daylight and motion scenes; reference deviation not increased |
| Tuning | tune split only; one run per commit |

## 7. Risks

- **Self-confirmation**: aligning to a merge that already contains misaligned content can lock errors
  in. Leave-one-out and K ≤ 2 mitigate this, and the oracle upper bound will show it.
- **Motion regions**: the global prior can drag a moving object's tiles toward camera motion. The
  Fisher weighting should prevent this, and the motion-region PSNR guard will catch it.
- **Runtime**: each iteration costs roughly one more align plus merge (~2× total). That is acceptable for
  research and needs a budget on phone.
- **Novelty**: likely low. The value may be an honest empirical result on public data rather than a new method.

## 8. Alternatives for the owner to choose from

1. **H1 (above)**: grounded in HIE's own measured failure F1.
2. **Finishing quality (not research, but product-visible).** HIE's merge already matches Google's
   merge in sharpness under identical finishing, while Google's `final.jpg` looks crisper and more
   saturated. Closing that gap is ISP tuning (sharpening, local contrast, colour), which is valuable
   for "better images" but not a research contribution.
3. **Night low-frequency noise (F4)**: larger tiles and noise shaping for very dark scenes. HDR+
   already uses 32×32 tiles there, so this is engineering, not research.
4. **Pixel 6 capture first (milestone 2)**: build Hanson Camera Lab and measure gyro–frame sync error,
   which is needed before gyro-based ideas can be tested at all.

**Recommendation:** approve H1 as a bounded experiment, run in parallel with milestone 2
(Pixel 6 capture). If H1 fails the success criterion, record it as a negative result.

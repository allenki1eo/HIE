# Prior-art matrix

Cells are filled **only** from sources checked in [literature-review.md](literature-review.md).
`✓` = described in the source · `✗` = explicitly absent / not applicable · `~` = partial (see note) · `?` = not verified yet.

| Paper / system | RAW | Burst | Alignment | Motion handling | Uncertainty / confidence | Adaptive capture | Gyro | Semantic | Super-resolution |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| HDR+ (Hasinoff 2016) | ✓ | ✓ | ✓ tile pyramid | ✓ robust Wiener merge | ~ noise model drives shrinkage; no confidence output | ~ auto-exposure picks under-exposure, compression and frame count; not motion-driven | ? not described | ? | ✗ pixel-level only |
| HDR+ with Bracketing (blog 2021) | ✓ | ✓ | ? | ? | ? | ✓ exposures chosen from dynamic range and motion | ? | ? | ? |
| Night Sight (Liba 2019) | ✓ | ✓ | ✓ HDR+-derived | ✓ mismatch maps, spatially varying merge | ✓ per-tile mismatch → per-tile noise variance → spatial denoise | ✓ motion metering (flow + future-motion model) picks exposure/gain; frame count from time budget | ✓ stability for metering | ? | ~ uses Super Res Zoom merge on some devices (per Wronski 2019) |
| Super Res Zoom (Wronski 2019) | ✓ CFA → RGB | ✓ | ✓ | ✓ robustness + motion prior | ✓ per-pixel robustness mask; denoise ∝ 1/merged frames | ✗ | ~ gyro used to *analyse* hand tremor, not to align | ✗ | ✓ up to 2× |
| Deep Burst SR (Bhat 2021) | ✓ | ✓ | ✓ learned flow | ~ attention fusion | ~ implicit attention weights | ✗ | ✗ | ✗ | ✓ |
| KPN burst denoising (Mildenhall 2018) | ✓ (synthetic raw) | ✓ | ~ implicit in predicted kernels | ~ implicit | ✗ | ✗ | ✗ | ✗ | ✗ |
| Noise-optimal capture (Hasinoff 2010) | ✓ | ✓ | ✗ static scenes | ✗ | ✓ SNR model | ✓ optimal exposure/ISO sequence by mixed-integer programming | ✗ | ✗ | ✗ |
| US 9,313,420 (patent) | ? | ✓ | ✓ | ? | ~ SNR estimates | ✓ incrementally adds frames to maximise summed SNR | ? | ? | ? |
| Gyro stabilisation (Karpenko 2011) | ✗ video | ✓ video | ✓ gyro-driven | ✗ | ✗ | ✗ | ✓ with automatic sync calibration | ✗ | ✗ |
| **HIE v0.1 (this repo)** | ✓ | ✓ | ✓ tiles / flow / global | ✓ confidence + motion-aware | ✓ per-pixel N_eff map output | ✗ not yet | ✗ not yet | ✗ | ✗ |

## What this means for the brief's research directions

| Direction | Closest prior art | Assessment today |
|---|---|---|
| #1 Adaptive capture & reconstruction (HACR) | Night Sight motion metering; HDR+ with Bracketing; Hasinoff 2010 | **Not novel as stated.** Choosing frame count and exposure from motion and light is shipped and published. A narrower gap may exist in planning capture against the *specific merge's* measured robustness behaviour, but that needs the patent claims read first. |
| #2 Adaptive burst termination | US 9,313,420 (incremental frames to maximise SNR); Night Sight time budget | **Partially covered.** Stopping on the *reconstruction's* per-pixel uncertainty, including motion rejection, was not found yet. Claims of US 9,313,420 and related patents must be read in full before any claim. |
| #3 Pixel / region confidence | Super Res Zoom robustness mask; Night Sight mismatch maps | **Covered.** Only a *calibrated*, predictive per-pixel σ that is evaluated for calibration might differ. Calibration literature has not been searched yet. |
| #4 Sensor-aware reconstruction | Brooks 2019 (noise-model-aware training); KPN (noise level as input) | **Largely covered for noise.** Conditioning on lens, temperature or motion state was not searched yet. |
| #5 Gyro-assisted alignment | Karpenko 2011; Night Sight (gyro for metering) | **Unclear.** Gyro-initialised *burst* alignment in industry is likely but unverified. Measuring sync error on Pixel 6 is still worth doing as an experiment. |
| #6 Semantic / region-aware ISP | not searched in this pass | **Unknown.** |
| #7 Multi-frame SR | Super Res Zoom, Deep Burst SR, IPOL 2023 | **Covered.** Reproduction is the right first step. |

HIE v0.1 re-derives several established ideas, and none of them is claimed as new:

- **Wiener factor**: the Wiener robustness factor of 8, found by our sweep, matches HDR+'s.
- **Sub-pixel propagation**: carrying sub-pixel alignment across coarse pyramid levels follows HDR+'s coarse-scale design.
- **N_eff-aware denoising**: this spatial denoising matches Night Sight and Super Res Zoom.

## Search log

| Date | Sources | Queries (abridged) | Outcome |
|---|---|---|---|
| 2026-09-22 | HDR+ PDF, arXiv, ACM DL, CVF, IPOL, Google Research blog | HDR+ merge/alignment details; Night Sight motion metering; Super Res Zoom robustness; HDR+ bracketing; Monod IPOL; Lafenetre IPOL; Deep Burst SR; KPN; Unprocessing; PyNET; Karpenko gyro | entries above |
| 2026-09-22 | Web, Google Patents / USPTO (full text blocked: 403/503) | adaptive burst termination; "capture additional frame based on noise of merged image" | US 9,313,420; US 9,087,391 (abstract level only) |
| **Not yet done** | IEEE Xplore, WIPO, EPO, Google Scholar citation chasing | semantic ISP; uncertainty calibration in burst denoising; gyro-initialised burst alignment; adaptive burst length | required before the approval-gate decision |

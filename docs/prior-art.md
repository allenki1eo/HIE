# Prior-art matrix

Cells are filled **only** from sources checked in [literature-review.md](literature-review.md).
`✓` = described in the source · `✗` = explicitly absent / not applicable · `~` = partial (see note) · `?` = not verified yet.

| Paper / system | RAW | Burst | Alignment | Motion handling | Uncertainty / confidence | Adaptive capture | Gyro | Semantic | Super-resolution |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| HDR+ (Hasinoff 2016) | ✓ | ✓ | ✓ tile pyramid | ✓ robust Wiener merge | ~ noise model drives shrinkage; no confidence output | ~ auto-exposure picks under-exposure, compression and frame count; not motion-driven | ? not described | ? | ✗ pixel-level only |
| HDR+ with Bracketing (blog 2021) | ✓ | ✓ | ? | ? | ? | ✓ exposures chosen from dynamic range and motion | ? | ? | ? |
| Night Sight (Liba 2019) | ✓ | ✓ | ✓ HDR+-derived | ✓ mismatch maps, spatially varying merge | ✓ per-tile mismatch → per-tile noise variance → spatial denoise | ✓ motion metering (flow + future-motion model) picks exposure/gain; frame count from time budget | ✓ stability for metering | ? | ~ uses Super Res Zoom merge on some devices (per Wronski 2019) |
| Super Res Zoom (Wronski 2019) | ✓ CFA → RGB | ✓ | ✓ | ✓ robustness + motion prior | ✓ per-pixel robustness mask; denoise ∝ 1/merged frames | ✗ | ~ gyro used to analyse hand tremor, not to align | ✗ | ✓ up to 2× |
| Deep Burst SR (Bhat 2021) | ✓ | ✓ | ✓ learned flow | ~ attention fusion | ~ implicit attention weights | ✗ | ✗ | ✗ | ✓ |
| KPN burst denoising (Mildenhall 2018) | ✓ (synthetic raw) | ✓ | ~ implicit in predicted kernels | ~ implicit | ✗ | ✗ | ✗ | ✗ | ✗ |
| Noise-optimal capture (Hasinoff 2010) | ✓ | ✓ | ✗ static scenes | ✗ | ✓ SNR model | ✓ optimal exposure/ISO sequence by mixed-integer programming | ✗ | ✗ | ✗ |
| US 9,313,420 (patent) | ✓ Bayer (description) | ✓ | ✓ 3-D rotation on raw | ~ ML merge | ~ SNR of captured pixels | ✓ incremental frames to max summed SNR | ✗ | ✗ | ✗ |
| US 9,087,391 (patent) | ? | ✓ | ? | ? | ✗ | ✓ metering TETs → long/short sequence (L-S-L) | ✗ | ✗ | ✗ |
| Gyro stabilisation (Karpenko 2011) | ✗ video | ✓ video | ✓ gyro-driven | ✗ | ✗ | ✗ | ✓ with automatic sync calibration | ✗ | ✗ |
| Zhang and Stevenson 2018 | ✓ Bayer | ✓ | ✓ gyro homography + UKF + pyramid | ~ Wiener merge | ✗ | ✗ | ✓ initialises homography | ✗ | ✗ |
| GyroFlow (Li 2021) | ✗ RGB video | ✓ video | ✓ gyro field + learned flow | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| DeepISP (Schwartz 2019) | ✓ | ✗ single | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ global quadratic colour | ✗ |
| Sky Optimization (Liba 2020) | ~ RGB in camera pipeline | ✗ finishing | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ sky mask → WB / tone / denoise | ✗ |
| Apple panoptic Camera page | ? | ? | ? | ? | ? | ? | ? | ✓ person/skin/sky for HDR / styles | ? |
| QUTCC (2025) | ✗ inverse problems | ✗ | ✗ | ✗ | ✓ conformal pixel intervals | ✗ | ✗ | ✗ | ✗ |
| **HIE v0.1 + Camera Lab** | ✓ | ✓ | ✓ tiles / flow / global | ✓ confidence + motion-aware | ✓ per-pixel N_eff map output | ~ published-style frame count from TET; no incremental SNR loop | ~ logs gyro; does not align with it | ✗ | ✗ |

## What this means for the brief's research directions

| Direction | Closest prior art | Assessment today |
|---|---|---|
| #1 Adaptive capture and reconstruction (HACR) | Night Sight motion metering; HDR+ with Bracketing; Hasinoff 2010; US 9,087,391 (metering TET sequence) | **Not novel as stated.** Choosing frame count and exposure from motion and light is shipped and patented. A narrower untested question is planning capture against this merge's measured robustness; that is an experiment, not a claim. |
| #2 Adaptive burst termination | US 9,313,420 claim 16 (incremental frames to maximise summed pixel SNR of the sample); Night Sight time budget | **Mostly covered.** Stopping on the reconstruction's per-pixel uncertainty after motion rejection was still not found. Do not implement an incremental SNR loop without treating it as a reproduction of US 9,313,420. |
| #3 Pixel / region confidence | Super Res Zoom robustness mask; Night Sight mismatch maps | **Covered** as a merge weight. A calibrated predictive per-pixel sigma (coverage / ECE on held-out bursts) was not found; QUTCC is conformal calibration but not on raw bursts. Possible experiment, not a claim. |
| #4 Sensor-aware reconstruction | Brooks 2019 (noise-model-aware training); KPN (noise level as input) | **Largely covered for noise.** Conditioning on lens, temperature or motion state was not searched yet. |
| #5 Gyro-assisted alignment | Zhang and Stevenson 2018 (gyro homography + UKF + pyramid on raw bursts); Karpenko 2011 (sync); GyroFlow; DeepOIS (abstract); Night Sight (gyro for metering) | **Covered as a method.** Gyro-initialised burst alignment is published. What remains is an experiment: measure Camera2-gyro sync error on Pixel 6 and other phones, which Camera Lab now records. |
| #6 Semantic / region-aware ISP | Sky Optimization (Liba 2020); Apple panoptic Camera page; DeepISP (global, not semantic); PyNET | **Covered for finishing** (sky, person, skin). Using a semantic mask to change temporal merge (class-dependent N_eff) was not found in the opened sources. Night Sight mismatch is motion, not class. |
| #7 Multi-frame SR | Super Res Zoom, Deep Burst SR, IPOL 2023 | **Covered.** Reproduction is the right first step. |

HIE v0.1 re-derives several established ideas, and none of them is claimed as new:

- **Wiener factor**: the Wiener robustness factor of 8, found by our sweep, matches HDR+'s.
- **Sub-pixel propagation**: carrying sub-pixel alignment across coarse pyramid levels follows HDR+'s coarse-scale design.
- **N_eff-aware denoising**: this spatial denoising matches Night Sight and Super Res Zoom.

Hanson Camera Lab's on-device burst policy (more constant-exposure frames when TET is high, cap 15) is a **reproduction** of the published HDR+ / Night Sight time-budget idea. It does not implement US 9,313,420's incremental SNR loop, US 9,087,391's bracketed TET sequence, or Zhang and Stevenson gyro alignment.

## Search log

| Date | Sources | Queries (abridged) | Outcome |
|---|---|---|---|
| 2026-09-22 | HDR+ PDF, arXiv, ACM DL, CVF, IPOL, Google Research blog | HDR+ merge/alignment details; Night Sight motion metering; Super Res Zoom robustness; HDR+ bracketing; Monod IPOL; Lafenetre IPOL; Deep Burst SR; KPN; Unprocessing; PyNET; Karpenko gyro | entries above |
| 2026-09-22 | Web, Google Patents / USPTO (full text blocked: 403/503) | adaptive burst termination; "capture additional frame based on noise of merged image" | US 9,313,420; US 9,087,391 (abstract level only; claims opened 2026-09-23) |
| 2026-09-23 | Google Patents US9313420B2 (full page, claims 10-21 + description) | US 9,313,420 claims | claim 16 incrementally increases frame count to maximise summed per-pixel SNR of the captured sample; alignment is 3-D rotation on raw Bayer; ML merge. Direction #2 covered for SNR-of-sample termination. |
| 2026-09-23 | Google Patents US9087391B2 (description); patents-review claim dump for 9,087,391; claims dump for US 8,866,927 | payload burst structure / metering sweep | metering TETs → long/short TET + sequence (incl. L-S-L); LDR ⇒ constant TET. Direction #1 covered. |
| 2026-09-23 | arXiv:1811.02013 (full text); IEEE Xplore 8451134 (bibliographic hit; HTML captcha) | gyro / inertia burst alignment | Zhang and Stevenson: gyro rotation + SURF translation → UKF homography → pyramid + Wiener on Bayer. Direction #5 covered. |
| 2026-09-23 | CVF GyroFlow PDF; IEEE Xplore 9509028 abstract (DeepOIS); IEEE 6831799 abstract only | gyro + flow / OIS / stacking | GyroFlow and DeepOIS use gyro fields; 6831799 abstract is gyro+features then stack. Full IEEE HTML blocked. |
| 2026-09-23 | WIPO PATENTSCOPE WO2024107273, WO2021138870 (abstracts) | orientation / multi-frame NR | orientation used for frame selection, not tile-align init. |
| 2026-09-23 | Espacenet home + advanced search UI | EPO gyro burst alignment | **Incomplete:** pages are JS shells; no document list was returned. |
| 2026-09-23 | arXiv:2006.10172 Sky Optimization; arXiv:1801.06724 DeepISP HTML; Apple ML panoptic Camera page | semantic ISP | sky / person / skin finishing is published and shipped. Semantic merge not found. |
| 2026-09-23 | arXiv:2507.14760 QUTCC HTML; KPN / Unprocessing already on file | uncertainty calibration burst denoising | conformal pixel intervals exist off-domain; no opened paper calibrates burst-merge N_eff. |

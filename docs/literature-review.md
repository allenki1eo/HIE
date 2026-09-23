# Literature review

Status legend for each entry:

- **Verified** — details below were checked against the primary source (paper PDF, publisher or arXiv page) during this review.
- **Cited** — a standard method reference used by HIE code; bibliographic details are from the standard citation and were not re-fetched in this pass.

Searches in this pass used the web (arXiv, ACM DL, CVF Open Access, IPOL, Google Research, Google Patents / USPTO). A second pass (2026-09-23) opened Google Patents for US 9,313,420 and US 9,087,391, IEEE Xplore bibliographic pages, WIPO PATENTSCOPE abstracts, and papers on gyro-initialised burst alignment, semantic ISP and uncertainty calibration. EPO Espacenet returned only the search UI (JavaScript), so EPO full-text remains open. IEEE Xplore HTML full texts were blocked by a captcha; those entries use the arXiv or abstract text that was actually opened. The log is in [prior-art.md](prior-art.md#search-log).

---

## Systems (smartphone burst pipelines)

### HDR+ — burst photography for HDR and low light  · Verified
- **Authors:** S. W. Hasinoff, D. Sharlet, R. Geiss, A. Adams, J. T. Barron, F. Kainz, J. Chen, M. Levoy
- **Venue:** ACM TOG 35(6), SIGGRAPH Asia 2016 · DOI [10.1145/2980179.2980254](https://doi.org/10.1145/2980179.2980254) · [PDF](https://www.hdrplusdata.org/hdrplus.pdf)
- **Problem:** noise and dynamic range of small sensors, fast enough for phones.
- **Input:** 2–8 raw frames at one *constant, deliberately short* exposure (constant exposure keeps alignment simple).
- **Method (as stated in the paper):**
  - Reference = sharpest of the **first 3** frames (green-channel gradient metric; "lucky imaging").
  - Alignment on 2×2-averaged Bayer gray, **four-level Gaussian pyramid**, tile matching with inherited offsets; upsampling tests **3 candidates** (nearest coarse tile + next-nearest in each dimension) by L1 residual. Coarse scales: **sub-pixel, L2, large search radius** (L2 via FFT cross-correlation, sub-pixel by a bivariate quadratic fit on the 3×3 cost patch). Finest scale: **pixel-level, L1, small radius**. Tile size n = 8 or 16. Displacements only in multiples of 2 Bayer pixels.
  - Merge: pairwise temporal filter in the 2-D DFT of each tile, per Bayer plane: `T̃0 = 1/N Σ [Tz + Az (T0 − Tz)]`, `Az = |Dz|² / (|Dz|² + c σ²)` (Eq. 6–7). `c` folds in n² (DFT), 1/4² (window), 2 (difference) and a **tuning factor fixed to 8**. Tiles **16×16**, **32×32 for very dark scenes**; half-overlapping, modified raised-cosine window `½ − ½cos(2π(x+½)/n)`.
  - Spatial denoising: same shrinkage on the merged tile with σ²/N ("assuming all N frames were averaged perfectly") plus frequency-dependent "noise shaping".
  - Finishing: black level, lens shading, WB, demosaic, chroma denoise, colour correction, dynamic-range compression by fusing **two synthetic exposures** (grayscale, Mertens-style), dehaze, S-curve + sRGB, CA correction, sharpening, hue-specific adjustments, dithering.
- **Limitations stated:** noise near strong high-contrast features; mild ghosting (shrinkage never fully rejects a tile); ringing near clipped highlights; very low light breaks AF/AWB; fast motion in low light forces short exposure → noise; halos from exposure fusion.
- **Relation to HIE:** HIE's `hdrplus_wiener` preset reproduces the merge concept; our tile aligner follows the paper's design. HIE's independent tuning sweep selected k = 8, matching the paper's factor of 8 (see benchmark.md).
- **Dataset:** the HDR+ Burst Photography Dataset (3,640 bursts; CC BY-SA) — HIE's first real-data benchmark.

### Night Sight — handheld mobile photography in very low light · Verified
- **Authors:** O. Liba, K. Murthy, Y.-T. Tsai, T. Brooks, T. Xue, N. Karnad, Q. He, J. T. Barron, D. Sharlet, R. Geiss, S. W. Hasinoff, Y. Pritch, M. Levoy
- **Venue:** ACM TOG 38(6), SIGGRAPH Asia 2019 · DOI [10.1145/3355089.3356508](https://doi.org/10.1145/3355089.3356508) · [arXiv:1910.11336](https://arxiv.org/abs/1910.11336)
- **Method:**
  - **Motion metering:** before the shutter press, estimates motion magnitude (a fast "bounded flow" optical-flow magnitude, weighted spatially), predicts future motion with a GMM-based temporal filter, and combines **gyroscope** angular-rate stability, then chooses **per-frame exposure time and gain** trading SNR against motion blur. Frame count follows from a capture-time budget (≤ ~6 s divided by exposure, capped by memory).
  - Merge extends HDR+: **per-tile mismatch maps** drive **spatially varying temporal strength**; spatial denoising uses the noise variance implied by **the merging that actually occurred per tile**, so regions with less temporal merging get more spatial denoising.
  - Learned white balance for very low light; tone mapping inspired by painting conventions.
- **Relation to HIE:** direct prior art for research directions #1 (adaptive capture), #3 (confidence), #5 (gyro) and for HIE v0.1's N_eff-aware spatial denoising.

### Super Res Zoom — handheld multi-frame super-resolution · Verified
- **Authors:** B. Wronski, I. Garcia-Dorado, M. Ernst, D. Kelly, M. Krainin, C.-K. Liang, M. Levoy, P. Milanfar
- **Venue:** ACM TOG 38(4), SIGGRAPH 2019 · DOI [10.1145/3306346.3323024](https://doi.org/10.1145/3306346.3323024) · [arXiv:1905.03277](https://arxiv.org/abs/1905.03277)
- **Method:** merges raw CFA frames directly to RGB with anisotropic **kernel regression** (kernel shape from local structure tensor); a **per-pixel robustness mask** `R = s·exp(−d²/σ²) − t` compares noise-corrected local colour differences with local spatial σ (noise model from Foi et al.), plus a motion prior; hand tremor provides sub-pixel offsets (analysed with **gyroscope** data from 86 bursts). Reports additional spatial denoising "with strength inversely proportional to" the number of merged frames.
- **Relation to HIE:** closest prior art for per-pixel confidence (direction #3) and the required starting point for super-resolution (direction #7).

### HDR+ with Bracketing · Verified (blog, not peer-reviewed)
- Google Research Blog, April 2021: [link](https://blog.research.google/2021/04/hdr-with-bracketing-on-pixel-phones.html). Adds longer exposures to the burst; "depending on the dynamic range of the scene, and the presence of motion, HDR+ with bracketing chooses the best exposures". Prior art for adaptive exposure selection (direction #1) and HDR (v0.4).

## Open re-implementations

### An Analysis and Implementation of the HDR+ Burst Denoising Method · Verified
- A. Monod, J. Delon, T. Veit · IPOL 11 (2021) 142–169 · DOI [10.5201/ipol.2021.336](https://doi.org/10.5201/ipol.2021.336) · open-source Python.
- **Relation:** the reference to cross-check `hdrplus_wiener` against (planned; not yet run — see research-plan).

### Implementing Handheld Burst Super-Resolution · Verified
- J. Lafenetre, G. Facciolo, T. Eboli · IPOL 13 (2023) 227–257 · DOI [10.5201/ipol.2023.460](https://doi.org/10.5201/ipol.2023.460).
- **Relation:** open implementation of Wronski et al.; baseline for v0.5 super-resolution.

## Learned burst and ISP methods

| Paper | Venue | Status | One-line method | Relation to HIE |
|---|---|---|---|---|
| Mildenhall, Barron, Chen, Sharlet, Ng, Carroll — *Burst Denoising with Kernel Prediction Networks* | CVPR 2018 · [arXiv:1712.02327](https://arxiv.org/abs/1712.02327) | Verified | CNN predicts per-pixel kernels that jointly align and denoise; synthetic training data from a realistic noise model | learned-fusion baseline for v0.8; its synthetic-noise protocol resembles ours |
| Godard, Matzen, Uyttendaele — *Deep Burst Denoising* | ECCV 2018 · [arXiv:1712.05790](https://arxiv.org/abs/1712.05790) | Cited | recurrent network over burst frames | learned baseline |
| Brooks, Mildenhall, Xue, Chen, Sharlet, Barron — *Unprocessing Images for Learned Raw Denoising* | CVPR 2019 · [CVF](https://openaccess.thecvf.com/content_CVPR_2019/html/Brooks_Unprocessing_Images_for_Learned_Raw_Denoising_CVPR_2019_paper.html) | Verified | invert the ISP to synthesise realistic raw training data | a better synthetic-data generator than our procedural chart |
| Bhat, Danelljan, Van Gool, Timofte — *Deep Burst Super-Resolution* | CVPR 2021 · [CVF](https://openaccess.thecvf.com/content/CVPR2021/html/Bhat_Deep_Burst_Super-Resolution_CVPR_2021_paper.html) | Verified | flow-aligned deep embeddings + attention fusion; SyntheticBurst and BurstSR (phone bursts + DSLR ground truth) datasets | BurstSR is the obvious real ground-truth dataset for SR evaluation |
| Lecouat, Ponce, Mairal — *Lucas-Kanade Reloaded* | ICCV 2021 · arXiv:2104.06191 | Cited | end-to-end SR from raw bursts with learned alignment | learned alignment comparison |
| Ignatov, Van Gool, Timofte — *Replacing Mobile Camera ISP with a Single Deep Learning Model* (PyNET) | [arXiv:2002.05509](https://arxiv.org/abs/2002.05509) (CVPR Workshops 2020) | Verified (arXiv) | pyramidal CNN replaces the full ISP; 10k Huawei P20 raw / Canon 5D IV pairs | neural-ISP baseline (level 4 of the recovery hierarchy) |

## Capture planning, noise and alignment foundations

| Reference | Status | Used for |
|---|---|---|
| Hasinoff, Durand, Freeman — *Noise-Optimal Capture for High Dynamic Range Photography*, CVPR 2010, pp. 553–560 | Verified | prior art for choosing an optimal capture *sequence* (exposures/ISO) as an optimisation problem — directions #1 and #2 |
| Foi, Trimeche, Katkovnik, Egiazarian — *Practical Poissonian-Gaussian noise modeling and fitting for single-image raw-data*, IEEE TIP 17(10), 2008 | Cited | noise model `var = S·x + O`; `NoiseModel` |
| Immerkær — *Fast Noise Variance Estimation*, CVIU 64(2), 1996 | Cited | single-image noise estimator and residual-noise metric |
| Kuglin & Hines — phase correlation, 1975 | Cited | `PhaseCorrelationAligner` |
| Kroeger, Timofte, Dai, Van Gool — *Fast Optical Flow using Dense Inverse Search*, ECCV 2016 | Cited | `DISFlowAligner` (OpenCV) |
| Karpenko, Jacobs, Baek, Levoy — *Digital Video Stabilization and Rolling Shutter Correction using Gyroscopes*, Stanford CSTR 2011-03 | Verified | gyro–camera calibration and synchronisation; direction #5 |
| Malvar, He, Cutler — *High-quality linear interpolation for demosaicing of Bayer-patterned color images*, ICASSP 2004 | Cited | default demosaic |
| Mertens, Kautz, Van Reeth — *Exposure Fusion*, Pacific Graphics 2007 | Cited | synthetic exposure fusion |
| He, Sun, Tang — *Guided Image Filtering*, ECCV 2010 | Cited | chroma denoising |
| Wang, Bovik, Sheikh, Simoncelli — SSIM, IEEE TIP 2004; Wang, Simoncelli, Bovik — MS-SSIM, Asilomar 2003 | Cited | metrics |
| Sharma, Wu, Dalal — *The CIEDE2000 color-difference formula*, Color Res. Appl. 2005 | Cited (test pairs reproduced exactly in unit tests) | ΔE2000 |
| Adobe — DNG Specification 1.4/1.6 | Cited | DNG tags, colour pipeline, opcodes |

## Gyro-initialised burst alignment

### Inertia Sensor Aided Alignment for Burst Pipeline in Low Light Conditions · Verified (arXiv)
- **Authors:** S. Zhang, R. L. Stevenson
- **Venue:** IEEE (Xplore document [8451134](https://ieeexplore.ieee.org/document/8451134); HTML full text blocked) · [arXiv:1811.02013](https://arxiv.org/abs/1811.02013) (opened)
- **Method (as stated on arXiv):** integrate smartphone gyro angular velocity (Runge–Kutta) to a rotation matrix, convert with camera intrinsics; estimate 3-D translation from SURF matches; form an initial homography `H0 = R0 + T0 n0ᵀ`; refine the 8 homography parameters with an unscented Kalman filter using the feature matches as observations; then run a Gaussian-pyramid tile alignment (HDR+-style) and a frequency-domain hybrid Wiener merge on Bayer raw.
- **Relation to HIE:** this is published gyro-*initialised* burst alignment on raw smartphone bursts. Direction #5 in the brief is therefore covered as a research claim. Measuring camera–gyro sync error on Pixel 6 (Karpenko 2011; Camera2 `SENSOR_INFO_TIMESTAMP_SOURCE`) is still a necessary *experiment* before any gyro prior is used, and is what Hanson Camera Lab logs.

### GyroFlow — gyroscope-guided unsupervised optical flow · Verified (CVF PDF)
- **Authors:** H. Li, K. Luo, B. Zeng, S. Liu
- **Venue:** ICCV 2021 · [CVF PDF](https://openaccess.thecvf.com/content/ICCV2021/papers/Li_GyroFlow_Gyroscope-Guided_Unsupervised_Optical_Flow_Learning_ICCV_2021_paper.pdf)
- **Method:** convert phone gyro readings to a “gyro field”; fuse it with image-based unsupervised flow via a self-guided fusion module. They read gyro from the Android HAL rather than the public API to reduce sync error.
- **Relation:** learned gyro+image flow, not a raw burst merge. Relevant as a prior for any later learned aligner.

### Related IEEE / WIPO hits (abstract level)
- IEEE Xplore document [6831799](https://ieeexplore.ieee.org/document/6831799): abstract describes gyro + feature tracking for rolling-shutter correction, then stacking a smartphone burst (iPhone 5s / similar). Full paper not opened (Xplore captcha).
- IEEE Xplore document [9509028](https://ieeexplore.ieee.org/document/9509028) (DeepOIS, abstract): a network that compensates OIS so gyro fields can still be used for alignment on OIS cameras.
- WIPO [WO/2024/107273](https://patentscope.wipo.int/search/en/WO2024107273): orientation-sensor data used to *select* similar frames before compositing, not to initialise tile alignment.
- WIPO [WO/2021/138870](https://patentscope.wipo.int/search/en/WO2021138870): multi-camera concurrent frames, warp to a benchmark, replace large residuals. Not gyro.

## Semantic / region-aware ISP

### Sky Optimization — semantically aware sky processing · Verified (arXiv)
- **Authors:** O. Liba, L. Cai, Y.-T. Tsai, E. Eban, Y. Movshovitz-Attias, Y. Pritch, H. Chen, J. T. Barron (Google Research)
- **Venue:** [arXiv:2006.10172](https://arxiv.org/abs/2006.10172) (opened)
- **Method:** MorphNet-compressed sky segmentation at 256×256 on a mobile GPU (~50 ms), weighted-guided-filter upsample (Halide), then sky-only spatially varying white balance, tone, contrast and denoise. Integrated in an Android Camera2 pipeline; end-to-end < 0.5 s.
- **Relation to HIE:** shipped semantic *finishing* of one region (sky). Direction #6 as “semantic ISP” is covered for sky. A narrower untested question is whether a semantic mask should change *temporal merge* (e.g. more averaging on sky, less on people). Night Sight’s mismatch maps are motion-based, not class-based.

### DeepISP — end-to-end learned ISP · Verified (arXiv HTML)
- **Authors:** E. Schwartz, R. Giryes, A. M. Bronstein
- **Venue:** IEEE TIP 28(2), 2019 · [arXiv:1801.06724](https://arxiv.org/abs/1801.06724)
- **Method:** CNN maps a low-light mosaiced raw to a finished RGB/JPEG (Samsung S7 pairs). Local residual corrections plus a *global* quadratic colour transform; the paper states it does not model local tone mapping or HDR.
- **Relation:** learned full-ISP baseline (with PyNET). Not region-aware.

### On-device panoptic segmentation for Camera · Verified (Apple ML Research page)
- Apple Machine Learning Research, [On-device Panoptic Segmentation for Camera Using Transformers](https://machinelearning.apple.com/research/panoptic-segmentation) (opened).
- Person / skin / hair / sky (and instance IDs) drive Portrait Mode, Photographic Styles, per-subject contrast in Smart HDR 4, and denoise/sharpen in low-texture regions.
- **Relation:** production semantic ISP on iPhone. Same direction #6 coverage from a second vendor.

## Uncertainty calibration (burst / imaging)

No opened source applies *calibrated* (coverage-guaranteed) per-pixel uncertainty to a raw burst merge.

- **QUTCC** (quantile regression + conformal calibration for imaging inverse problems) · Verified ([arXiv:2507.14760](https://arxiv.org/html/2507.14760)): pixel-wise intervals and uncertainty maps after conformal adjustment of quantile bounds. Demonstrated on imaging inverse problems / denoising, **not** on smartphone raw bursts or on an `N_eff` merge residual.
- **KPN / Unprocessing / Night Sight / Super Res Zoom** (already in this review): they *condition* on a noise model or emit robustness / mismatch weights. Those weights are not evaluated as calibrated predictive σ (ECE, coverage).
- Direction #3’s remaining sliver — a *calibrated* predictive per-pixel σ for the merge, checked for coverage on held-out bursts — was not found in this pass. That is a possible experiment, not a claim.

## Patents found so far

| Patent | What the opened text covers | Status |
|---|---|---|
| US 9,313,420 B2 — *Intelligent computational imaging system* (Seshadrinathan, Park, Nestares; Intel; 2016; expired 2024 for unpaid fees) | Independent method claim 16 (Google Patents page opened): analyse a first set of frames; if multi-image processing is chosen, determine a frame count for scene dynamic range, capture, align, merge; the minimum count is obtained by estimating SNR, dynamic range and a spectral-irradiance histogram, then **incrementally increasing the number of frames to maximise the sum of per-pixel SNR**. Device claims 10 and 18 repeat the same SNR-increment step. Description adds a camera noise model, short/long exposure search from histogram percentiles, 60 ms motion-blur cap, 3-D rotation alignment on raw Bayer, and ML merge. | Claims + description opened on [Google Patents](https://patents.google.com/patent/US9313420B2/en). Direction #2 (adaptive burst length / termination on *summed SNR of captured pixels*) is covered. Termination on the *reconstruction’s* per-pixel uncertainty after motion rejection is still not in these claims. |
| US 9,087,391 B2 — *Determining an image capture payload burst structure* (Geiss, Hasinoff; Google; 2015) | Description (Google Patents opened) and independent claim 1 (patents-review / claim dump opened): a metering burst at different TETs → determine a long TET, a short TET and a TET *sequence* → capture a payload burst in that order, including a long–short–long subsequence → construct the output. Dependent claims cover HDR vs LDR histogram classification and single-TET LDR bursts. | Direction #1 (choosing burst structure / exposures from a metering sweep) is covered. Constant-exposure HDR+ bursts are the LDR special case. |
| US 8,866,927 B2 — *…payload burst structure based on a metering image capture sweep* (Google) | Independent claim (opened on a claims dump): metering sweep → TET sequence; if the scene is classified LDR, all payload TETs are equal and frames are aligned and combined. | Sister patent to 9,087,391; same conclusion. |
| WO/2024/107273 | Orientation-sensor frame *selection* before compositing. | Abstract only (WIPO PATENTSCOPE). |
| WO/2021/138870 | Multi-camera concurrent capture, warp, residual replacement. | Abstract only (WIPO PATENTSCOPE). |

Adaptive capture, burst-structure planning and SNR-driven extra frames are patented and published. Hanson Camera Lab’s default burst policy is a **reproduction** of the published constant-exposure HDR+ / Night Sight time-budget idea (more frames in low light, cap 15), not a new method. It does **not** implement US 9,313,420’s incremental SNR loop or US 9,087,391’s bracketed TET sequence.

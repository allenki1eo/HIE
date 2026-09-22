# Literature review

Status legend for each entry:

- **Verified** — details below were checked against the primary source (paper PDF, publisher or arXiv page) during this review.
- **Cited** — a standard method reference used by HIE code; bibliographic details are from the standard citation and were not re-fetched in this pass.

Searches in this pass used the web (arXiv, ACM DL, CVF Open Access, IPOL, Google Research, Google Patents / USPTO). IEEE Xplore, WIPO and EPO were **not** searched yet; that gap is tracked in [prior-art.md](prior-art.md#search-log).

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

## Patents found so far

| Patent | What it covers (from the abstract/summary) | Status |
|---|---|---|
| US 9,313,420 — *Intelligent computational imaging system* | analyse input frames, decide on multi-image processing, estimate SNR and dynamic range, and **incrementally increase the number of frames to maximise the summed SNR** | abstract only; full claims not yet read (USPTO/Google Patents returned 403/503) |
| US 9,087,391 B2 — *Determining an image capture payload burst structure* (Google) | histogram of merged images → scene classification → burst structure (frame count, exposures) | search summary only; claims not yet read |

Full-text claim review is required before any novelty statement about adaptive capture or burst termination.

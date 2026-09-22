# Hanson Image Engine (HIE)

A computational photography **research engine** for smartphone RAW bursts, by Hanson Technologies.
HIE v0.1 reproduces and benchmarks the established burst pipeline (RAW decoding, alignment, robust
merging, denoising, colour, tone mapping) on real Google HDR+ bursts and on synthetic bursts with
exact ground truth. It is the measured baseline that any new HIE method must beat.

> **Status:** v0.1 baselines complete. The research report is waiting at the brief's **approval gate**
> ([docs/research-report-001.md](docs/research-report-001.md)). No method in this repository is
> claimed to be novel. See [docs/prior-art.md](docs/prior-art.md) for what already exists.

## v0.1 results at a glance

Real RAW bursts (12 Google HDR+ bursts, ISO 50–2056, mean) and synthetic bursts with exact ground truth
(6 scenes, test split). Full tables and failure analysis are in [docs/benchmark.md](docs/benchmark.md).

| Method | Real: noise removed | Real: reference deviation | Synthetic: PSNR | Synthetic: motion-region PSNR | Synthetic: detail retained |
|---|--:|--:|--:|--:|--:|
| Single frame | 0.0 dB | 0.00 % | 36.7 dB | 35.1 dB | 0.98 |
| Mean (aligned) | 9.4 dB | 2.53 % | 41.5 dB | 30.3 dB | 0.84 |
| HDR+ merge (reproduction) | 7.7 dB | 0.03 % | 43.3 dB | 39.5 dB | 0.87 |
| Confidence fusion | 9.3 dB | 0.50 % | 44.6 dB | 41.8 dB | 0.86 |
| **HIE v0.1** | **14.8 dB** | 0.50 % | **47.0 dB** | **44.0 dB** | 0.81 |

Plain averaging ghosts on motion, and robust weighting fixes that. HIE v0.1's noise-aware spatial
denoising adds the most, at a measured cost in fine detail at night. The biggest open problem is
alignment at very low light: perfect alignment would keep 0.88 of night detail, and today's best
estimated alignment keeps 0.70.

## Quick start

```bash
pip install -e ".[dev]"                        # Python ≥ 3.10
python -m pytest -q                            # unit + integration + regression tests

hie data download 0127_20161018_111029_303     # one HDR+ burst (MD5-verified, CC BY-SA)
hie inspect 0127_20161018_111029_303           # sizes, bit depth, CFA, levels, ISO, noise profile
hie process 0127_20161018_111029_303 -p hie_v0.1 --tiff
hie bench synthetic                            # ground-truth benchmark (EXP-001…005)
hie bench hdrplus                              # all local HDR+ bursts + interactive HTML report
```

`hie process` also accepts a folder of DNGs, such as a Pixel 6 experiment package. Every run writes
a new directory under `benchmarks/results/` with an `experiment.json` recording the commit,
parameters and environment. Runs never overwrite each other.

## Algorithms (presets)

| Preset | What it does | Brief |
|---|---|---|
| `single` | reference frame only, same rendering as all others | EXP-001 |
| `single_denoised` | single frame + the same spatial denoiser HIE uses | control |
| `mean_noalign` / `mean` | temporal mean without / with tile alignment | EXP-002 + ablation |
| `median` | per-pixel temporal median | EXP-003 |
| `weighted` | per-frame sharpness weights ("lucky imaging") + saturation | baseline 3 |
| `motion_aware` | pixel-domain temporal Wiener shrinkage toward the reference | baseline 4 |
| `flow_mean` | DIS dense optical flow + mean | EXP-004 |
| `hdrplus_wiener` | reproduction of the HDR+ frequency-domain pairwise merge (Hasinoff et al. 2016) | published baseline |
| `confidence` | weighted mean with explicit per-pixel confidence; outputs an N_eff map | EXP-005 |
| `hie_v0.1` | `confidence` + spatial Wiener denoising driven by σ²/N_eff | current default |

Aligners: `none`, `phase_correlation`, `feature_homography`, `dis_flow`, `hdrplus_tiles` (default).

## Repository map

```text
hie_core/        engine: raw · noise · alignment · fusion · confidence · demosaic · color ·
                 tone_mapping · finish · pipeline · datasets · metrics · bench · report · cli
docs/            research-plan · literature-review · prior-art · architecture · benchmark ·
                 datasets · research-report-001 (approval gate)
datasets/        download instructions and attribution only (data is never committed)
benchmarks/      reports (committed summaries) · results (local runs) · scripts
tests/           unit · integration · regression
research/        experiment notes, algorithm proposals
android/         Hanson Camera Lab plan (Pixel 6, milestone 2, not built yet)
```

## Data and licence

Real-image results use the **Google HDR+ Burst Photography Dataset** (Hasinoff et al., SIGGRAPH Asia
2016), licensed **CC BY-SA**. It is not redistributed here; see
[datasets/google-hdr-plus/README.md](datasets/google-hdr-plus/README.md). HIE's own code is
"all rights reserved" for now ([LICENSE](LICENSE)); the open-sourcing decision belongs to the owner.

*Capture intelligently. Measure uncertainty. Recover information. Preserve reality.*

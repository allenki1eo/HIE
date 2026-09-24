# Research plan

The protocol follows the brief: literature → implementations → baseline reproduction → failure
analysis → gap → hypothesis → approval gate → new method → benchmark → ablation → prior-art comparison.

## Status against the brief's first tasks

| # | Task | Status |
|---|---|---|
| 1 | Repository structure | done |
| 2 | Research documentation | done (this folder) |
| 3 | Literature investigation | second pass 2026-09-23: US 9,313,420 and US 9,087,391 claims opened; IEEE Xplore bibliographic search; WIPO abstracts; gyro alignment, semantic ISP, uncertainty calibration recorded. EPO Espacenet still incomplete (JS-only UI). |
| 4 | HDR+ dataset setup | done: MD5-verified downloader, manifest, attribution |
| 5 | RAW inspection tool | done: `hie inspect` |
| 6 | Single RAW baseline | done: preset `single` |
| 7 | Multi-frame mean | done: `mean`, `mean_noalign` |
| 8 | Alignment comparison | done: 5 aligners; oracle-alignment study on synthetic data |
| 9 | Benchmark framework | done: `hie bench synthetic`, `hie bench hdrplus`, HTML report |
| 10 | Failure analysis | done: F1–F4 plus negative results in [benchmark.md](benchmark.md#failure-analysis) |
| 11 | Research hypothesis | done: H1 in [research-report-001.md](research-report-001.md) |
| 12 | **Approval gate** | **waiting for human approval**. No allegedly novel algorithm has been implemented. H1 is not in the Android app or the Python engine. |
| 13 | Hanson Camera Lab (milestone 2) | done as v0.1 of the Android app: Camera2 inspector, RAW burst + DNG, gyro/accel log, stock JPEG, Pixel-6 package layout. APK built from `android/`. On-device processing is the phone ISP JPEG plus a bilinear RAW preview — not a port of H1. |

## Next work that does not need the approval gate

1. **Cross-check the HDR+ reproduction** against the open IPOL implementation (Monod et al. 2021) on the same bursts.
2. **Finish EPO / IEEE full-text**: Espacenet returned no documents (JS shell); IEEE HTML was captcha-blocked. Abstracts and arXiv texts are recorded.
3. **Capture on Pixel 6 and other Android phones** with Camera Lab; measure `SENSOR_INFO_TIMESTAMP_SOURCE` vs gyro timestamps (needed before any gyro prior).
4. **Reference-quality synthetic data**: replace the procedural chart with unprocessed real images (Brooks et al. 2019) for more natural statistics.
5. **Perceptual metrics**: LPIPS and DISTS need PyTorch and pretrained weights, and are not in v0.1.
6. **On-device HIE port** (later): Halide / NDK of the existing v0.1 stages. That is engineering, not a new method.

## Roadmap (provisional, from the brief)

v0.2 robust motion-aware fusion · v0.3 adaptive burst capture · v0.4 HDR / bracketing ·
v0.5 burst super-resolution (2× first) · v0.6 semantic ISP · v0.7 sensor-aware reconstruction ·
v0.8 hybrid learned reconstruction · v1.0 integrated engine.

## Open decisions for the project owner

- **Licence**: decided. HIE code and docs are Apache License 2.0 so others can use, modify, and contribute them ([LICENSE](../LICENSE), [CONTRIBUTING.md](../CONTRIBUTING.md)). The Google HDR+ dataset stays CC BY-SA and is not in this repository.
- **Research direction** after the approval gate: see the options in the research report.

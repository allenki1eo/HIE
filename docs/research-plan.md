# Research plan

The protocol follows the brief: literature → implementations → baseline reproduction → failure
analysis → gap → hypothesis → approval gate → new method → benchmark → ablation → prior-art comparison.

## Status against the brief's first tasks

| # | Task | Status |
|---|---|---|
| 1 | Repository structure | done |
| 2 | Research documentation | done (this folder) |
| 3 | Literature investigation | first pass done, with systems papers verified against primary sources; IEEE Xplore, WIPO, EPO and full patent claims still open ([prior-art](prior-art.md#search-log)) |
| 4 | HDR+ dataset setup | done: MD5-verified downloader, manifest, attribution |
| 5 | RAW inspection tool | done: `hie inspect` |
| 6 | Single RAW baseline | done: preset `single` |
| 7 | Multi-frame mean | done: `mean`, `mean_noalign` |
| 8 | Alignment comparison | done: 5 aligners; oracle-alignment study on synthetic data |
| 9 | Benchmark framework | done: `hie bench synthetic`, `hie bench hdrplus`, HTML report |
| 10 | Failure analysis | first pass in [benchmark.md](benchmark.md#failure-analysis) |
| 11 | Research hypothesis | drafted in [research-report-001.md](research-report-001.md) |
| 12 | **Approval gate** | **waiting for human approval**. No allegedly novel algorithm has been implemented. |

## Next work that does not need the approval gate

1. **Cross-check the HDR+ reproduction** against the open IPOL implementation (Monod et al. 2021) on the same bursts.
2. **Close the literature gaps**: IEEE Xplore, WIPO, EPO; full claims of US 9,313,420 and US 9,087,391; semantic ISP; uncertainty calibration in burst denoising; gyro-initialised burst alignment.
3. **Hanson Camera Lab (milestone 2)**: a Camera2 capability inspector and RAW burst capture with gyro logging on the Pixel 6 ([android/README.md](../android/README.md)).
4. **Reference-quality synthetic data**: replace the procedural chart with unprocessed real images (Brooks et al. 2019) for more natural statistics.
5. **Perceptual metrics**: LPIPS and DISTS need PyTorch and pretrained weights, and are not in v0.1.

## Roadmap (provisional, from the brief)

v0.2 robust motion-aware fusion · v0.3 adaptive burst capture · v0.4 HDR / bracketing ·
v0.5 burst super-resolution (2× first) · v0.6 semantic ISP · v0.7 sensor-aware reconstruction ·
v0.8 hybrid learned reconstruction · v1.0 integrated engine.

## Open decisions for the project owner

- **Licence**: the repository is "all rights reserved" for now. The brief anticipates open-sourcing some research components; which ones is a business decision.
- **Research direction** after the approval gate: see the options in the research report.

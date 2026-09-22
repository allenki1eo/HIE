# Metrics

Implemented in `hie_core/metrics/`:

| Metric | Kind | Notes |
|---|---|---|
| PSNR, SSIM, MS-SSIM | full reference | SSIM uses an 11×11 Gaussian window, σ = 1.5 (Wang et al. 2004) |
| CIEDE2000 | colour | reproduces Sharma et al. (2005) test pairs exactly |
| Detail retention | full reference | band-pass energy of the reference recovered by the output; catches over-smoothing that PSNR rewards |
| Immerkær residual noise | no reference | measured in flat regions only |
| Reference deviation rate | no reference | fraction of pixels whose low-passed difference from the reference exceeds 5σ; a ghosting and blur proxy |
| Agreement with Google merge | reference system | PSNR vs HDR+ `merged.dng` after a gain fit; similarity, **not** quality |

Not yet implemented: LPIPS and DISTS (need PyTorch and pretrained weights), system metrics on the
phone (power, thermal), and semantic crops (faces, text), which need detectors.

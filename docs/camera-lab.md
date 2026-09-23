# Hanson Camera Lab

Android Camera2 app for milestone 2, plus an on-device port of the existing
**HIE v0.1** finish (tile align → confidence merge → N_eff spatial Wiener → MHC
→ Camera2 WB/CCM → local tone → finish). The phone writes `hie/output.jpg`
after each RAW burst.

It does **not** implement hypothesis H1 or any method waiting at the approval
gate. The C++ path is a reproduction of the Python `hie_v0.1` stages, not a new
algorithm.

## What it captures

Each shutter press writes a never-overwritten package under the app’s files dir
(`Android/data/com.hanson.hie.cameralab.debug/files/experiments/experiment_NNNN/`):

| Path | Source |
|---|---|
| `raw/frame_000.dng` … | Camera2 `RAW_SENSOR` via `DngCreator` |
| `metadata.json` | per-frame `CaptureResult` (timestamp, exposure, ISO, focus, AWB, CCM, OIS samples) |
| `motion/sensors.csv` | gyro + accelerometer at `SENSOR_DELAY_FASTEST`, `t_ns` = `SensorEvent.timestamp` |
| `stock/reference.jpg` | hardware-ISP JPEG of the same scene, taken **after** the burst |
| `preview.jpg` | optional bilinear RAW preview (established demosaic, not HIE) |
| `hie/output.jpg` | on-device HIE v0.1 JPEG (this is the photo the app shows) |
| `hie/process.json` | timings, `mean_n_eff`, notes (downsample, estimated noise) |
| `experiment.json` | device, app version, git commit, capture policy, timestamp-source note |

A copy of `hie/output.jpg` is also inserted into the device gallery
(`Pictures/HansonCameraLab`) when MediaStore allows it.

Camera characteristics are **enumerated**, never hard-coded to Pixel 6.

## On-device HIE (reproduction)

Stages match `hie_core` preset `hie_v0.1`:

1. Normalise RAW to float32 planes (black 0, white 1), CFA → R/Gr/Gb/B.
2. Pick the sharpest of the first three frames as reference.
3. Hierarchical HDR+ tiles (`hdrplus_tiles`) + cubic warp.
4. EXP-005 confidence fusion with Kish `N_eff`.
5. Spatial Wiener on overlapping 16×16 tiles, variance `σ² / N_eff`.
6. White-balance from `COLOR_CORRECTION_GAINS`, highlight-neutral clip, MHC
   demosaic, `COLOR_CORRECTION_TRANSFORM` as cam→linear sRGB, synthetic-exposure
   fusion, chroma guided filter + cored sharpen.

Documented on-device budgets (recorded in `hie/process.json` notes):

- Mosaic larger than 16 MP: 2× box downsample on the planes (50 MP / quad-Bayer).
- More than 8 frames: extras dropped after the reference (memory).
- Colour uses the Camera2 result matrix, not the Python DNG CCT iteration.
- No lens-shading map yet (Python applies it when a DNG map is present).

Host check of the same C++ (no Android): compile
`android/app/src/main/cpp/hie_pipeline.cpp` + `hie_host_test.cpp` with g++.

## Capture policy (reproduction)

`BurstPolicy` chooses 5–15 constant-exposure frames from the current TET and a time budget
(1.2 s burst / 3 s night). That is the published HDR+ / Night Sight idea (Hasinoff 2016,
Liba 2019). It is **not** US 9,313,420’s incremental SNR loop and **not** US 9,087,391’s
bracketed TET sequence. See [prior-art.md](prior-art.md).

AE and AWB are locked for burst/night so every raw frame has the same exposure.

## Gyro timestamps

`SENSOR_INFO_TIMESTAMP_SOURCE` is written into the package.

- `realtime`: Camera2 timestamps and `SensorEvent.timestamp` share the boottime clock.
- `unknown`: do **not** assume they match. Measure the offset (Karpenko 2011) before any
  gyro-initialised aligner. Zhang & Stevenson 2018 already publish that aligner; Camera Lab
  only logs the data needed to test it.

## Offline processing (workstation check)

```bash
adb pull /sdcard/Android/data/com.hanson.hie.cameralab.debug/files/experiments/
hie package validate experiments/experiment_0001
hie inspect experiments/experiment_0001
hie process experiments/experiment_0001 -p hie_v0.1 --tiff
```

The workstation command is the reference implementation. On-device JPEG is the
same stage list with the budgets above.

## Build

See [android/README.md](../android/README.md). Debug APK: `android/app/build/outputs/apk/debug/`
and `android/dist/`.

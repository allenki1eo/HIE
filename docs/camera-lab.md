# Hanson Camera Lab

Android Camera2 app for milestone 2. It is a **working camera** (live preview + hardware JPEG)
and a **research capture bench** (constant-exposure RAW burst, DNG, gyro/accel, capabilities).

It does **not** implement hypothesis H1 or any method waiting at the approval gate. On-device
“processing” is the phone’s own ISP JPEG plus a bilinear RAW preview. Full HIE finishing is
`hie process <package> -p hie_v0.1` on a workstation.

## What it captures

Each shutter press writes a never-overwritten package under the app’s files dir
(`Android/data/com.hanson.hie.cameralab.debug/files/experiments/experiment_NNNN/`):

| Path | Source |
|---|---|
| `raw/frame_000.dng` … | Camera2 `RAW_SENSOR` via `DngCreator` |
| `metadata.json` | per-frame `CaptureResult` (timestamp, exposure, ISO, focus, AWB, OIS samples) |
| `motion/sensors.csv` | gyro + accelerometer at `SENSOR_DELAY_FASTEST`, `t_ns` = `SensorEvent.timestamp` |
| `stock/reference.jpg` | hardware-ISP JPEG of the same scene, taken **after** the burst |
| `preview.jpg` | optional bilinear RAW preview (established demosaic, not HIE) |
| `experiment.json` | device, app version, git commit, capture policy, timestamp-source note |

Camera characteristics are **enumerated**, never hard-coded to Pixel 6.

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

## Offline processing

```bash
adb pull /sdcard/Android/data/com.hanson.hie.cameralab.debug/files/experiments/
hie package validate experiments/experiment_0001
hie inspect experiments/experiment_0001
hie process experiments/experiment_0001 -p hie_v0.1 --tiff
```

## Build

See [android/README.md](../android/README.md). Debug APK: `android/app/build/outputs/apk/debug/`.

# Hanson Camera Lab (Android)

Working Camera2 app: live preview, hardware JPEG stills, constant-exposure RAW
bursts with `DngCreator`, gyro/accel logging, capability inspector, and an
**on-device HIE v0.1 JPEG** (`hie/output.jpg`) after each RAW capture.

That JPEG is a C++/NDK port of the Python `hie_v0.1` stages (tile align,
confidence merge, N_eff Wiener, MHC, Camera2 colour, local tone, finish). It is
not hypothesis H1.

## Install the debug APK

1. Enable Developer options → USB debugging on the phone.
2. `adb install -r app/build/outputs/apk/debug/app-debug.apk`
3. Grant camera permission. Burst/Night need a camera that advertises `REQUEST_AVAILABLE_CAPABILITIES_RAW`.

A built APK is also copied to `dist/` when the Gradle assemble task succeeds.

## Build from source

Needs JDK 17, Android SDK 34, NDK 26.2, CMake 3.22.1 (`ANDROID_HOME` or `local.properties` `sdk.dir`).

```bash
cd android
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew :app:assembleDebug :app:test
```

Host-only check of the C++ stages (no Android, no NDK):

```bash
g++ -std=c++17 -O2 -o /tmp/hie_host_test \
  app/src/main/cpp/hie_host_test.cpp app/src/main/cpp/hie_pipeline.cpp
/tmp/hie_host_test
```

`minSdk 26` (Oreo). RAW_SENSOR / DngCreator are used when the device exposes them; otherwise
the app still takes JPEGs and records `raw_available=false` (no on-device HIE without RAW).

## Using the app

- **Photo** — HIE burst (the default). Looks like a normal camera; research capture still happens in the background.
- **Night** — same, with a longer time budget.
- Tap the viewfinder to focus. The preview is letterboxed to the sensor aspect so it is not stretched.
- After capture, the photo is shown at its real pixel size (Hanson / Phone toggle if both exist) and saved to **Gallery → DCIM/Hanson**.
- Long-press the title for the lab page (packages + capability dump).

On-device budgets (written into `hie/process.json`): mosaics larger than 16 MP are 2×
plane-downsampled; more than 8 frames are dropped after the reference. Colour uses
`COLOR_CORRECTION_GAINS` + `COLOR_CORRECTION_TRANSFORM` from the capture result.

## Pull a package

```text
adb pull /sdcard/Android/data/com.hanson.hie.cameralab.debug/files/experiments/
hie package validate experiment_0001
hie process experiment_0001 -p hie_v0.1
```

Layout matches [datasets/pixel6](../datasets/pixel6/README.md). The loader never drops frames
silently; `hie package validate` lists missing DNGs as errors and reports `has_hie_jpeg`.

## What this is not

- Not hypothesis H1, not a new merge, not a generative ISP.
- Not US 9,313,420 incremental SNR capture, not US 9,087,391 bracketing, not Zhang & Stevenson
  gyro alignment. Those stay documented prior art; the app only **records** gyro so the sync
  experiment can be run on a real phone.

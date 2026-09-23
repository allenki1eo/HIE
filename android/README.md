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

- **Photo** — one hardware JPEG and, if RAW exists, one DNG + HIE JPEG of that frame.
- **Burst** — 5–15 locked-exposure RAW frames (count from TET / 1.2 s budget) + stock JPEG + HIE merge JPEG.
- **Night** — same, with a 3 s budget (more frames; on-device merge caps at 8).
- **Inspector** — every CameraCharacteristics field listed in the brief, exported as JSON.
- **Experiments** — list packages; the latest HIE JPEG is shown; share the package as a zip.

Tap the viewfinder to meter/focus. After a burst the overlay says `HIE merge…` then shows
the finished JPEG. A copy is also written to the system gallery (`Pictures/HansonCameraLab`)
when MediaStore permits it.

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

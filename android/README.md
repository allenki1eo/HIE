# Hanson Camera Lab (Android)

Working Camera2 app for HIE milestone 2: live preview, hardware JPEG stills, constant-exposure
RAW bursts with `DngCreator`, gyro/accel logging, and a capability inspector. Pixel values are
never hard-coded.

On-device output is the **phone ISP JPEG** plus a bilinear RAW preview. That is not HIE v0.1
and not hypothesis H1. Pull the package and run `hie process` for the research engine.

## Install the debug APK

1. Enable Developer options → USB debugging on the phone.
2. `adb install -r app/build/outputs/apk/debug/app-debug.apk`
3. Grant camera permission. Burst/Night need a camera that advertises `REQUEST_AVAILABLE_CAPABILITIES_RAW`.

A built APK is also copied to `dist/` when the Gradle assemble task succeeds.

## Build from source

Needs JDK 17 and Android SDK 34 (`ANDROID_HOME` or `local.properties` `sdk.dir`).

```bash
cd android
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
./gradlew :app:assembleDebug :app:test
```

`minSdk 26` (Oreo). RAW_SENSOR / DngCreator are used when the device exposes them; otherwise
the app still takes JPEGs and records `raw_available=false`.

## Using the app

- **Photo** — one hardware JPEG and, if RAW exists, one DNG.
- **Burst** — 5–15 locked-exposure RAW frames (count from TET / 1.2 s budget) + stock JPEG after the burst.
- **Night** — same, with a 3 s budget (more frames).
- **Inspector** — every CameraCharacteristics field listed in the brief, exported as JSON.
- **Experiments** — list packages; share the latest as a zip.

Tap the viewfinder to meter/focus. The overlay shows ISO, exposure, RAW size, timestamp source and gyro presence.

## Pull a package

```text
adb pull /sdcard/Android/data/com.hanson.hie.cameralab.debug/files/experiments/
hie package validate experiment_0001
hie process experiment_0001 -p hie_v0.1
```

Layout matches [datasets/pixel6](../datasets/pixel6/README.md). The loader never drops frames
silently; `hie package validate` lists missing DNGs as errors.

## What this is not

- Not a Halide/NDK port of HIE (planned later as engineering).
- Not US 9,313,420 incremental SNR capture, not US 9,087,391 bracketing, not Zhang & Stevenson
  gyro alignment. Those stay documented prior art; the app only **records** gyro so the sync
  experiment can be run on a real phone.

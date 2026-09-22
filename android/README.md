# Hanson Camera Lab (Android) — milestone 2, not built yet

This folder is reserved for the Pixel 6 diagnostic app (brief §20–21). **No Android code exists
yet.** This session had no Android SDK or device to build and test against, and shipping untested
Camera2 code would be worse than none. The plan below is what the app must do.

## Scope of v0.1 of the app
1. **Capability inspector.** Enumerate cameras and show every item in brief §20 from
   `CameraCharacteristics`, never hard-coded Pixel values. Items include RAW capability, RAW sizes,
   ISO and exposure ranges, black and white level, CFA arrangement, OIS, focal lengths, active and
   pixel array, and FPS ranges. Export as JSON.
2. **RAW burst capture.** Manual AE/AWB lock, with 5–15 `RAW_SENSOR` frames at a fixed exposure
   and ISO, written with `DngCreator`. Record each `CaptureResult` (sensor timestamp, exposure,
   sensitivity, lens state, OIS samples) in `metadata.json`.
3. **Motion logging.** Gyroscope and accelerometer at the highest rate, stamped with
   `SENSOR_TIMESTAMP`-compatible clocks, stored in `motion/sensors.csv`. Check
   `SENSOR_INFO_TIMESTAMP_SOURCE` and measure camera–gyro sync error rather than assume it (brief §14).
4. **Stock reference.** Capture a stock JPEG of the same scene right after the burst.
5. **Package export** in the layout of [datasets/pixel6](../datasets/pixel6/README.md). Never overwrite.

## Planned structure
`app/` (Kotlin UI) · `camera/` (Camera2 session, capability inspection) · `capture/` (burst policy and
DNG writing) · `sensors/` (gyro logging) · `native/` (NDK/C++ ports of HIE stages, later).

The Python engine already reads these packages (`hie inspect`, `hie process`), including
GainMap lens shading in `OpcodeList2`, so the offline half of milestone 2 is ready.

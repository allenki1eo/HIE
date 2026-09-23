# Pixel 6 experiment packages

Real-world captures from Hanson Camera Lab (Pixel 6 first, any Android phone with RAW).
Nothing here is committed. The capture app is `android/` — see [docs/camera-lab.md](../../docs/camera-lab.md).
Each capture is one self-contained, never-overwritten package (brief §21):

```text
experiment_0001/
├── raw/frame_000.dng …        Camera2 RAW burst (DngCreator)
├── metadata.json              per-frame CaptureResult: timestamp, exposure, ISO, focus, AWB, OIS data
├── motion/sensors.csv         gyroscope + accelerometer with sensor timestamps
├── stock/reference.jpg        stock camera photo of the same scene, captured right after
├── hie/                       outputs (written by `hie process`, never overwritten)
└── experiment.json            device, app version, capture policy, commit
```

HIE reads these today with `hie inspect <folder>` and `hie process <folder>`. Pixel 6 DNGs store
lens shading as GainMap opcodes in `OpcodeList2`, which `hie_core.raw.opcodes` already parses.
That parser is validated on HDR+ `merged.dng` files, **not yet on a real Pixel 6 file**.

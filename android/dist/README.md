# Built APK

`hanson-camera-lab-debug.apk` — debug-signed Camera Lab (`com.hanson.hie.cameralab.debug`),
version 0.2: on-device HIE v0.1 JPEG (`hie/output.jpg`) after each RAW burst.

```bash
adb install -r hanson-camera-lab-debug.apk
```

Rebuild: `cd android && ./gradlew :app:assembleDebug`

SHA-256 of the copy committed with this tree:

`97429b5bfe99cedece79f5e96c9f7b2fc6f2f8d10663cec9a11c370417d7517b`

Do not treat a debug APK as a store release.

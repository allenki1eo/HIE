# Built APK

`hanson-camera-lab-debug.apk` — debug-signed Camera Lab (`com.hanson.hie.cameralab.debug`).

```bash
adb install -r hanson-camera-lab-debug.apk
```

Rebuild: `cd android && ./gradlew :app:assembleDebug`

SHA-256 of the copy committed with this tree is recorded in the PR when the assemble task succeeds. Do not treat a debug APK as a store release.

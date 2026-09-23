# Built APK

`hanson-camera-lab-debug.apk` — debug-signed Camera Lab (`com.hanson.hie.cameralab.debug`),
version 0.2.1: on-device HIE JPEG, gallery save, and a viewfinder that stays connected.

```bash
adb install -r hanson-camera-lab-debug.apk
```

Rebuild: `cd android && ./gradlew :app:assembleDebug`

SHA-256 of the copy committed with this tree:

`f4c8c330fa456ac531cb81995601f621e83f05f16853a2b90c35820385342cc6`

Do not treat a debug APK as a store release.

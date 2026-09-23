# Built APK

`hanson-camera-lab-debug.apk` — debug-signed Camera Lab (`com.hanson.hie.cameralab.debug`),
version 0.2.1: on-device HIE JPEG, gallery save, and a viewfinder that stays connected.

```bash
adb install -r hanson-camera-lab-debug.apk
```

Rebuild: `cd android && ./gradlew :app:assembleDebug`

SHA-256 of the copy committed with this tree:

`fb57afcd5e98cb0399ca8d1b9ca22b75736cf90a143fbf27c435f716ac93ff7c`

Do not treat a debug APK as a store release.

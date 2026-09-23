package com.hanson.hie.cameralab

import android.app.Application
import android.os.Build
import com.hanson.hie.cameralab.capture.ExperimentStore

class CameraLabApp : Application() {
    lateinit var experiments: ExperimentStore
        private set

    override fun onCreate() {
        super.onCreate()
        experiments = ExperimentStore(filesDir.resolve("experiments"))
    }

    companion object {
        fun deviceInfo(): Map<String, Any?> = mapOf(
            "manufacturer" to Build.MANUFACTURER,
            "brand" to Build.BRAND,
            "model" to Build.MODEL,
            "device" to Build.DEVICE,
            "product" to Build.PRODUCT,
            "android_release" to Build.VERSION.RELEASE,
            "android_sdk" to Build.VERSION.SDK_INT,
        )
    }
}

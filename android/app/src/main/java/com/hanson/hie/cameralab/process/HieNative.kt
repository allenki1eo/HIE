package com.hanson.hie.cameralab.process

import java.nio.ByteBuffer

/**
 * JNI entry for the on-device port of Python `hie_v0.1`.
 * Loaded only when a burst is processed — unit tests never touch this class.
 */
object HieNative {
    @Volatile private var loaded = false

    @Synchronized
    fun ensureLoaded() {
        if (!loaded) {
            System.loadLibrary("hie_jni")
            loaded = true
        }
    }

    /**
     * @param mosaics packed little-endian uint16 mosaics (direct ByteBuffer or ShortArray)
     * @param outWh length-2; filled with output width, height
     * @param outJson length-1; filled with process JSON
     * @return packed RGB bytes, display-referred sRGB
     */
    @JvmStatic
    external fun processBurst(
        mosaics: Array<Any>,
        width: Int,
        height: Int,
        stridePixels: Int,
        cfa: String,
        black: FloatArray,
        white: Float,
        shot: FloatArray,
        read: FloatArray,
        haveNoise: Boolean,
        wb: FloatArray,
        ccm: FloatArray,
        orientationDeg: Int,
        maxMosaicPixels: Int,
        maxFrames: Int,
        outWh: IntArray,
        outJson: Array<String?>,
    ): ByteArray
}

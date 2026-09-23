package com.hanson.hie.cameralab.process

import android.graphics.Bitmap
import android.graphics.Color
import android.media.Image
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * Downsampled bilinear demosaic + white-balance + sRGB gamma for a RAW preview.
 *
 * This is the established Malvar/bilinear-family preview path, not HIE v0.1 and
 * not hypothesis H1. Full finishing stays in `hie process` on a workstation.
 */
object OnDeviceIsp {
    fun preview(image: Image, black: Int, white: Int, wb: FloatArray, maxSide: Int = 512): Bitmap {
        val w = image.width
        val h = image.height
        val rowStride = image.planes[0].rowStride
        val pixelStride = image.planes[0].pixelStride.coerceAtLeast(2)
        val buf = image.planes[0].buffer
        val step = max(2, (max(w, h) / maxSide) * 2)
        val outW = (w / step).coerceAtLeast(1)
        val outH = (h / step).coerceAtLeast(1)
        val pixels = IntArray(outW * outH)
        val scale = 1f / max(1, white - black)
        val wr = if (wb.size >= 3) wb[0] else 1f
        val wg = if (wb.size >= 3) wb[1] else 1f
        val wb_ = if (wb.size >= 3) wb[2] else 1f
        for (oy in 0 until outH) {
            val y = (oy * step).coerceAtMost(h - 2)
            for (ox in 0 until outW) {
                val x = (ox * step).coerceAtMost(w - 2)
                val p00 = sample(buf, x, y, rowStride, pixelStride, black, scale)
                val p10 = sample(buf, x + 1, y, rowStride, pixelStride, black, scale)
                val p01 = sample(buf, x, y + 1, rowStride, pixelStride, black, scale)
                val p11 = sample(buf, x + 1, y + 1, rowStride, pixelStride, black, scale)
                // Assume RGGB at (0,0). Wrong phase still yields a usable preview.
                val r = p00 * wr
                val g = 0.5f * (p10 + p01) * wg
                val b = p11 * wb_
                pixels[oy * outW + ox] = Color.rgb(srgb(r), srgb(g), srgb(b))
            }
        }
        return Bitmap.createBitmap(pixels, outW, outH, Bitmap.Config.ARGB_8888)
    }

    private fun sample(
        buf: java.nio.ByteBuffer,
        x: Int,
        y: Int,
        rowStride: Int,
        pixelStride: Int,
        black: Int,
        scale: Float,
    ): Float {
        val i = y * rowStride + x * pixelStride
        if (i + 1 >= buf.limit()) return 0f
        val lo = buf.get(i).toInt() and 0xff
        val hi = buf.get(i + 1).toInt() and 0xff
        val raw = lo or (hi shl 8)
        return ((raw - black) * scale).coerceIn(0f, 1f)
    }

    private fun srgb(x: Float): Int {
        val c = min(1.0, max(0.0, x.toDouble()))
        val g = if (c <= 0.0031308) 12.92 * c else 1.055 * c.pow(1.0 / 2.4) - 0.055
        return (g * 255.0).toInt().coerceIn(0, 255)
    }
}

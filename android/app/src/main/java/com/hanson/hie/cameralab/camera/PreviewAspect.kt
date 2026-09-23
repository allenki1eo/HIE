package com.hanson.hie.cameralab.camera

/**
 * Keep the viewfinder and review frames from stretching.
 *
 * Camera2 preview buffers are typically landscape; on a portrait phone the
 * sensor orientation swaps the displayed sides. The view must match that
 * displayed aspect or SurfaceView will scale the buffer to fill and squash it.
 */
object PreviewAspect {
    data class Box(val width: Int, val height: Int)

    fun displayedAspect(bufferW: Int, bufferH: Int, sensorOrientationDeg: Int): Float {
        val w = bufferW.coerceAtLeast(1)
        val h = bufferH.coerceAtLeast(1)
        val rotated = (sensorOrientationDeg % 180) != 0
        return if (rotated) h.toFloat() / w else w.toFloat() / h
    }

    fun letterbox(
        parentW: Int,
        parentH: Int,
        bufferW: Int,
        bufferH: Int,
        sensorOrientationDeg: Int,
    ): Box {
        val pw = parentW.coerceAtLeast(1)
        val ph = parentH.coerceAtLeast(1)
        val aspect = displayedAspect(bufferW, bufferH, sensorOrientationDeg)
        val parentAspect = pw.toFloat() / ph
        return if (parentAspect > aspect) {
            Box(width = (ph * aspect).toInt().coerceAtLeast(1), height = ph)
        } else {
            Box(width = pw, height = (pw / aspect).toInt().coerceAtLeast(1))
        }
    }

    /**
     * Prefer a 4:3 preview near 1–2 MP so the viewfinder matches stills.
     * [sizes] are (width, height) in sensor coordinates.
     */
    fun choosePreview(sizes: List<Pair<Int, Int>>, maxPixels: Int = 1920 * 1440): Pair<Int, Int> {
        if (sizes.isEmpty()) return 1280 to 960
        val fit = sizes.filter { it.first.toLong() * it.second <= maxPixels.toLong() }.ifEmpty { sizes }
        return fit.minWith(
            compareBy<Pair<Int, Int>> { (w, h) ->
                kotlin.math.abs(w.toFloat() / h.coerceAtLeast(1) - 4f / 3f)
            }.thenBy { (w, h) ->
                kotlin.math.abs(w * h - 1280 * 960)
            },
        )
    }
}

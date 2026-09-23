package com.hanson.hie.cameralab.process

import android.content.Context
import android.graphics.Bitmap
import android.hardware.camera2.CameraCharacteristics
import android.media.Image
import com.hanson.hie.cameralab.camera.FrameMeta
import com.hanson.hie.cameralab.camera.SessionInfo
import com.hanson.hie.cameralab.capture.ExperimentStore
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.min

/**
 * Copy Camera2 RAW planes and run the on-device HIE v0.1 port.
 *
 * Reproduction of the workstation pipeline (tile align → confidence merge →
 * N_eff Wiener → MHC → local tone → finish). Not hypothesis H1.
 */
class HieProcessor(private val context: Context, private val store: ExperimentStore) {

    data class RawCopy(
        val packed: ByteBuffer,
        val width: Int,
        val height: Int,
        val stridePixels: Int,
        val meta: FrameMeta,
    )

    data class Result(
        val jpeg: File,
        val json: File,
        val width: Int,
        val height: Int,
        val processJson: String,
        val galleryUri: String?,
    )

    fun copyRaw(image: Image, meta: FrameMeta): RawCopy {
        val packed = packMosaic(image)
        return RawCopy(packed, image.width, image.height, image.width, meta)
    }

    fun process(dir: File, session: SessionInfo, frames: List<RawCopy>): Result {
        if (frames.isEmpty()) throw IllegalArgumentException("no RAW frames for HIE")
        HieNative.ensureLoaded()
        val first = frames[0]
        val mosaics: Array<Any> = frames.map { it.packed.duplicate().rewind() }.toTypedArray()
        val ch = session.characteristics
        val cfa = cfaName(ch.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT))
        val black = blackLevels(ch)
        val white = (ch.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL) ?: 1023).toFloat()
        val (shot, read, haveNoise) = noiseModel(ch, cfa)
        val wb = whiteBalance(frames)
        val ccm = colorMatrix(frames[0].meta)
        val orientation = jpegOrientation(ch)
        val outWh = IntArray(2)
        val outJson = arrayOfNulls<String>(1)
        val rgb = HieNative.processBurst(
            mosaics,
            first.width,
            first.height,
            first.stridePixels,
            cfa,
            black,
            white,
            shot,
            read,
            haveNoise,
            wb,
            ccm,
            orientation,
            MAX_MOSAIC_PIXELS,
            MAX_FRAMES,
            outWh,
            outJson,
        )
        val w = outWh[0]
        val h = outWh[1]
        if (w <= 0 || h <= 0 || rgb.size < w * h * 3) {
            throw IllegalStateException("HIE returned empty RGB")
        }
        val bmp = rgbToBitmap(rgb, w, h)
        val jpeg = File(File(dir, "hie"), "output.jpg")
        if (jpeg.exists()) throw IllegalStateException("refusing to overwrite $jpeg")
        FileOutputStream(jpeg).use { bmp.compress(Bitmap.CompressFormat.JPEG, 92, it) }
        val jsonText = outJson[0] ?: "{}"
        val extra = JSONObject(jsonText)
            .put("jpeg", "hie/output.jpg")
            .put("jpeg_quality", 92)
            .put("color_source", "camera2_color_correction")
            .put("wb", org.json.JSONArray().put(wb[0]).put(wb[1]).put(wb[2]).put(wb[3]))
        val jsonFile = File(File(dir, "hie"), "process.json")
        store.writeJson(jsonFile, extra)
        val uri = GalleryStore.saveJpeg(context, jpeg)
        return Result(jpeg, jsonFile, w, h, extra.toString(), uri)
    }

    companion object {
        const val MAX_MOSAIC_PIXELS = 16_000_000
        const val MAX_FRAMES = 8

        fun packMosaic(image: Image): ByteBuffer {
            val w = image.width
            val h = image.height
            val plane = image.planes[0]
            val rowStride = plane.rowStride
            val pixelStride = plane.pixelStride.coerceAtLeast(2)
            val src = plane.buffer.duplicate()
            val packed = ByteBuffer.allocateDirect(w * h * 2).order(ByteOrder.LITTLE_ENDIAN)
            val row = ByteArray(rowStride)
            for (y in 0 until h) {
                val pos = y * rowStride
                if (pos >= src.capacity()) break
                src.position(pos)
                val n = min(rowStride, src.remaining())
                src.get(row, 0, n)
                for (x in 0 until w) {
                    val i = x * pixelStride
                    if (i + 1 >= n) {
                        packed.putShort(0)
                        continue
                    }
                    val lo = row[i].toInt() and 0xff
                    val hi = row[i + 1].toInt() and 0xff
                    packed.putShort((lo or (hi shl 8)).toShort())
                }
            }
            packed.rewind()
            return packed
        }

        fun cfaName(v: Int?): String = when (v) {
            CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB -> "RGGB"
            CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_GRBG -> "GRBG"
            CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_GBRG -> "GBRG"
            CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_BGGR -> "BGGR"
            else -> "RGGB"
        }

        fun blackLevels(ch: CameraCharacteristics): FloatArray {
            val p = ch.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)
            val out = FloatArray(4)
            if (p == null) {
                out.fill(64f)
                return out
            }
            // Canonical R, Gr, Gb, B from the 2×2 CFA tile.
            val cfa = cfaName(ch.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT))
            val offs = planeOffsets(cfa)
            for (i in 0 until 4) {
                out[i] = p.getOffsetForIndex(offs[i].second, offs[i].first).toFloat()
            }
            return out
        }

        /** (row, col) in the 2×2 tile for R, Gr, Gb, B. */
        fun planeOffsets(cfa: String): Array<Pair<Int, Int>> {
            val p = cfa.uppercase()
            val grid = arrayOf(charArrayOf(p[0], p[1]), charArrayOf(p[2], p[3]))
            val out = arrayOf(0 to 0, 0 to 1, 1 to 0, 1 to 1)
            for (r in 0..1) for (c in 0..1) {
                when (grid[r][c]) {
                    'R' -> out[0] = r to c
                    'B' -> out[3] = r to c
                    'G' -> {
                        val other = grid[r][1 - c]
                        if (other == 'R') out[1] = r to c else out[2] = r to c
                    }
                }
            }
            return out
        }

        fun noiseModel(ch: CameraCharacteristics, cfa: String): Triple<FloatArray, FloatArray, Boolean> {
            val shot = FloatArray(4) { 1e-4f }
            val read = FloatArray(4) { 1e-6f }
            return try {
                val field = CameraCharacteristics::class.java.getField("SENSOR_NOISE_PROFILE")
                @Suppress("UNCHECKED_CAST")
                val key = field.get(null) as CameraCharacteristics.Key<Array<android.util.Pair<Double, Double>>>
                val p = ch.get(key) ?: return Triple(shot, read, false)
                val offs = planeOffsets(cfa)
                // Pairs are usually listed in CFA scan order (row-major 2×2).
                if (p.size >= 4) {
                    val byRc = Array(2) { Array(2) { p[0] } }
                    var k = 0
                    for (r in 0..1) for (c in 0..1) {
                        if (k < p.size) byRc[r][c] = p[k++]
                    }
                    for (i in 0 until 4) {
                        val (r, c) = offs[i]
                        shot[i] = byRc[r][c].first.toFloat()
                        read[i] = byRc[r][c].second.toFloat()
                    }
                    Triple(shot, read, true)
                } else if (p.isNotEmpty()) {
                    for (i in 0 until 4) {
                        shot[i] = p[0].first.toFloat()
                        read[i] = p[0].second.toFloat()
                    }
                    Triple(shot, read, true)
                } else Triple(shot, read, false)
            } catch (_: Exception) {
                Triple(shot, read, false)
            }
        }

        fun whiteBalance(frames: List<RawCopy>): FloatArray {
            val g = frames.firstOrNull { it.meta.colorGains != null }?.meta?.colorGains
            return if (g != null && g.size >= 4) {
                floatArrayOf(g[0], g[1], g[2], g[3])
            } else {
                floatArrayOf(1f, 1f, 1f, 1f)
            }
        }

        fun colorMatrix(meta: FrameMeta): FloatArray = colorMatrix(meta.colorTransform)

        fun colorMatrix(m: FloatArray?): FloatArray {
            return if (m != null && m.size >= 9) m.copyOf(9) else floatArrayOf(
                1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f,
            )
        }

        fun jpegOrientation(ch: CameraCharacteristics): Int {
            val deg = ch.get(CameraCharacteristics.SENSOR_ORIENTATION) ?: 0
            return ((deg % 360) + 360) % 360
        }

        fun packRgbToArgb(rgb: ByteArray, w: Int, h: Int): IntArray {
            val pixels = IntArray(w * h)
            var i = 0
            for (p in 0 until w * h) {
                val r = rgb[i].toInt() and 0xff
                val g = rgb[i + 1].toInt() and 0xff
                val b = rgb[i + 2].toInt() and 0xff
                i += 3
                pixels[p] = (0xff shl 24) or (r shl 16) or (g shl 8) or b
            }
            return pixels
        }

        fun rgbToBitmap(rgb: ByteArray, w: Int, h: Int): Bitmap {
            return Bitmap.createBitmap(packRgbToArgb(rgb, w, h), w, h, Bitmap.Config.ARGB_8888)
        }
    }
}

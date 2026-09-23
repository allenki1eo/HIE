package com.hanson.hie.cameralab.camera

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.camera2.params.StreamConfigurationMap
import android.os.Build
import android.util.Range
import android.util.Size
import org.json.JSONArray
import org.json.JSONObject

/**
 * Enumerate every camera and dump CameraCharacteristics. Never hard-codes Pixel values.
 *
 * Covers brief §20: RAW capability and sizes, ISO / exposure ranges, black / white level,
 * CFA, OIS, focal lengths, active and pixel array, FPS ranges, plus extras that HIE needs
 * (timestamp source, noise profile, colour filter, hardware level).
 */
object CapabilityInspector {

    fun dumpAll(context: Context): JSONObject {
        val mgr = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val root = JSONObject()
            .put("schema", "hie.camera_lab.capabilities/v1")
            .put("device", JSONObject(com.hanson.hie.cameralab.CameraLabApp.deviceInfo()))
        val cams = JSONArray()
        for (id in mgr.cameraIdList) {
            cams.put(dumpCamera(id, mgr.getCameraCharacteristics(id)))
        }
        root.put("cameras", cams)
        return root
    }

    @SuppressLint("DefaultLocale")
    fun dumpCamera(id: String, ch: CameraCharacteristics): JSONObject {
        val caps = ch.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
        val raw = caps.contains(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW)
        val map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
        val obj = JSONObject()
            .put("id", id)
            .put("facing", facingName(ch.get(CameraCharacteristics.LENS_FACING)))
            .put("hardware_level", hwLevel(ch.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL)))
            .put("raw_capability", raw)
            .put("capabilities", intArrayJson(caps))
            .put("sensor_info_timestamp_source", timestampSource(ch.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)))
            .put("cfa_arrangement", cfaName(ch.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)))
            .put("black_level", jsonArray(ch.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)?.let { p ->
                (0 until 4).map { p.getOffsetForIndex(it % 2, it / 2) }
            }))
            .put("white_level", ch.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL))
            .put("pixel_array", sizeJson(ch.get(CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE)))
            .put("pre_correction_active_array", rectJson(ch.get(CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE)))
            .put("active_array", rectJson(ch.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE)))
            .put("physical_size_mm", sizeFJson(ch.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE)))
            .put("iso_range", rangeJson(ch.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE)))
            .put("exposure_time_ns_range", rangeJson(ch.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE)))
            .put("max_analog_sensitivity", ch.get(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY))
            .put("focal_lengths_mm", floatArrayJson(ch.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS)))
            .put("apertures", floatArrayJson(ch.get(CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES)))
            .put("minimum_focus_distance", ch.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE))
            .put("ois", intArrayJson(ch.get(CameraCharacteristics.LENS_INFO_AVAILABLE_OPTICAL_STABILIZATION)))
            .put("af_modes", intArrayJson(ch.get(CameraCharacteristics.CONTROL_AF_AVAILABLE_MODES)))
            .put("ae_modes", intArrayJson(ch.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_MODES)))
            .put("awb_modes", intArrayJson(ch.get(CameraCharacteristics.CONTROL_AWB_AVAILABLE_MODES)))
            .put("fps_ranges", rangesJson(ch.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)))
            .put("flash_available", ch.get(CameraCharacteristics.FLASH_INFO_AVAILABLE))
            .put("raw_sizes", sizesJson(map?.getOutputSizes(ImageFormat.RAW_SENSOR)))
            .put("jpeg_sizes", sizesJson(map?.getOutputSizes(ImageFormat.JPEG)))
            .put("private_sizes", sizesJson(map?.getOutputSizes(ImageFormat.PRIVATE)))
            .put("noise_profile", noiseProfile(ch))
        if (Build.VERSION.SDK_INT >= 28) {
            obj.put("physical_camera_ids", JSONArray(ch.physicalCameraIds.toList()))
        }
        return obj
    }

    fun chooseBackCameraId(context: Context): String? {
        val mgr = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        var fallback: String? = null
        for (id in mgr.cameraIdList) {
            val ch = mgr.getCameraCharacteristics(id)
            if (fallback == null) fallback = id
            val facing = ch.get(CameraCharacteristics.LENS_FACING)
            val caps = ch.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
            val raw = caps.contains(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW)
            if (facing == CameraCharacteristics.LENS_FACING_BACK && raw) return id
        }
        for (id in mgr.cameraIdList) {
            val ch = mgr.getCameraCharacteristics(id)
            if (ch.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK) return id
        }
        return fallback
    }

    fun rawAvailable(ch: CameraCharacteristics): Boolean {
        val caps = ch.get(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES) ?: intArrayOf()
        return caps.contains(CameraCharacteristics.REQUEST_AVAILABLE_CAPABILITIES_RAW)
    }

    fun largest(map: StreamConfigurationMap?, format: Int): Size? =
        map?.getOutputSizes(format)?.maxByOrNull { it.width.toLong() * it.height }

    private fun facingName(v: Int?) = when (v) {
        CameraCharacteristics.LENS_FACING_BACK -> "back"
        CameraCharacteristics.LENS_FACING_FRONT -> "front"
        CameraCharacteristics.LENS_FACING_EXTERNAL -> "external"
        else -> v?.toString()
    }

    private fun hwLevel(v: Int?) = when (v) {
        CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_LEGACY -> "legacy"
        CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_LIMITED -> "limited"
        CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_FULL -> "full"
        CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_3 -> "level_3"
        CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL_EXTERNAL -> "external"
        else -> v?.toString()
    }

    private fun timestampSource(v: Int?) = when (v) {
        CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_UNKNOWN -> "unknown"
        CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME -> "realtime"
        else -> v?.toString()
    }

    private fun cfaName(v: Int?) = when (v) {
        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGGB -> "RGGB"
        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_GRBG -> "GRBG"
        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_GBRG -> "GBRG"
        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_BGGR -> "BGGR"
        CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT_RGB -> "RGB"
        else -> v?.toString()
    }

    private fun noiseProfile(ch: CameraCharacteristics): JSONArray? {
        val p = ch.get(CameraCharacteristics.SENSOR_NOISE_PROFILE) ?: return null
        val arr = JSONArray()
        for (pair in p) arr.put(JSONArray().put(pair.first).put(pair.second))
        return arr
    }

    private fun sizeJson(s: Size?) = s?.let { JSONObject().put("w", it.width).put("h", it.height) }
    private fun sizeFJson(s: android.util.SizeF?) = s?.let { JSONObject().put("w", it.width.toDouble()).put("h", it.height.toDouble()) }
    private fun rectJson(r: android.graphics.Rect?) = r?.let {
        JSONObject().put("l", it.left).put("t", it.top).put("r", it.right).put("b", it.bottom)
            .put("w", it.width()).put("h", it.height())
    }
    private fun rangeJson(r: Range<*>?) = r?.let { JSONObject().put("min", it.lower).put("max", it.upper) }
    private fun rangesJson(rs: Array<out Range<Int>>?) = JSONArray().also { a -> rs?.forEach { a.put(rangeJson(it)) } }
    private fun sizesJson(ss: Array<Size>?) = JSONArray().also { a -> ss?.forEach { a.put(sizeJson(it)) } }
    private fun floatArrayJson(v: FloatArray?) = JSONArray().also { a -> v?.forEach { a.put(it.toDouble()) } }
    private fun intArrayJson(v: IntArray?) = JSONArray().also { a -> v?.forEach { a.put(it) } }
    private fun jsonArray(v: List<Int>?) = v?.let { JSONArray().also { a -> it.forEach { n -> a.put(n) } } }
}

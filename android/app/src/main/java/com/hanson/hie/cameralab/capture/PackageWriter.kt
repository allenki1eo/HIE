package com.hanson.hie.cameralab.capture

import android.graphics.Bitmap
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.DngCreator
import android.media.Image
import android.os.Build
import com.hanson.hie.cameralab.BuildConfig
import com.hanson.hie.cameralab.CameraLabApp
import com.hanson.hie.cameralab.camera.FrameMeta
import com.hanson.hie.cameralab.camera.SessionInfo
import com.hanson.hie.cameralab.process.OnDeviceIsp
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream

class PackageWriter(
    private val store: ExperimentStore,
    private val session: SessionInfo,
    private val plan: BurstPlan,
    private val extraNotes: MutableList<String> = mutableListOf(),
) {
    val dir: File = store.nextPackage()
    private val frames = JSONArray()
    private var preview: Bitmap? = null
    private var stockWritten = false

    fun writeRaw(index: Int, image: Image, meta: FrameMeta) {
        val name = "frame_%03d.dng".format(index)
        val file = File(File(dir, "raw"), name)
        if (file.exists()) throw IllegalStateException("refusing to overwrite $file")
        FileOutputStream(file).use { out ->
            DngCreator(session.characteristics, meta.result).use { dng ->
                dng.setDescription("Hanson Camera Lab ${BuildConfig.VERSION_NAME} ${BuildConfig.GIT_COMMIT}")
                dng.writeImage(out, image)
            }
        }
        if (preview == null) {
            val black = session.characteristics.get(CameraCharacteristics.SENSOR_BLACK_LEVEL_PATTERN)
                ?.getOffsetForIndex(0, 0) ?: 64
            val white = session.characteristics.get(CameraCharacteristics.SENSOR_INFO_WHITE_LEVEL) ?: 1023
            val wb = meta.colorGains?.let { floatArrayOf(it[0], (it[1] + it[2]) * 0.5f, it[3]) } ?: floatArrayOf(1f, 1f, 1f)
            preview = try {
                OnDeviceIsp.preview(image, black, white, wb)
            } catch (e: Exception) {
                extraNotes.add("RAW preview failed: ${e.message}")
                null
            }
        }
        frames.put(frameJson("raw/$name", meta))
    }

    fun writeStockJpeg(image: Image, meta: FrameMeta) {
        val file = File(File(dir, "stock"), "reference.jpg")
        if (file.exists()) throw IllegalStateException("refusing to overwrite $file")
        val plane = image.planes[0].buffer
        val bytes = ByteArray(plane.remaining())
        plane.get(bytes)
        file.writeBytes(bytes)
        stockWritten = true
        File(dir, "stock_capture.json").takeIf { !it.exists() }?.writeText(frameJson("stock/reference.jpg", meta).toString(2))
    }

    fun finish(
        motionSamples: Int,
        motionInfo: Map<String, Any?>,
        gyroSyncNote: String?,
        notes: List<String>,
    ): File {
        val allNotes = (extraNotes + notes + listOfNotNull(gyroSyncNote)).toMutableList()
        val metadata = JSONObject()
            .put("schema", BuildConfig.PACKAGE_SCHEMA)
            .put("camera_id", session.cameraId)
            .put("raw_available", session.rawAvailable)
            .put("raw_size", session.rawSize?.let { JSONObject().put("w", it.width).put("h", it.height) })
            .put("timestamp_source", session.timestampSource)
            .put("frames", frames)
        store.writeJson(File(dir, "metadata.json"), metadata)

        val experiment = JSONObject()
            .put("schema", BuildConfig.PACKAGE_SCHEMA)
            .put("device", JSONObject(CameraLabApp.deviceInfo()))
            .put("app", JSONObject()
                .put("name", "Hanson Camera Lab")
                .put("version", BuildConfig.VERSION_NAME)
                .put("git_commit", BuildConfig.GIT_COMMIT)
                .put("application_id", BuildConfig.APPLICATION_ID))
            .put("capture_policy", JSONObject()
                .put("mode", plan.mode.name.lowercase())
                .put("frame_count", plan.frameCount)
                .put("ae_lock", plan.lockAe)
                .put("awb_lock", plan.lockAwb)
                .put("reason", plan.reason)
                .put("prior_art", "HDR+ constant-exposure burst / Night Sight time budget (reproduction)"))
            .put("session", JSONObject()
                .put("camera_id", session.cameraId)
                .put("raw_available", session.rawAvailable)
                .put("timestamp_source", session.timestampSource))
            .put("motion", JSONObject(motionInfo).put("sample_count", motionSamples))
            .put("stock_jpeg", stockWritten)
            .put("notes", JSONArray(allNotes))
        store.writeJson(File(dir, "experiment.json"), experiment)
        preview?.let { bmp ->
            val f = File(dir, "preview.jpg")
            if (!f.exists()) FileOutputStream(f).use { bmp.compress(Bitmap.CompressFormat.JPEG, 90, it) }
        }
        return dir
    }

    private fun frameJson(rel: String, meta: FrameMeta): JSONObject {
        val o = JSONObject()
            .put("file", rel)
            .put("sensor_timestamp_ns", meta.sensorTimestampNs)
            .put("exposure_time_ns", meta.exposureNs)
            .put("sensitivity", meta.sensitivity)
            .put("focal_length_mm", meta.focalLength)
            .put("focus_distance", meta.focusDistance)
            .put("lens_state", meta.lensState)
        meta.colorGains?.let {
            o.put("color_correction_gains", JSONArray().put(it[0]).put(it[1]).put(it[2]).put(it[3]))
        }
        meta.colorTransform?.let {
            val arr = JSONArray()
            for (v in it) arr.put(v.toDouble())
            o.put("color_correction_transform", arr)
        }
        if (Build.VERSION.SDK_INT >= 28) {
            val ois = meta.result.get(CaptureResult.STATISTICS_OIS_SAMPLES)
            if (ois != null) {
                val arr = JSONArray()
                for (s in ois) {
                    arr.put(JSONObject()
                        .put("timestamp_ns", s.timestamp)
                        .put("x_shift", s.xshift)
                        .put("y_shift", s.yshift))
                }
                o.put("ois_samples", arr)
            }
        }
        return o
    }
}

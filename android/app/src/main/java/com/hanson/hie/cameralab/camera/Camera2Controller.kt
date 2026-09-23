package com.hanson.hie.cameralab.camera

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.ImageFormat
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.media.Image
import android.media.ImageReader
import android.os.Handler
import android.os.HandlerThread
import android.util.Size
import android.view.Surface
import com.hanson.hie.cameralab.capture.BurstPlan
import com.hanson.hie.cameralab.capture.CaptureMode
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.abs

data class SessionInfo(
    val cameraId: String,
    val characteristics: CameraCharacteristics,
    val rawAvailable: Boolean,
    val rawSize: Size?,
    val jpegSize: Size?,
    val previewSize: Size,
    val timestampSource: String,
)

data class FrameMeta(
    val sensorTimestampNs: Long,
    val exposureNs: Long?,
    val sensitivity: Int?,
    val focalLength: Float?,
    val focusDistance: Float?,
    val lensState: Int?,
    val colorGains: FloatArray?,
    val result: TotalCaptureResult,
)

interface CaptureSink {
    fun onRaw(index: Int, image: Image, meta: FrameMeta)
    fun onJpeg(image: Image, meta: FrameMeta)
    fun onProgress(done: Int, total: Int)
    fun onComplete(notes: List<String>)
    fun onFailed(message: String)
}

class Camera2Controller(
    private val context: Context,
    private val listener: Listener,
) {
    interface Listener {
        fun onSession(info: SessionInfo)
        fun onMetering(iso: Int?, exposureNs: Long?, focal: Float?)
        fun onError(message: String)
    }

    private val mgr = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    private val thread = HandlerThread("hie-camera2").also { it.start() }
    private val handler = Handler(thread.looper)

    private var camera: CameraDevice? = null
    private var session: CameraCaptureSession? = null
    private var info: SessionInfo? = null
    private var previewSurface: Surface? = null
    private var rawReader: ImageReader? = null
    private var jpegReader: ImageReader? = null
    private var repeating: CaptureRequest.Builder? = null

    @Volatile private var capturing = false
    private var sink: CaptureSink? = null
    private var expectedRaw = 0
    private val rawDone = AtomicInteger(0)
    private val pendingRaw = ConcurrentHashMap<Long, Image>()
    private val pendingRawResult = ConcurrentHashMap<Long, FrameMeta>()
    private val pendingJpeg = ConcurrentHashMap<Long, Image>()
    private val pendingJpegResult = ConcurrentHashMap<Long, FrameMeta>()
    private var jpegExpected = false
    private var jpegDone = false
    private val notes = mutableListOf<String>()

    val sessionInfo: SessionInfo? get() = info
    val isCapturing: Boolean get() = capturing

    fun start(cameraId: String, preview: Surface, viewW: Int, viewH: Int) {
        handler.post {
            try {
                openLocked(cameraId, preview, viewW, viewH)
            } catch (e: Exception) {
                listener.onError(e.message ?: e.toString())
            }
        }
    }

    fun stop() {
        handler.post { closeLocked() }
    }

    fun release() {
        stop()
        thread.quitSafely()
    }

    fun tapToFocus(nx: Float, ny: Float) {
        handler.post {
            val i = info ?: return@post
            val builder = repeating ?: return@post
            val arr = i.characteristics.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE) ?: return@post
            val x = (arr.left + nx * arr.width()).toInt()
            val y = (arr.top + ny * arr.height()).toInt()
            val half = (arr.width() * 0.05f).toInt().coerceAtLeast(20)
            val region = android.hardware.camera2.params.MeteringRectangle(
                (x - half).coerceAtLeast(arr.left),
                (y - half).coerceAtLeast(arr.top),
                half * 2,
                half * 2,
                1,
            )
            builder.set(CaptureRequest.CONTROL_AF_REGIONS, arrayOf(region))
            builder.set(CaptureRequest.CONTROL_AE_REGIONS, arrayOf(region))
            builder.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_START)
            try {
                session?.capture(builder.build(), previewCallback, handler)
                builder.set(CaptureRequest.CONTROL_AF_TRIGGER, CaptureRequest.CONTROL_AF_TRIGGER_IDLE)
                session?.setRepeatingRequest(builder.build(), previewCallback, handler)
            } catch (e: CameraAccessException) {
                listener.onError(e.message ?: "AF failed")
            }
        }
    }

    fun capture(plan: BurstPlan, sink: CaptureSink) {
        handler.post {
            if (capturing) {
                sink.onFailed("capture already running")
                return@post
            }
            val sess = session
            val cam = camera
            val i = info
            if (sess == null || cam == null || i == null) {
                sink.onFailed("camera is not ready")
                return@post
            }
            this.sink = sink
            capturing = true
            rawDone.set(0)
            jpegDone = false
            pendingRaw.clear()
            pendingRawResult.clear()
            pendingJpeg.clear()
            pendingJpegResult.clear()
            notes.clear()
            expectedRaw = if (i.rawAvailable && plan.mode != CaptureMode.PHOTO) plan.frameCount
            else if (i.rawAvailable) 1 else 0
            jpegExpected = true
            if (!i.rawAvailable) notes.add("RAW_SENSOR unavailable; JPEG-only capture")
            if (expectedRaw == 0 && !jpegExpected) {
                finishCapture("nothing to capture")
                return@post
            }
            try {
                runCapture(sess, cam, i, plan)
            } catch (e: Exception) {
                finishCapture(e.message ?: e.toString())
            }
        }
    }

    @SuppressLint("MissingPermission")
    private fun openLocked(cameraId: String, preview: Surface, viewW: Int, viewH: Int) {
        closeLocked()
        previewSurface = preview
        val ch = mgr.getCameraCharacteristics(cameraId)
        val map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)
            ?: throw IllegalStateException("no stream map for camera $cameraId")
        val rawOk = CapabilityInspector.rawAvailable(ch)
        val rawSize = CapabilityInspector.largest(map, ImageFormat.RAW_SENSOR)
        val jpegSize = CapabilityInspector.largest(map, ImageFormat.JPEG)
            ?: Size(1920, 1080)
        val previewSize = choosePreview(map, viewW, viewH)
        val ts = ch.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE)
        val tsName = when (ts) {
            CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME -> "realtime"
            else -> "unknown"
        }
        if (rawOk && rawSize != null) {
            rawReader = ImageReader.newInstance(rawSize.width, rawSize.height, ImageFormat.RAW_SENSOR, 16)
            rawReader?.setOnImageAvailableListener({ reader -> drainRaw(reader) }, handler)
        }
        jpegReader = ImageReader.newInstance(jpegSize.width, jpegSize.height, ImageFormat.JPEG, 3)
        jpegReader?.setOnImageAvailableListener({ reader -> drainJpeg(reader) }, handler)

        info = SessionInfo(cameraId, ch, rawOk && rawSize != null, rawSize, jpegSize, previewSize, tsName)
        mgr.openCamera(cameraId, object : CameraDevice.StateCallback() {
            override fun onOpened(c: CameraDevice) {
                camera = c
                createSession(c)
            }
            override fun onDisconnected(c: CameraDevice) {
                listener.onError("camera disconnected")
                closeLocked()
            }
            override fun onError(c: CameraDevice, error: Int) {
                listener.onError("camera error $error")
                closeLocked()
            }
        }, handler)
    }

    private fun createSession(c: CameraDevice) {
        val surfaces = ArrayList<Surface>()
        previewSurface?.let { surfaces.add(it) }
        rawReader?.surface?.let { surfaces.add(it) }
        jpegReader?.surface?.let { surfaces.add(it) }
        try {
            @Suppress("DEPRECATION")
            c.createCaptureSession(surfaces, object : CameraCaptureSession.StateCallback() {
                override fun onConfigured(s: CameraCaptureSession) {
                    session = s
                    startRepeating(c, s)
                    info?.let { listener.onSession(it) }
                }
                override fun onConfigureFailed(s: CameraCaptureSession) {
                    if (rawReader != null) {
                        notes.add("session with RAW failed; retrying JPEG+preview")
                        rawReader?.close()
                        rawReader = null
                        info = info?.copy(rawAvailable = false, rawSize = null)
                        createSession(c)
                    } else {
                        listener.onError("failed to configure capture session")
                    }
                }
            }, handler)
        } catch (e: CameraAccessException) {
            listener.onError(e.message ?: "session error")
        }
    }

    private fun startRepeating(c: CameraDevice, s: CameraCaptureSession) {
        val preview = previewSurface ?: return
        val b = c.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
        b.addTarget(preview)
        b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
        b.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
        b.set(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_AUTO)
        repeating = b
        s.setRepeatingRequest(b.build(), previewCallback, handler)
    }

    private val previewCallback = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(
            session: CameraCaptureSession,
            request: CaptureRequest,
            result: TotalCaptureResult,
        ) {
            listener.onMetering(
                result.get(CaptureResult.SENSOR_SENSITIVITY),
                result.get(CaptureResult.SENSOR_EXPOSURE_TIME),
                result.get(CaptureResult.LENS_FOCAL_LENGTH),
            )
        }
    }

    private fun runCapture(
        sess: CameraCaptureSession,
        cam: CameraDevice,
        @Suppress("UNUSED_PARAMETER") _info: SessionInfo,
        plan: BurstPlan,
    ) {
        val preview = previewSurface
        if (plan.lockAe || plan.lockAwb) {
            val lock = cam.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
            preview?.let { lock.addTarget(it) }
            lock.set(CaptureRequest.CONTROL_AE_LOCK, plan.lockAe)
            lock.set(CaptureRequest.CONTROL_AWB_LOCK, plan.lockAwb)
            lock.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
            sess.setRepeatingRequest(lock.build(), previewCallback, handler)
            repeating = lock
        }

        val requests = ArrayList<CaptureRequest>()
        if (expectedRaw > 0) {
            repeat(expectedRaw) {
                val b = cam.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
                rawReader?.surface?.let { b.addTarget(it) }
                preview?.let { b.addTarget(it) }
                applyStill(b, plan)
                requests.add(b.build())
            }
            sess.captureBurst(requests, object : CameraCaptureSession.CaptureCallback() {
                override fun onCaptureCompleted(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    result: TotalCaptureResult,
                ) {
                    val meta = frameMeta(result)
                    pendingRawResult[meta.sensorTimestampNs] = meta
                    matchRaw()
                }

                override fun onCaptureFailed(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    failure: android.hardware.camera2.CaptureFailure,
                ) {
                    notes.add("RAW capture failed reason=${failure.reason}")
                    if (rawDone.incrementAndGet() >= expectedRaw) captureStockJpeg(sess, cam, plan)
                }
            }, handler)
        } else {
            captureStockJpeg(sess, cam, plan)
        }
        if (expectedRaw == 0) {
            // JPEG-only path already kicked off
        } else {
            // stock JPEG after the burst, as specified
            handler.postDelayed({
                if (capturing && rawDone.get() >= expectedRaw && !jpegDone) {
                    captureStockJpeg(sess, cam, plan)
                }
            }, 8_000)
        }
    }

    private fun captureStockJpeg(sess: CameraCaptureSession, cam: CameraDevice, plan: BurstPlan) {
        if (jpegDone) return
        val b = cam.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE)
        jpegReader?.surface?.let { b.addTarget(it) }
        previewSurface?.let { b.addTarget(it) }
        applyStill(b, plan.copy(lockAe = false, lockAwb = false))
        try {
            sess.capture(b.build(), object : CameraCaptureSession.CaptureCallback() {
                override fun onCaptureCompleted(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    result: TotalCaptureResult,
                ) {
                    pendingJpegResult[frameMeta(result).sensorTimestampNs] = frameMeta(result)
                    matchJpeg()
                }

                override fun onCaptureFailed(
                    session: CameraCaptureSession,
                    request: CaptureRequest,
                    failure: android.hardware.camera2.CaptureFailure,
                ) {
                    notes.add("stock JPEG failed reason=${failure.reason}")
                    jpegDone = true
                    maybeFinish()
                }
            }, handler)
        } catch (e: CameraAccessException) {
            notes.add("stock JPEG: ${e.message}")
            jpegDone = true
            maybeFinish()
        }
    }

    private fun applyStill(b: CaptureRequest.Builder, plan: BurstPlan) {
        b.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
        if (plan.lockAe) b.set(CaptureRequest.CONTROL_AE_LOCK, true)
        if (plan.lockAwb) b.set(CaptureRequest.CONTROL_AWB_LOCK, true)
        info?.let {
            if (it.rawAvailable) {
                b.set(CaptureRequest.STATISTICS_LENS_SHADING_MAP_MODE, CaptureRequest.STATISTICS_LENS_SHADING_MAP_MODE_ON)
            }
        }
    }

    private fun drainRaw(reader: ImageReader) {
        while (true) {
            val img = reader.acquireNextImage() ?: break
            pendingRaw[img.timestamp] = img
            matchRaw()
        }
    }

    private fun drainJpeg(reader: ImageReader) {
        while (true) {
            val img = reader.acquireNextImage() ?: break
            pendingJpeg[img.timestamp] = img
            matchJpeg()
        }
    }

    private fun matchRaw() {
        val keys = pendingRaw.keys.intersect(pendingRawResult.keys)
        for (ts in keys) {
            val img = pendingRaw.remove(ts) ?: continue
            val meta = pendingRawResult.remove(ts)
            if (meta == null) {
                img.close()
                continue
            }
            val idx = rawDone.getAndIncrement()
            try {
                sink?.onRaw(idx, img, meta)
            } finally {
                img.close()
            }
            sink?.onProgress(rawDone.get(), expectedRaw + 1)
            if (rawDone.get() >= expectedRaw) {
                val sess = session
                val cam = camera
                val plan = BurstPlan(CaptureMode.BURST, expectedRaw, lockAe = true, lockAwb = true, reason = "")
                if (sess != null && cam != null) captureStockJpeg(sess, cam, plan)
            }
        }
        maybeFinish()
    }

    private fun matchJpeg() {
        val keys = pendingJpeg.keys.toList()
        if (keys.isEmpty()) return
        val results = pendingJpegResult
        for (ts in keys) {
            val meta = results[ts] ?: nearest(results, ts) ?: continue
            val img = pendingJpeg.remove(ts) ?: continue
            results.remove(meta.sensorTimestampNs)
            try {
                sink?.onJpeg(img, meta)
            } finally {
                img.close()
            }
            jpegDone = true
            sink?.onProgress(expectedRaw + 1, expectedRaw + 1)
            maybeFinish()
            return
        }
    }

    private fun nearest(map: ConcurrentHashMap<Long, FrameMeta>, ts: Long): FrameMeta? {
        var best: FrameMeta? = null
        var bestD = Long.MAX_VALUE
        for ((k, v) in map) {
            val d = abs(k - ts)
            if (d < bestD) {
                bestD = d
                best = v
            }
        }
        return if (bestD < 50_000_000L) best else null
    }

    private fun maybeFinish() {
        if (!capturing) return
        val rawOk = expectedRaw == 0 || rawDone.get() >= expectedRaw
        if (rawOk && jpegDone) finishCapture(null)
    }

    private fun finishCapture(error: String?) {
        if (!capturing && error == null) return
        capturing = false
        pendingRaw.values.forEach { it.close() }
        pendingJpeg.values.forEach { it.close() }
        pendingRaw.clear()
        pendingJpeg.clear()
        val s = sink
        sink = null
        if (error != null) s?.onFailed(error) else s?.onComplete(notes.toList())
        // unlock AE/AWB
        camera?.let { cam ->
            session?.let { sess ->
                try {
                    startRepeating(cam, sess)
                } catch (_: Exception) {
                }
            }
        }
    }

    private fun frameMeta(result: TotalCaptureResult): FrameMeta {
        val gains = result.get(CaptureResult.COLOR_CORRECTION_GAINS)
        return FrameMeta(
            sensorTimestampNs = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: 0L,
            exposureNs = result.get(CaptureResult.SENSOR_EXPOSURE_TIME),
            sensitivity = result.get(CaptureResult.SENSOR_SENSITIVITY),
            focalLength = result.get(CaptureResult.LENS_FOCAL_LENGTH),
            focusDistance = result.get(CaptureResult.LENS_FOCUS_DISTANCE),
            lensState = result.get(CaptureResult.LENS_STATE),
            colorGains = gains?.let { floatArrayOf(it.red, it.greenEven, it.greenOdd, it.blue) },
            result = result,
        )
    }

    private fun choosePreview(map: android.hardware.camera2.params.StreamConfigurationMap, vw: Int, vh: Int): Size {
        val target = if (vw > 0 && vh > 0) vw.toLong() * vh else 1280L * 720
        val sizes = map.getOutputSizes(Surface::class.java) ?: map.getOutputSizes(ImageFormat.PRIVATE) ?: emptyArray()
        return sizes.minByOrNull { abs(it.width.toLong() * it.height - target) } ?: Size(1280, 720)
    }

    private fun closeLocked() {
        capturing = false
        try { session?.close() } catch (_: Exception) {}
        session = null
        try { camera?.close() } catch (_: Exception) {}
        camera = null
        rawReader?.close(); rawReader = null
        jpegReader?.close(); jpegReader = null
        repeating = null
    }
}

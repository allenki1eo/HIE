package com.hanson.hie.cameralab

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.hardware.camera2.CameraManager
import android.os.Bundle
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.hanson.hie.cameralab.camera.Camera2Controller
import com.hanson.hie.cameralab.camera.CapabilityInspector
import com.hanson.hie.cameralab.camera.CaptureSink
import com.hanson.hie.cameralab.camera.FrameMeta
import com.hanson.hie.cameralab.camera.SessionInfo
import com.hanson.hie.cameralab.capture.BurstPlan
import com.hanson.hie.cameralab.capture.BurstPolicy
import com.hanson.hie.cameralab.capture.CaptureMode
import com.hanson.hie.cameralab.capture.PackageWriter
import com.hanson.hie.cameralab.process.HieProcessor
import com.hanson.hie.cameralab.sensors.MotionLogger
import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.Executors
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import android.media.Image

class MainActivity : AppCompatActivity(), Camera2Controller.Listener {
    private lateinit var preview: android.view.SurfaceView
    private lateinit var meter: android.widget.TextView
    private lateinit var status: android.widget.TextView
    private lateinit var progress: android.widget.TextView
    private lateinit var sheet: android.view.View
    private lateinit var sheetTitle: android.widget.TextView
    private lateinit var sheetBody: android.widget.TextView
    private lateinit var sheetAction: android.widget.TextView
    private lateinit var sheetImage: android.widget.ImageView
    private lateinit var thumb: android.widget.ImageView
    private lateinit var modePhoto: android.widget.TextView
    private lateinit var modeBurst: android.widget.TextView
    private lateinit var modeNight: android.widget.TextView

    private lateinit var camera: Camera2Controller
    private lateinit var motion: MotionLogger
    private var mode = CaptureMode.BURST
    private var cameraId: String? = null
    private var lastIso: Int? = null
    private var lastExp: Long? = null
    private var lastFocal: Float? = null
    private var surfaceReady = false
    private var writer: PackageWriter? = null
    private var firstRawTs: Long? = null
    private var firstGyroTs: Long? = null
    private val rawCopies = mutableListOf<HieProcessor.RawCopy>()
    private val hieExec = Executors.newSingleThreadExecutor()
    private var lastHieJpeg: File? = null

    private val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) startPreview() else toast(getString(R.string.permission_required))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        preview = findViewById(R.id.preview)
        meter = findViewById(R.id.meter)
        status = findViewById(R.id.status)
        progress = findViewById(R.id.progress)
        sheet = findViewById(R.id.sheet)
        sheetTitle = findViewById(R.id.sheetTitle)
        sheetBody = findViewById(R.id.sheetBody)
        sheetAction = findViewById(R.id.sheetAction)
        sheetImage = findViewById(R.id.sheetImage)
        thumb = findViewById(R.id.thumb)
        modePhoto = findViewById(R.id.modePhoto)
        modeBurst = findViewById(R.id.modeBurst)
        modeNight = findViewById(R.id.modeNight)

        camera = Camera2Controller(this, this)
        motion = MotionLogger(this)
        cameraId = CapabilityInspector.chooseBackCameraId(this)

        findViewById<View>(R.id.shutter).setOnClickListener { onShutter() }
        findViewById<View>(R.id.btnInspector).setOnClickListener { showInspector() }
        findViewById<View>(R.id.btnExperiments).setOnClickListener { showExperiments() }
        findViewById<View>(R.id.sheetBack).setOnClickListener { sheet.visibility = View.GONE }
        findViewById<View>(R.id.btnSwitch).setOnClickListener { switchCamera() }
        thumb.setOnClickListener { showExperiments() }
        modePhoto.setOnClickListener { setMode(CaptureMode.PHOTO) }
        modeBurst.setOnClickListener { setMode(CaptureMode.BURST) }
        modeNight.setOnClickListener { setMode(CaptureMode.NIGHT) }

        preview.setOnTouchListener { v, e ->
            if (e.action == MotionEvent.ACTION_UP && v.width > 0 && v.height > 0) {
                camera.tapToFocus(e.x / v.width, e.y / v.height)
                v.performClick()
            }
            true
        }

        preview.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                surfaceReady = true
                startPreview()
            }
            override fun surfaceChanged(holder: SurfaceHolder, format: Int, w: Int, h: Int) {
                if (surfaceReady) startPreview()
            }
            override fun surfaceDestroyed(holder: SurfaceHolder) {
                surfaceReady = false
                camera.stop()
            }
        })
        refreshThumb()
    }

    override fun onResume() {
        super.onResume()
        if (surfaceReady) startPreview()
    }

    override fun onPause() {
        camera.stop()
        motion.stop()
        super.onPause()
    }

    override fun onDestroy() {
        camera.release()
        hieExec.shutdownNow()
        super.onDestroy()
    }

    private fun startPreview() {
        if (!surfaceReady) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            askCamera.launch(Manifest.permission.CAMERA)
            return
        }
        val id = cameraId ?: CapabilityInspector.chooseBackCameraId(this) ?: run {
            status.text = "No camera"
            return
        }
        cameraId = id
        camera.start(id, preview.holder.surface, preview.width, preview.height)
    }

    private fun switchCamera() {
        val mgr = getSystemService(CAMERA_SERVICE) as CameraManager
        val ids = mgr.cameraIdList
        if (ids.isEmpty()) return
        val idx = ids.indexOf(cameraId).let { if (it < 0) 0 else it }
        cameraId = ids[(idx + 1) % ids.size]
        startPreview()
    }

    private fun setMode(m: CaptureMode) {
        mode = m
        val accent = ContextCompat.getColor(this, R.color.lab_accent)
        val muted = ContextCompat.getColor(this, R.color.lab_muted)
        modePhoto.setTextColor(if (m == CaptureMode.PHOTO) accent else muted)
        modeBurst.setTextColor(if (m == CaptureMode.BURST) accent else muted)
        modeNight.setTextColor(if (m == CaptureMode.NIGHT) accent else muted)
        updateMeter()
    }

    override fun onSession(info: SessionInfo) {
        runOnUiThread {
            val raw = if (info.rawAvailable) "RAW ${info.rawSize?.width}×${info.rawSize?.height}" else "no RAW"
            status.text = "cam ${info.cameraId} · $raw · ts=${info.timestampSource} · gyro=${motion.gyroAvailable}"
            if (!info.rawAvailable && mode != CaptureMode.PHOTO) {
                toast(getString(R.string.no_raw))
            }
            updateMeter()
        }
    }

    override fun onMetering(iso: Int?, exposureNs: Long?, focal: Float?) {
        lastIso = iso
        lastExp = exposureNs
        lastFocal = focal
        runOnUiThread { updateMeter() }
    }

    override fun onError(message: String) {
        runOnUiThread {
            status.text = message
            toast(message)
        }
    }

    private fun updateMeter() {
        val expMs = lastExp?.let { it / 1_000_000.0 }
        val plan = currentPlan()
        meter.text = "ISO ${lastIso ?: "—"}   ${expMs?.let { "%.1f ms".format(it) } ?: "—"}   " +
            "f ${lastFocal ?: "—"}   ${mode.name} ×${plan.frameCount}\n" +
            plan.reason
    }

    private fun currentPlan(): BurstPlan {
        val raw = camera.sessionInfo?.rawAvailable == true
        return BurstPolicy.plan(mode, lastIso, lastExp, raw)
    }

    private fun onShutter() {
        if (camera.isCapturing) return
        val info = camera.sessionInfo ?: run {
            toast("Camera not ready")
            return
        }
        val plan = currentPlan()
        val store = (application as CameraLabApp).experiments
        val pw = try {
            PackageWriter(store, info, plan)
        } catch (e: Exception) {
            toast(e.message ?: "package")
            return
        }
        writer = pw
        firstRawTs = null
        firstGyroTs = null
        rawCopies.clear()
        motion.start()
        progress.visibility = View.VISIBLE
        progress.text = "Capturing 0/${plan.frameCount}"
        val processor = HieProcessor(this, store)
        camera.capture(plan, object : CaptureSink {
            override fun onRaw(index: Int, image: Image, meta: FrameMeta) {
                if (firstRawTs == null) firstRawTs = meta.sensorTimestampNs
                try {
                    rawCopies.add(processor.copyRaw(image, meta))
                } catch (e: Exception) {
                    // DNG still written; HIE may run with fewer copies
                }
                pw.writeRaw(index, image, meta)
            }

            override fun onJpeg(image: Image, meta: FrameMeta) {
                pw.writeStockJpeg(image, meta)
            }

            override fun onProgress(done: Int, total: Int) {
                runOnUiThread { progress.text = "Capturing $done/$total" }
            }

            override fun onComplete(notes: List<String>) {
                finishPackage(pw, info, notes)
            }

            override fun onFailed(message: String) {
                motion.stop()
                runOnUiThread {
                    progress.visibility = View.GONE
                    toast(message)
                }
            }
        })
    }

    private fun finishPackage(pw: PackageWriter, info: SessionInfo, notes: List<String>) {
        val samples = motion.stop()
        val csv = File(pw.dir, "motion/sensors.csv")
        val count = try {
            motion.writeCsv(csv)
        } catch (_: Exception) {
            0
        }
        val sync = when {
            info.timestampSource == "realtime" && firstRawTs != null ->
                "SENSOR_INFO_TIMESTAMP_SOURCE=realtime: camera and SensorEvent.timestamp share the boottime clock. first_raw_ts=$firstRawTs"
            info.timestampSource != "realtime" ->
                "SENSOR_INFO_TIMESTAMP_SOURCE=${info.timestampSource}: do not assume gyro and frames share a clock; measure offset before any gyro prior (Karpenko 2011)."
            else -> null
        }
        try {
            pw.finish(count.coerceAtLeast(samples), motion.sensorInfo(), sync, notes)
        } catch (e: Exception) {
            runOnUiThread { toast(e.message ?: "finish") }
        }
        val copies = rawCopies.toList()
        rawCopies.clear()
        runOnUiThread {
            status.text = "saved ${pw.dir.name}  (${File(pw.dir, "raw").list()?.size ?: 0} DNG)"
            refreshThumb()
        }
        if (copies.isNotEmpty()) {
            runOnUiThread {
                progress.visibility = View.VISIBLE
                progress.text = getString(R.string.hie_merge)
            }
            hieExec.execute {
                try {
                    val processor = HieProcessor(this, (application as CameraLabApp).experiments)
                    val result = processor.process(pw.dir, info, copies)
                    lastHieJpeg = result.jpeg
                    runOnUiThread {
                        progress.visibility = View.GONE
                        status.text = "HIE ${pw.dir.name}  ${result.width}×${result.height}"
                        refreshThumb()
                        showHieResult(result)
                        toast("HIE JPEG ${pw.dir.name}")
                    }
                } catch (e: Exception) {
                    runOnUiThread {
                        progress.visibility = View.GONE
                        status.text = "HIE failed: ${e.message}"
                        toast(e.message ?: "HIE failed")
                    }
                }
            }
        } else {
            runOnUiThread {
                progress.visibility = View.GONE
                toast("Saved ${pw.dir.name}")
            }
        }
        writer = null
    }

    private fun showHieResult(result: HieProcessor.Result) {
        sheetImage.visibility = View.VISIBLE
        sheetImage.setImageBitmap(BitmapFactory.decodeFile(result.jpeg.absolutePath))
        sheetTitle.text = getString(R.string.hie_jpeg)
        val gallery = result.galleryUri?.let { "\ngallery $it" } ?: ""
        sheetBody.text = "hie/output.jpg  ${result.width}×${result.height}\n" +
            result.processJson + gallery
        sheetAction.text = getString(R.string.share_hie)
        sheetAction.setOnClickListener { shareFile(result.jpeg, "image/jpeg") }
        sheet.visibility = View.VISIBLE
    }

    private fun showInspector() {
        val json = CapabilityInspector.dumpAll(this)
        val export = File(filesDir, "exports").apply { mkdirs() }
        val out = File(export, "capabilities.json")
        out.writeText(json.toString(2))
        sheetImage.visibility = View.GONE
        sheetTitle.text = "Capability inspector"
        sheetBody.text = json.toString(2)
        sheetAction.text = getString(R.string.export_json)
        sheetAction.setOnClickListener { shareFile(out, "application/json") }
        sheet.visibility = View.VISIBLE
    }

    private fun showExperiments() {
        val store = (application as CameraLabApp).experiments
        val pkgs = store.list()
        val sb = StringBuilder()
        if (pkgs.isEmpty()) sb.append("No packages yet. Capture a burst.\n")
        for (p in pkgs) {
            val exp = File(p, "experiment.json")
            val n = File(p, "raw").list()?.size ?: 0
            val hie = File(p, "hie/output.jpg").exists()
            sb.append(p.name).append("  raw=").append(n)
            if (hie) sb.append("  hie")
            if (exp.exists()) {
                try {
                    val o = JSONObject(exp.readText())
                    sb.append("  ").append(o.optJSONObject("capture_policy")?.optString("mode"))
                } catch (_: Exception) {
                }
            }
            sb.append('\n')
        }
        sb.append("\nOn-device HIE writes hie/output.jpg after each RAW burst.\n")
        sb.append("Pull with:\nadb pull ")
        sb.append(store.list().firstOrNull()?.parent ?: filesDir.resolve("experiments").absolutePath)
        sb.append("\nWorkstation check: hie process <folder> -p hie_v0.1\n")
        sheetImage.visibility = View.GONE
        sheetTitle.text = "Experiments"
        sheetBody.text = sb.toString()
        val latest = pkgs.firstOrNull()
        val latestHie = latest?.let { File(it, "hie/output.jpg") }?.takeIf { it.exists() }
        if (latestHie != null) {
            sheetImage.visibility = View.VISIBLE
            sheetImage.setImageBitmap(BitmapFactory.decodeFile(latestHie.absolutePath))
        }
        sheetAction.text = if (latest != null) getString(R.string.share_package) else ""
        sheetAction.setOnClickListener {
            if (latest != null) shareZip(latest)
        }
        sheet.visibility = View.VISIBLE
    }

    private fun refreshThumb() {
        val latest = (application as CameraLabApp).experiments.list().firstOrNull() ?: return
        val jpg = listOf(
            File(latest, "hie/output.jpg"),
            lastHieJpeg,
            File(latest, "stock/reference.jpg"),
            File(latest, "preview.jpg"),
        ).firstOrNull { it != null && it.exists() }
        if (jpg != null) {
            thumb.setImageBitmap(BitmapFactory.decodeFile(jpg.absolutePath))
        }
    }

    private fun shareZip(dir: File) {
        val zip = File(cacheDir.resolve("shared").apply { mkdirs() }, "${dir.name}.zip")
        ZipOutputStream(BufferedOutputStream(FileOutputStream(zip))).use { zos ->
            dir.walkTopDown().filter { it.isFile }.forEach { f ->
                val rel = f.relativeTo(dir).path
                zos.putNextEntry(ZipEntry(rel))
                f.inputStream().use { it.copyTo(zos) }
                zos.closeEntry()
            }
        }
        shareFile(zip, "application/zip")
    }

    private fun shareFile(file: File, type: String) {
        val uri = FileProvider.getUriForFile(this, "${BuildConfig.APPLICATION_ID}.files", file)
        val intent = Intent(Intent.ACTION_SEND).setType(type).putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(intent, file.name))
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
}

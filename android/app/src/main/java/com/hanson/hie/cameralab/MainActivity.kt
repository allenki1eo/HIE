package com.hanson.hie.cameralab

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.hardware.camera2.CameraManager
import android.media.Image
import android.os.Build
import android.os.Bundle
import android.view.Gravity
import android.view.MotionEvent
import android.view.SurfaceHolder
import android.view.View
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.hanson.hie.cameralab.camera.Camera2Controller
import com.hanson.hie.cameralab.camera.CapabilityInspector
import com.hanson.hie.cameralab.camera.CaptureSink
import com.hanson.hie.cameralab.camera.FrameMeta
import com.hanson.hie.cameralab.camera.PreviewAspect
import com.hanson.hie.cameralab.camera.SessionInfo
import com.hanson.hie.cameralab.capture.BurstPlan
import com.hanson.hie.cameralab.capture.BurstPolicy
import com.hanson.hie.cameralab.capture.CaptureMode
import com.hanson.hie.cameralab.capture.PackageWriter
import com.hanson.hie.cameralab.process.GalleryStore
import com.hanson.hie.cameralab.process.HieProcessor
import com.hanson.hie.cameralab.sensors.MotionLogger
import java.io.BufferedOutputStream
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.Executors
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class MainActivity : AppCompatActivity(), Camera2Controller.Listener {
    private lateinit var root: View
    private lateinit var preview: android.view.SurfaceView
    private lateinit var progress: android.widget.TextView
    private lateinit var sheet: android.view.View
    private lateinit var sheetTitle: android.widget.TextView
    private lateinit var sheetBody: android.widget.TextView
    private lateinit var sheetAction: android.widget.TextView
    private lateinit var sheetImage: android.widget.ImageView
    private lateinit var sheetCaption: android.widget.TextView
    private lateinit var sheetLabScroll: android.view.View
    private lateinit var compareRow: android.view.View
    private lateinit var compareHie: android.widget.TextView
    private lateinit var comparePhone: android.widget.TextView
    private lateinit var thumb: android.widget.ImageView
    private lateinit var modePhoto: android.widget.TextView
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
    private var lastStockJpeg: File? = null
    private var reviewHie: File? = null
    private var reviewStock: File? = null
    private var showingHie = true

    private val askCamera = registerForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) startPreview() else toast(getString(R.string.permission_required))
    }
    private val askStorage = registerForActivityResult(ActivityResultContracts.RequestPermission()) { /* gallery insert still attempted */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        root = findViewById(R.id.root)
        preview = findViewById(R.id.preview)
        progress = findViewById(R.id.progress)
        sheet = findViewById(R.id.sheet)
        sheetTitle = findViewById(R.id.sheetTitle)
        sheetBody = findViewById(R.id.sheetBody)
        sheetAction = findViewById(R.id.sheetAction)
        sheetImage = findViewById(R.id.sheetImage)
        sheetCaption = findViewById(R.id.sheetCaption)
        sheetLabScroll = findViewById(R.id.sheetLabScroll)
        compareRow = findViewById(R.id.compareRow)
        compareHie = findViewById(R.id.compareHie)
        comparePhone = findViewById(R.id.comparePhone)
        thumb = findViewById(R.id.thumb)
        modePhoto = findViewById(R.id.modePhoto)
        modeNight = findViewById(R.id.modeNight)

        camera = Camera2Controller(this, this)
        motion = MotionLogger(this)
        cameraId = CapabilityInspector.chooseBackCameraId(this)

        findViewById<View>(R.id.shutter).setOnClickListener { onShutter() }
        findViewById<View>(R.id.sheetBack).setOnClickListener { sheet.visibility = View.GONE }
        findViewById<View>(R.id.btnSwitch).setOnClickListener { switchCamera() }
        findViewById<View>(R.id.title).setOnLongClickListener {
            showLab()
            true
        }
        thumb.setOnClickListener { showLastPhoto() }
        modePhoto.setOnClickListener { setMode(CaptureMode.BURST) }
        modeNight.setOnClickListener { setMode(CaptureMode.NIGHT) }
        compareHie.setOnClickListener { showReview(true) }
        comparePhone.setOnClickListener { showReview(false) }

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
                // Letterbox resizes the view; do not reopen the camera here.
            }
            override fun surfaceDestroyed(holder: SurfaceHolder) {
                surfaceReady = false
                camera.stop()
            }
        })
        askGalleryPermission()
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
            toast("No camera")
            return
        }
        cameraId = id
        camera.start(id, preview.holder.surface, preview.width, preview.height)
    }

    private fun askGalleryPermission() {
        if (Build.VERSION.SDK_INT >= 29) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            askStorage.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
        }
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
        modePhoto.setTextColor(if (m == CaptureMode.BURST) accent else muted)
        modePhoto.setTypeface(null, if (m == CaptureMode.BURST) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
        modeNight.setTextColor(if (m == CaptureMode.NIGHT) accent else muted)
        modeNight.setTypeface(null, if (m == CaptureMode.NIGHT) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
    }

    override fun onSession(info: SessionInfo) {
        runOnUiThread {
            applyLetterbox(info)
            if (!info.rawAvailable && mode != CaptureMode.PHOTO) {
                toast(getString(R.string.no_raw))
            }
        }
    }

    private fun applyLetterbox(info: SessionInfo) {
        val pw = root.width
        val ph = root.height
        if (pw <= 0 || ph <= 0) {
            root.post { if (root.width > 0) applyLetterbox(info) }
            return
        }
        val box = PreviewAspect.letterbox(
            pw, ph, info.previewSize.width, info.previewSize.height, info.sensorOrientation,
        )
        val lp = preview.layoutParams as FrameLayout.LayoutParams
        if (lp.width == box.width && lp.height == box.height) return
        lp.width = box.width
        lp.height = box.height
        lp.gravity = Gravity.CENTER
        preview.layoutParams = lp
    }

    override fun onMetering(iso: Int?, exposureNs: Long?, focal: Float?) {
        lastIso = iso
        lastExp = exposureNs
        lastFocal = focal
    }

    override fun onError(message: String) {
        runOnUiThread { toast(message) }
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
        progress.text = getString(R.string.capturing)
        val processor = HieProcessor(this, store)
        camera.capture(plan, object : CaptureSink {
            override fun onRaw(index: Int, image: Image, meta: FrameMeta) {
                if (firstRawTs == null) firstRawTs = meta.sensorTimestampNs
                try {
                    rawCopies.add(processor.copyRaw(image, meta))
                } catch (_: Exception) {
                }
                pw.writeRaw(index, image, meta)
            }

            override fun onJpeg(image: Image, meta: FrameMeta) {
                pw.writeStockJpeg(image, meta)
            }

            override fun onProgress(done: Int, total: Int) {
                runOnUiThread { progress.text = getString(R.string.capturing) }
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
        lastStockJpeg = File(pw.dir, "stock/reference.jpg").takeIf { it.exists() }
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
                    val gallery = result.galleryUri ?: GalleryStore.saveJpeg(this, result.jpeg)
                    runOnUiThread {
                        progress.visibility = View.GONE
                        refreshThumb()
                        showPhoto(result.jpeg, lastStockJpeg, result.width, result.height, gallery != null)
                    }
                } catch (e: Exception) {
                    val stock = lastStockJpeg
                    val gallery = stock?.let { GalleryStore.saveJpeg(this, it) }
                    runOnUiThread {
                        progress.visibility = View.GONE
                        refreshThumb()
                        if (stock != null) {
                            showPhoto(stock, null, null, null, gallery != null)
                        } else {
                            toast(e.message ?: "Could not finish photo")
                        }
                    }
                }
            }
        } else {
            val stock = lastStockJpeg
            val gallery = stock?.let { GalleryStore.saveJpeg(this, it) }
            runOnUiThread {
                progress.visibility = View.GONE
                refreshThumb()
                if (stock != null) {
                    showPhoto(stock, null, null, null, gallery != null)
                } else {
                    toast("Saved")
                }
            }
        }
        writer = null
    }

    private fun showPhoto(hie: File, stock: File?, width: Int?, height: Int?, inGallery: Boolean) {
        reviewHie = hie
        reviewStock = stock?.takeIf { it.exists() && it.absolutePath != hie.absolutePath }
        showingHie = true
        sheetLabScroll.visibility = View.GONE
        sheetImage.visibility = View.VISIBLE
        sheetCaption.visibility = View.VISIBLE
        compareRow.visibility = if (reviewStock != null) View.VISIBLE else View.GONE
        sheetTitle.text = getString(R.string.hie_jpeg)
        sheetAction.text = getString(R.string.share)
        sheetAction.setOnClickListener {
            val file = if (showingHie) reviewHie else reviewStock
            if (file != null) shareFile(file, "image/jpeg")
        }
        showReview(true)
        val size = if (width != null && height != null) getString(R.string.size_caption, width, height) else photoSize(hie)
        val gallery = if (inGallery) getString(R.string.saved_gallery) else getString(R.string.saved_gallery_failed)
        sheetCaption.text = "$size\n$gallery"
        sheet.visibility = View.VISIBLE
        toast(if (inGallery) getString(R.string.saved_gallery) else getString(R.string.saved_gallery_failed))
    }

    private fun showReview(hie: Boolean) {
        showingHie = hie
        val file = if (hie) reviewHie else reviewStock
        if (file != null) {
            sheetImage.setImageBitmap(decodeForView(file))
            val extra = photoSize(file)
            val galleryLine = sheetCaption.text.toString().substringAfter('\n', "")
            sheetCaption.text = if (galleryLine.isNotEmpty()) "$extra\n$galleryLine" else extra
        }
        val accent = ContextCompat.getColor(this, R.color.lab_accent)
        val muted = ContextCompat.getColor(this, R.color.lab_muted)
        compareHie.setTextColor(if (hie) accent else muted)
        comparePhone.setTextColor(if (!hie) accent else muted)
    }

    private fun showLastPhoto() {
        val latest = (application as CameraLabApp).experiments.list().firstOrNull() ?: return
        val hie = File(latest, "hie/output.jpg").takeIf { it.exists() } ?: lastHieJpeg
        val stock = File(latest, "stock/reference.jpg").takeIf { it.exists() } ?: lastStockJpeg
        val main = hie ?: stock ?: return
        showPhoto(main, stock, null, null, true)
    }

    private fun showLab() {
        sheetImage.visibility = View.GONE
        compareRow.visibility = View.GONE
        sheetCaption.visibility = View.GONE
        sheetLabScroll.visibility = View.VISIBLE
        val store = (application as CameraLabApp).experiments
        val json = CapabilityInspector.dumpAll(this)
        val sb = StringBuilder()
        sb.append("Long-press title for this lab page.\n\n")
        for (p in store.list()) {
            val n = File(p, "raw").list()?.size ?: 0
            sb.append(p.name).append("  raw=").append(n)
            if (File(p, "hie/output.jpg").exists()) sb.append("  hie")
            sb.append('\n')
        }
        sb.append('\n').append(json.toString(2))
        sheetTitle.text = getString(R.string.experiments)
        sheetBody.text = sb.toString()
        val latest = store.list().firstOrNull()
        sheetAction.text = if (latest != null) getString(R.string.share_package) else ""
        sheetAction.setOnClickListener { if (latest != null) shareZip(latest) }
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
            thumb.setImageBitmap(decodeForView(jpg, 256))
        }
    }

    private fun photoSize(file: File): String {
        val opt = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, opt)
        return if (opt.outWidth > 0) getString(R.string.size_caption, opt.outWidth, opt.outHeight) else file.name
    }

    private fun decodeForView(file: File, maxSide: Int = 2048): android.graphics.Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        val w = bounds.outWidth.coerceAtLeast(1)
        val h = bounds.outHeight.coerceAtLeast(1)
        var sample = 1
        while (w / sample > maxSide || h / sample > maxSide) sample *= 2
        val opts = BitmapFactory.Options().apply { inSampleSize = sample }
        return BitmapFactory.decodeFile(file.absolutePath, opts)
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

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
}

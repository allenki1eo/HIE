package com.hanson.hie.cameralab.sensors

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.Build
import java.io.File
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Gyroscope + accelerometer at the highest available rate.
 *
 * Camera2 SENSOR_INFO_TIMESTAMP_SOURCE_REALTIME uses the same clock as
 * SensorEvent.timestamp (elapsed realtime / boottime). UNKNOWN means we must
 * measure the offset instead of assuming it — that offset is recorded in the
 * package, not guessed.
 */
class MotionLogger(context: Context) : SensorEventListener {
    private val mgr = context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val gyro = mgr.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
    private val accel = mgr.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
    private val running = AtomicBoolean(false)
    private val lock = Any()
    private val rows = ArrayList<String>(4096)

    val gyroAvailable: Boolean get() = gyro != null
    val accelAvailable: Boolean get() = accel != null

    fun start() {
        if (!running.compareAndSet(false, true)) return
        synchronized(lock) { rows.clear() }
        val rate = SensorManager.SENSOR_DELAY_FASTEST
        gyro?.let { mgr.registerListener(this, it, rate) }
        accel?.let { mgr.registerListener(this, it, rate) }
    }

    fun stop(): Int {
        if (!running.compareAndSet(true, false)) return sampleCount()
        mgr.unregisterListener(this)
        return sampleCount()
    }

    fun sampleCount(): Int = synchronized(lock) { rows.size }

    fun writeCsv(file: File): Int {
        file.parentFile?.mkdirs()
        if (file.exists()) throw IllegalStateException("refusing to overwrite $file")
        val copy = synchronized(lock) { rows.toList() }
        file.printWriter().use { out ->
            out.println("t_ns,sensor,x,y,z,accuracy")
            copy.forEach { out.println(it) }
        }
        return copy.size
    }

    fun sensorInfo(): Map<String, Any?> = mapOf(
        "gyro_name" to gyro?.name,
        "gyro_vendor" to gyro?.vendor,
        "gyro_min_delay_us" to gyro?.minDelay,
        "accel_name" to accel?.name,
        "accel_min_delay_us" to accel?.minDelay,
        "android_sensor_clock" to "elapsed_realtime_nanos",
        "high_sampling_rate_permission" to (Build.VERSION.SDK_INT < 31),
    )

    override fun onSensorChanged(event: SensorEvent) {
        if (!running.get()) return
        val name = when (event.sensor.type) {
            Sensor.TYPE_GYROSCOPE -> "gyro"
            Sensor.TYPE_ACCELEROMETER -> "accel"
            else -> return
        }
        val v = event.values
        val line = "${event.timestamp},$name,${v[0]},${v[1]},${v[2]},${event.accuracy}"
        synchronized(lock) { rows.add(line) }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) = Unit
}

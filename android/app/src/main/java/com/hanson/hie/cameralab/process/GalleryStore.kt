package com.hanson.hie.cameralab.process

import android.content.ContentValues
import android.content.Context
import android.os.Build
import android.provider.MediaStore
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Insert a finished JPEG into the device gallery (DCIM/Hanson).
 * On API 29+ this does not need a storage permission.
 */
object GalleryStore {
    const val RELATIVE_PATH = "DCIM/Hanson"
    const val FALLBACK_RELATIVE_PATH = "Pictures/Hanson"

    fun displayName(takenAtMs: Long = System.currentTimeMillis()): String {
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date(takenAtMs))
        return "Hanson_$stamp.jpg"
    }

    fun saveJpeg(context: Context, jpeg: File, displayName: String = displayName()): String? {
        if (!jpeg.isFile) return null
        val paths = listOf(RELATIVE_PATH, FALLBACK_RELATIVE_PATH)
        for (path in paths) {
            val uri = insert(context, jpeg, displayName, path)
            if (uri != null) return uri
        }
        return null
    }

    private fun insert(context: Context, jpeg: File, displayName: String, relative: String): String? {
        return try {
            val now = System.currentTimeMillis()
            val values = ContentValues().apply {
                put(MediaStore.Images.Media.DISPLAY_NAME, displayName)
                put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg")
                put(MediaStore.Images.Media.DATE_TAKEN, now)
                put(MediaStore.Images.Media.DATE_ADDED, now / 1000)
                put(MediaStore.Images.Media.DATE_MODIFIED, now / 1000)
                if (Build.VERSION.SDK_INT >= 29) {
                    put(MediaStore.Images.Media.RELATIVE_PATH, relative)
                    put(MediaStore.Images.Media.IS_PENDING, 1)
                }
            }
            val resolver = context.contentResolver
            val uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values) ?: return null
            resolver.openOutputStream(uri)?.use { out ->
                jpeg.inputStream().use { it.copyTo(out) }
            } ?: run {
                resolver.delete(uri, null, null)
                return null
            }
            if (Build.VERSION.SDK_INT >= 29) {
                val done = ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }
                resolver.update(uri, done, null, null)
            }
            uri.toString()
        } catch (_: Exception) {
            null
        }
    }
}

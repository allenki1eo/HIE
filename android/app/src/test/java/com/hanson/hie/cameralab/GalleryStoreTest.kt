package com.hanson.hie.cameralab

import com.hanson.hie.cameralab.process.GalleryStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar
import java.util.TimeZone

class GalleryStoreTest {
    @Test
    fun displayNameLooksLikeACameraRollFile() {
        val utc = TimeZone.getTimeZone("UTC")
        val prev = TimeZone.getDefault()
        TimeZone.setDefault(utc)
        try {
            val cal = Calendar.getInstance(utc)
            cal.set(2026, Calendar.SEPTEMBER, 23, 12, 0, 0)
            cal.set(Calendar.MILLISECOND, 0)
            assertEquals("Hanson_20260923_120000.jpg", GalleryStore.displayName(cal.timeInMillis))
        } finally {
            TimeZone.setDefault(prev)
        }
    }

    @Test
    fun albumIsDcimSoTheSystemGalleryPicksItUp() {
        assertTrue(GalleryStore.RELATIVE_PATH.startsWith("DCIM/"))
    }
}

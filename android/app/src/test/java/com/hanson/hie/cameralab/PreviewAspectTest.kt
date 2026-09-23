package com.hanson.hie.cameralab

import com.hanson.hie.cameralab.camera.PreviewAspect
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PreviewAspectTest {
    @Test
    fun portraitPhoneLetterboxesFourByThreeBuffer() {
        // 1440×1080 landscape buffer, sensor 90° → displayed 3:4
        val box = PreviewAspect.letterbox(1080, 1920, 1440, 1080, 90)
        assertEquals(1080, box.width)
        assertEquals(1440, box.height)
        val aspect = box.width.toFloat() / box.height
        assertEquals(0.75f, aspect, 0.01f)
    }

    @Test
    fun wideParentGetsPillarbox() {
        val box = PreviewAspect.letterbox(1920, 1080, 1440, 1080, 0)
        assertEquals(1440, box.width)
        assertEquals(1080, box.height)
    }

    @Test
    fun choosePreviewPrefersFourByThree() {
        val sizes = listOf(
            1920 to 1080,
            1440 to 1080,
            1280 to 720,
            4032 to 3024,
        )
        val chosen = PreviewAspect.choosePreview(sizes)
        assertEquals(1440 to 1080, chosen)
    }

    @Test
    fun portraitFitIsUniformAndUnstretched() {
        val fit = PreviewAspect.fit(1080, 1920, 1440, 1080, sensorOrientationDeg = 90, displayRotationDeg = 0)
        assertEquals(90, fit.rotationDeg)
        assertEquals(1080, fit.contentWidth)
        assertEquals(1440, fit.contentHeight)
        assertEquals(1f, fit.scale, 0.01f)
    }

    @Test
    fun emptySizesFallsBack() {
        val chosen = PreviewAspect.choosePreview(emptyList())
        assertTrue(chosen.first > 0 && chosen.second > 0)
    }
}

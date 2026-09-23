package com.hanson.hie.cameralab

import com.hanson.hie.cameralab.process.HieProcessor
import org.junit.Assert.assertEquals
import org.junit.Test

class HieProcessorTest {
    @Test
    fun planeOffsetsMatchPythonCanonicalOrder() {
        val rggb = HieProcessor.planeOffsets("RGGB")
        assertEquals(0 to 0, rggb[0]) // R
        assertEquals(0 to 1, rggb[1]) // Gr
        assertEquals(1 to 0, rggb[2]) // Gb
        assertEquals(1 to 1, rggb[3]) // B

        val bggr = HieProcessor.planeOffsets("BGGR")
        assertEquals(1 to 1, bggr[0]) // R
        assertEquals(1 to 0, bggr[1]) // Gr (green sharing R's row)
        assertEquals(0 to 1, bggr[2]) // Gb
        assertEquals(0 to 0, bggr[3]) // B
    }

    @Test
    fun packRgbToArgbIsOpaqueRgb() {
        val rgb = byteArrayOf(10, 20, 30, 40, 50, 60)
        val pix = HieProcessor.packRgbToArgb(rgb, 2, 1)
        assertEquals(2, pix.size)
        assertEquals((0xff shl 24) or (10 shl 16) or (20 shl 8) or 30, pix[0])
        assertEquals((0xff shl 24) or (40 shl 16) or (50 shl 8) or 60, pix[1])
    }

    @Test
    fun identityMatrixWhenTransformMissing() {
        val m = HieProcessor.colorMatrix(null)
        assertEquals(9, m.size)
        assertEquals(1f, m[0])
        assertEquals(1f, m[4])
        assertEquals(1f, m[8])
    }
}

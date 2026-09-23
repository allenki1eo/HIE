package com.hanson.hie.cameralab

import com.hanson.hie.cameralab.capture.BurstPolicy
import com.hanson.hie.cameralab.capture.CaptureMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BurstPolicyTest {
    @Test
    fun photoIsSingleFrameWithoutLocks() {
        val p = BurstPolicy.plan(CaptureMode.PHOTO, 800, 20_000_000L, true)
        assertEquals(1, p.frameCount)
        assertEquals(false, p.lockAe)
    }

    @Test
    fun burstStaysWithinPublishedBounds() {
        val dark = BurstPolicy.plan(CaptureMode.BURST, 3200, 40_000_000L, true)
        val bright = BurstPolicy.plan(CaptureMode.BURST, 50, 8_000_000L, true)
        assertTrue(dark.frameCount in BurstPolicy.MIN_BURST..BurstPolicy.MAX_BURST)
        assertTrue(bright.frameCount in BurstPolicy.MIN_BURST..BurstPolicy.MAX_BURST)
        assertTrue(dark.frameCount >= bright.frameCount)
        assertTrue(dark.lockAe && dark.lockAwb)
    }

    @Test
    fun nightUsesMoreFramesThanDayBurstAtSameExposure() {
        val night = BurstPolicy.plan(CaptureMode.NIGHT, 1600, 30_000_000L, true)
        val burst = BurstPolicy.plan(CaptureMode.BURST, 1600, 30_000_000L, true)
        assertTrue(night.frameCount >= burst.frameCount)
        assertTrue(night.frameCount <= BurstPolicy.MAX_BURST)
    }

    @Test
    fun missingMeteringStillProducesAValidPlan() {
        val p = BurstPolicy.plan(CaptureMode.BURST, null, null, false)
        assertTrue(p.frameCount in BurstPolicy.MIN_BURST..BurstPolicy.MAX_BURST)
    }
}

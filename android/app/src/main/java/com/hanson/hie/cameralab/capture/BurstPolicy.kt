package com.hanson.hie.cameralab.capture

/**
 * Published-style constant-exposure burst length (HDR+ / Night Sight time budget).
 *
 * This is a reproduction of ideas in Hasinoff et al. 2016 (constant short exposure,
 * 2–8 frames) and Liba et al. 2019 (frame count from a capture-time budget).
 * It is **not** US 9,313,420 (incremental frames to maximise summed SNR) and
 * **not** US 9,087,391 (metering TET sequence with long/short bracketing).
 *
 * Tune only via the documented constants. Do not fit these on evaluation bursts.
 */
enum class CaptureMode {
    PHOTO,
    BURST,
    NIGHT,
}

data class BurstPlan(
    val mode: CaptureMode,
    val frameCount: Int,
    val lockAe: Boolean,
    val lockAwb: Boolean,
    val reason: String,
) {
    val writeRaw: Boolean get() = mode != CaptureMode.PHOTO || frameCount >= 1
}

object BurstPolicy {
    const val MIN_BURST = 5
    const val MAX_BURST = 15
    /** Night Sight-style time budget for the payload, seconds. */
    const val NIGHT_BUDGET_S = 3.0
    const val BURST_BUDGET_S = 1.2

    fun plan(mode: CaptureMode, iso: Int?, exposureNs: Long?, rawAvailable: Boolean): BurstPlan {
        if (mode == CaptureMode.PHOTO) {
            return BurstPlan(mode, 1, lockAe = false, lockAwb = false, reason = "single still")
        }
        val exposureS = (exposureNs ?: 20_000_000L).coerceAtLeast(1L) / 1_000_000_000.0
        val isoSafe = (iso ?: 100).coerceAtLeast(1)
        val tet = isoSafe * exposureS
        val budget = if (mode == CaptureMode.NIGHT) NIGHT_BUDGET_S else BURST_BUDGET_S
        val fromBudget = (budget / exposureS).toInt()
        // Brighter scenes (low TET) need fewer frames; night TET is large.
        val fromLight = when {
            tet < 4.0 -> MIN_BURST
            tet < 16.0 -> 8
            tet < 64.0 -> 12
            else -> MAX_BURST
        }
        val count = fromBudget.coerceIn(MIN_BURST, MAX_BURST).coerceAtMost(fromLight.coerceAtLeast(MIN_BURST))
        val reason = "constant-exposure reproduction: tet=$tet iso=$isoSafe exp=${"%.4f".format(exposureS)}s " +
            "budget=${budget}s raw=$rawAvailable → $count frames"
        return BurstPlan(mode, count, lockAe = true, lockAwb = true, reason = reason)
    }
}

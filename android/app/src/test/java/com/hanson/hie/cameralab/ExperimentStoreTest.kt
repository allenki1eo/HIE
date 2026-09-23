package com.hanson.hie.cameralab

import com.hanson.hie.cameralab.capture.ExperimentStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.json.JSONObject
import java.io.File
import kotlin.io.path.createTempDirectory

class ExperimentStoreTest {
    @Test
    fun neverReusesADirectoryName() {
        val root = createTempDirectory("hie-pkg").toFile()
        val store = ExperimentStore(root)
        val a = store.nextPackage()
        val b = store.nextPackage()
        assertEquals("experiment_0001", a.name)
        assertEquals("experiment_0002", b.name)
        assertTrue(File(a, "raw").isDirectory)
        store.writeJson(File(a, "experiment.json"), JSONObject().put("ok", true))
        try {
            store.writeJson(File(a, "experiment.json"), JSONObject().put("again", true))
            throw AssertionError("overwrite allowed")
        } catch (e: IllegalStateException) {
            assertTrue(e.message!!.contains("overwrite"))
        }
    }
}

package com.hanson.hie.cameralab.capture

import org.json.JSONObject
import java.io.File

/**
 * Never-overwrite experiment packages, matching datasets/pixel6.
 *
 * experiment_0001/, experiment_0002/, …
 */
class ExperimentStore(private val root: File) {
    init {
        root.mkdirs()
    }

    fun list(): List<File> =
        root.listFiles()
            ?.filter { it.isDirectory && it.name.matches(Regex("experiment_\\d{4,}")) }
            ?.sortedByDescending { it.name }
            ?: emptyList()

    fun nextPackage(): File {
        val used = list().mapNotNull { it.name.removePrefix("experiment_").toIntOrNull() }.toSet()
        var n = 1
        while (n in used) n++
        val dir = File(root, "experiment_%04d".format(n))
        if (dir.exists()) {
            throw IllegalStateException("refusing to overwrite $dir")
        }
        dir.mkdirs()
        File(dir, "raw").mkdirs()
        File(dir, "motion").mkdirs()
        File(dir, "stock").mkdirs()
        File(dir, "hie").mkdirs()
        return dir
    }

    fun writeJson(file: File, obj: JSONObject) {
        if (file.exists()) throw IllegalStateException("refusing to overwrite $file")
        file.writeText(obj.toString(2))
    }
}

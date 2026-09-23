#include "hie_pipeline.hpp"

#include <jni.h>

#include <cstring>
#include <string>
#include <vector>

namespace {

void throw_java(JNIEnv* env, const char* msg) {
    jclass cls = env->FindClass("java/lang/IllegalStateException");
    if (cls) env->ThrowNew(cls, msg);
}

}  // namespace

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_hanson_hie_cameralab_process_HieNative_processBurst(
    JNIEnv* env, jclass /*clazz*/,
    jobjectArray mosaics,
    jint width, jint height, jint stride_pixels,
    jstring cfa_j,
    jfloatArray black_j, jfloat white,
    jfloatArray shot_j, jfloatArray read_j, jboolean have_noise,
    jfloatArray wb_j, jfloatArray ccm_j,
    jint orientation_deg, jint max_mosaic_pixels, jint max_frames,
    jintArray out_wh, jobjectArray out_json) {
    if (!mosaics || !black_j || !wb_j || !ccm_j || !out_wh || !out_json) {
        throw_java(env, "HIE JNI: null argument");
        return nullptr;
    }
    const int n = env->GetArrayLength(mosaics);
    if (n <= 0) {
        throw_java(env, "HIE JNI: empty burst");
        return nullptr;
    }
    const char* cfa = env->GetStringUTFChars(cfa_j, nullptr);
    std::vector<const uint16_t*> ptrs(n);
    std::vector<void*> releases(n, nullptr);
    std::vector<jshortArray> keep(n, nullptr);
    bool ok = true;
    std::string err;
    for (int i = 0; i < n; ++i) {
        jobject obj = env->GetObjectArrayElement(mosaics, i);
        if (env->IsInstanceOf(obj, env->FindClass("java/nio/ByteBuffer"))) {
            uint8_t* p = static_cast<uint8_t*>(env->GetDirectBufferAddress(obj));
            jlong cap = env->GetDirectBufferCapacity(obj);
            if (!p || cap < static_cast<jlong>(height) * stride_pixels * 2) {
                ok = false;
                err = "HIE JNI: mosaic ByteBuffer too small";
                env->DeleteLocalRef(obj);
                break;
            }
            ptrs[i] = reinterpret_cast<const uint16_t*>(p);
        } else {
            jshortArray arr = static_cast<jshortArray>(obj);
            keep[i] = arr;
            jshort* p = env->GetShortArrayElements(arr, nullptr);
            if (!p) {
                ok = false;
                err = "HIE JNI: mosaic short[] failed";
                break;
            }
            ptrs[i] = reinterpret_cast<const uint16_t*>(p);
            releases[i] = p;
        }
    }
    hie::BurstResult result;
    if (ok) {
        hie::BurstSpec spec;
        spec.width = width;
        spec.height = height;
        spec.stride_pixels = stride_pixels;
        spec.n_frames = n;
        spec.mosaics = ptrs.data();
        spec.cfa = cfa ? cfa : "RGGB";
        spec.white = white;
        spec.have_noise = have_noise == JNI_TRUE;
        spec.orientation_deg = orientation_deg;
        spec.max_mosaic_pixels = max_mosaic_pixels;
        spec.max_frames = max_frames;
        env->GetFloatArrayRegion(black_j, 0, 4, spec.black);
        if (shot_j) env->GetFloatArrayRegion(shot_j, 0, 4, spec.shot);
        if (read_j) env->GetFloatArrayRegion(read_j, 0, 4, spec.read);
        env->GetFloatArrayRegion(wb_j, 0, 4, spec.wb);
        env->GetFloatArrayRegion(ccm_j, 0, 9, spec.ccm);
        try {
            result = hie::process_burst(spec);
        } catch (const std::exception& e) {
            ok = false;
            err = e.what();
        }
    }
    if (cfa) env->ReleaseStringUTFChars(cfa_j, cfa);
    for (int i = 0; i < n; ++i) {
        if (keep[i] && releases[i]) {
            env->ReleaseShortArrayElements(keep[i], static_cast<jshort*>(releases[i]), JNI_ABORT);
        }
    }
    if (!ok) {
        throw_java(env, err.empty() ? "HIE process failed" : err.c_str());
        return nullptr;
    }
    jint wh[2] = {result.width, result.height};
    env->SetIntArrayRegion(out_wh, 0, 2, wh);
    jstring js = env->NewStringUTF(result.json.c_str());
    env->SetObjectArrayElement(out_json, 0, js);
    jbyteArray rgb = env->NewByteArray(static_cast<jsize>(result.rgb.size()));
    if (!rgb) {
        throw_java(env, "HIE JNI: OOM writing RGB");
        return nullptr;
    }
    env->SetByteArrayRegion(rgb, 0, static_cast<jsize>(result.rgb.size()),
                            reinterpret_cast<const jbyte*>(result.rgb.data()));
    return rgb;
}

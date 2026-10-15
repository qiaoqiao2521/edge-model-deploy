/**
 * JNI 标准接口层 (对标移动视频剪辑应用的 JNI 签名规范)
 * 提供与 Android Java / Kotlin 层的零拷贝交互。
 */

#include "edge_model_deploy/whisper_engine.hpp"

#include <jni.h>
#include <string>
#include <vector>

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_edgeai_deploy_WhisperLib_initContext(JNIEnv* env, jobject /*thiz*/, jstring model_path) {
    if (!model_path) return 0;
    const char* path_chars = env->GetStringUTFChars(model_path, nullptr);
    auto engine = edge_ai::WhisperEngine::Create(path_chars);
    env->ReleaseStringUTFChars(model_path, path_chars);
    return reinterpret_cast<jlong>(engine.release());
}

JNIEXPORT void JNICALL
Java_com_edgeai_deploy_WhisperLib_freeContext(JNIEnv* /*env*/, jobject /*thiz*/, jlong context_ptr) {
    if (context_ptr != 0) {
        delete reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    }
}

JNIEXPORT void JNICALL
Java_com_edgeai_deploy_WhisperLib_fullTranscribe(
    JNIEnv* env, jobject /*thiz*/, jlong context_ptr, jint num_threads,
    jfloatArray audio_data, jstring language_code, jstring prompt) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    if (!engine || !audio_data) return;

    jsize len = env->GetArrayLength(audio_data);
    std::vector<float> pcm(len);
    env->GetFloatArrayRegion(audio_data, 0, len, pcm.data());

    std::string lang = "zh";
    if (language_code) {
        const char* lang_chars = env->GetStringUTFChars(language_code, nullptr);
        lang = lang_chars;
        env->ReleaseStringUTFChars(language_code, lang_chars);
    }

    std::string prompt_str = "";
    if (prompt) {
        const char* prompt_chars = env->GetStringUTFChars(prompt, nullptr);
        prompt_str = prompt_chars;
        env->ReleaseStringUTFChars(prompt, prompt_chars);
    }

    engine->FullTranscribe(pcm, lang, prompt_str, num_threads);
}

JNIEXPORT jint JNICALL
Java_com_edgeai_deploy_WhisperLib_getTextSegmentCount(JNIEnv* /*env*/, jobject /*thiz*/, jlong context_ptr) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    return engine ? engine->GetSegmentCount() : 0;
}

JNIEXPORT jstring JNICALL
Java_com_edgeai_deploy_WhisperLib_getTextSegment(JNIEnv* env, jobject /*thiz*/, jlong context_ptr, jint index) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    if (!engine) return env->NewStringUTF("");
    std::string text = engine->GetSegmentText(index);
    return env->NewStringUTF(text.c_str());
}

JNIEXPORT jlong JNICALL
Java_com_edgeai_deploy_WhisperLib_getTextSegmentBegin(JNIEnv* /*env*/, jobject /*thiz*/, jlong context_ptr, jint index) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    return engine ? engine->GetSegmentBegin(index) : 0;
}

JNIEXPORT jlong JNICALL
Java_com_edgeai_deploy_WhisperLib_getTextSegmentEnd(JNIEnv* /*env*/, jobject /*thiz*/, jlong context_ptr, jint index) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    return engine ? engine->GetSegmentEnd(index) : 0;
}

JNIEXPORT void JNICALL
Java_com_edgeai_deploy_WhisperLib_cancel(JNIEnv* /*env*/, jobject /*thiz*/, jlong context_ptr) {
    auto* engine = reinterpret_cast<edge_ai::WhisperEngine*>(context_ptr);
    if (engine) engine->Cancel();
}

} // extern "C"

/**
 * JNI 标准接口层 (对标移动视频剪辑应用的 JNI 签名规范)
 * Java float[] is copied into a native buffer. Android device acceptance is pending.
 */

#include "edge_model_deploy/whisper_engine.hpp"

#include <jni.h>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
void ThrowJava(JNIEnv* env, const char* class_name, const char* message) {
    if (env->ExceptionCheck()) return;
    jclass exception_class = env->FindClass(class_name);
    if (exception_class) {
        env->ThrowNew(exception_class, message);
        env->DeleteLocalRef(exception_class);
    }
}

class UtfChars {
public:
    UtfChars(JNIEnv* env, jstring value) : env_(env), value_(value) {
        chars_ = env_->GetStringUTFChars(value_, nullptr);
        if (!chars_) throw std::runtime_error("Cannot access Java string");
    }
    ~UtfChars() { env_->ReleaseStringUTFChars(value_, chars_); }
    const char* get() const { return chars_; }
    UtfChars(const UtfChars&) = delete;
    UtfChars& operator=(const UtfChars&) = delete;
private:
    JNIEnv* env_;
    jstring value_;
    const char* chars_;
};
} // namespace

extern "C" {

JNIEXPORT jlong JNICALL
Java_com_edgeai_deploy_WhisperLib_initContext(JNIEnv* env, jobject /*thiz*/, jstring model_path) {
    if (!model_path) {
        ThrowJava(env, "java/lang/IllegalArgumentException", "Model path is required");
        return 0;
    }
    try {
        UtfChars path_chars(env, model_path);
        auto engine = edge_ai::WhisperEngine::Create(path_chars.get());
        return reinterpret_cast<jlong>(engine.release());
    } catch (const std::exception& error) {
        ThrowJava(env, "java/lang/IllegalStateException", error.what());
    } catch (...) {
        ThrowJava(env, "java/lang/IllegalStateException", "Native model initialization failed");
    }
    return 0;
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
    if (!engine || !audio_data) {
        ThrowJava(env, "java/lang/IllegalArgumentException", "Context and audio are required");
        return;
    }
    try {
        const jsize len = env->GetArrayLength(audio_data);
        if (env->ExceptionCheck()) return;
        std::vector<float> pcm(static_cast<size_t>(len));
        env->GetFloatArrayRegion(audio_data, 0, len, pcm.data());
        if (env->ExceptionCheck()) return;
        std::string lang = "zh";
        if (language_code) {
            UtfChars lang_chars(env, language_code);
            lang = lang_chars.get();
        }
        std::string prompt_str;
        if (prompt) {
            UtfChars prompt_chars(env, prompt);
            prompt_str = prompt_chars.get();
        }
        if (!engine->FullTranscribe(pcm, lang, prompt_str, num_threads)) {
            ThrowJava(env, "java/lang/IllegalStateException", "Transcription failed, cancelled, or input was invalid");
        }
    } catch (const std::exception& error) {
        ThrowJava(env, "java/lang/IllegalStateException", error.what());
    } catch (...) {
        ThrowJava(env, "java/lang/IllegalStateException", "Native transcription failed");
    }
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

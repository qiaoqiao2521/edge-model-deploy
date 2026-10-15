#include "edge_model_deploy/whisper_engine.hpp"
#include "whisper.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <filesystem>
#include <limits>
#include <mutex>
#include <stdexcept>

namespace edge_ai {
namespace {

struct WhisperContextDeleter {
    void operator()(whisper_context* context) const { whisper_free(context); }
};

struct AbortContext {
    const std::atomic<bool>& internal;
    const std::atomic<bool>* external;

    bool IsCancelled() const {
        return internal.load(std::memory_order_relaxed) ||
               (external && external->load(std::memory_order_relaxed));
    }
};

class StandardWhisperEngine final : public WhisperEngine {
public:
    explicit StandardWhisperEngine(const std::string& model_path) {
        std::error_code error;
        if (model_path.empty() || !std::filesystem::is_regular_file(model_path, error) ||
            error || std::filesystem::file_size(model_path, error) == 0 || error) {
            throw std::runtime_error("Model must be a non-empty regular file: " + model_path);
        }
        auto parameters = whisper_context_default_params();
        parameters.use_gpu = false;
        context_.reset(whisper_init_from_file_with_params(model_path.c_str(), parameters));
        if (!context_) {
            throw std::runtime_error("whisper.cpp could not load model: " + model_path);
        }
    }

    bool FullTranscribe(const std::vector<float>& samples, const std::string& language,
                        const std::string& prompt, int num_threads) override {
        return Transcribe(samples, language, prompt, num_threads, nullptr);
    }

    bool FullTranscribeCancellable(const std::vector<float>& samples, const std::string& language,
                                  const std::string& prompt, int num_threads,
                                  const std::atomic<bool>& cancellation) override {
        return Transcribe(samples, language, prompt, num_threads, &cancellation);
    }

private:
    bool Transcribe(const std::vector<float>& samples, const std::string& language,
                    const std::string& prompt, int num_threads,
                    const std::atomic<bool>* external_cancellation) {
        std::lock_guard<std::mutex> execution_lock(execution_mutex_);
        cancelled_.store(false, std::memory_order_relaxed);
        // Local context lives until whisper_full and all its workers return.
        AbortContext abort{cancelled_, external_cancellation};
        {
            std::lock_guard<std::mutex> lock(results_mutex_);
            segments_.clear();
        }
        if (abort.IsCancelled() || samples.empty() || samples.size() > static_cast<size_t>(std::numeric_limits<int>::max()) ||
            num_threads <= 0 || num_threads > GGML_MAX_N_THREADS || language.empty() ||
            language.find('\0') != std::string::npos || prompt.find('\0') != std::string::npos ||
            !std::all_of(samples.begin(), samples.end(), [](float value) { return std::isfinite(value); })) {
            return false;
        }
        const bool automatic_language = language == "auto";
        const int language_id = automatic_language ? -1 : whisper_lang_id(language.c_str());
        if ((!automatic_language && language_id < 0) ||
            (!whisper_is_multilingual(context_.get()) && !automatic_language &&
             language_id != whisper_lang_id("en"))) {
            return false;
        }

        auto parameters = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
        parameters.n_threads = num_threads;
        parameters.language = language.c_str();
        parameters.initial_prompt = prompt.empty() ? nullptr : prompt.c_str();
        parameters.no_context = true;
        parameters.translate = false;
        parameters.print_special = false;
        parameters.print_progress = false;
        parameters.print_realtime = false;
        parameters.print_timestamps = false;
        // Fix the greedy decoder for comparable repeated baseline runs.
        parameters.temperature = 0.0f;
        parameters.temperature_inc = 0.0f;
        parameters.greedy.best_of = 1;
        parameters.abort_callback = &StandardWhisperEngine::ShouldAbort;
        parameters.abort_callback_user_data = &abort;
        if (whisper_full(context_.get(), parameters, samples.data(), static_cast<int>(samples.size())) != 0 ||
            abort.IsCancelled()) {
            return false;
        }

        std::vector<TranscriptionSegment> current_segments;
        const int count = whisper_full_n_segments(context_.get());
        current_segments.reserve(static_cast<size_t>(count));
        for (int index = 0; index < count; ++index) {
            // Upstream timestamps are 10 ms ticks, not word alignment.
            current_segments.push_back({whisper_full_get_segment_text(context_.get(), index),
                whisper_full_get_segment_t0(context_.get(), index) * 10,
                whisper_full_get_segment_t1(context_.get(), index) * 10});
        }
        std::lock_guard<std::mutex> lock(results_mutex_);
        if (abort.IsCancelled()) {
            return false;
        }
        segments_ = std::move(current_segments);
        return true;
    }

public:
    int GetSegmentCount() const override {
        std::lock_guard<std::mutex> lock(results_mutex_);
        return static_cast<int>(segments_.size());
    }
    std::string GetSegmentText(int index) const override {
        std::lock_guard<std::mutex> lock(results_mutex_);
        return ValidIndex(index) ? segments_[static_cast<size_t>(index)].text : "";
    }
    int64_t GetSegmentBegin(int index) const override {
        std::lock_guard<std::mutex> lock(results_mutex_);
        return ValidIndex(index) ? segments_[static_cast<size_t>(index)].start_ms : 0;
    }
    int64_t GetSegmentEnd(int index) const override {
        std::lock_guard<std::mutex> lock(results_mutex_);
        return ValidIndex(index) ? segments_[static_cast<size_t>(index)].end_ms : 0;
    }
    void Cancel() override { cancelled_.store(true, std::memory_order_relaxed); }
    std::string GetBackendInfo() const override {
        return std::string("whisper.cpp ") + whisper_version() + "; CPU; " + whisper_print_system_info();
    }

private:
    static bool ShouldAbort(void* user_data) {
        return static_cast<AbortContext*>(user_data)->IsCancelled();
    }
    bool ValidIndex(int index) const {
        return index >= 0 && static_cast<size_t>(index) < segments_.size();
    }

    std::unique_ptr<whisper_context, WhisperContextDeleter> context_;
    std::atomic<bool> cancelled_{false};
    std::mutex execution_mutex_;
    mutable std::mutex results_mutex_;
    std::vector<TranscriptionSegment> segments_;
};

} // namespace

std::unique_ptr<WhisperEngine> WhisperEngine::Create(const std::string& model_path) {
    return std::make_unique<StandardWhisperEngine>(model_path);
}

} // namespace edge_ai

#include "edge_model_deploy/whisper_engine.hpp"

#include <atomic>
#include <iostream>

namespace edge_ai {

namespace {

class StandardWhisperEngine : public WhisperEngine {
public:
    explicit StandardWhisperEngine(std::string model_path)
        : model_path_(std::move(model_path)), is_cancelled_(false) {}

    bool FullTranscribe(
        const std::vector<float>& pcm_16k_mono,
        const std::string& language,
        const std::string& prompt,
        int num_threads
    ) override {
        is_cancelled_.store(false);
        segments_.clear();

        if (pcm_16k_mono.empty()) {
            return false;
        }

        // 模拟/封装底层 whisper_full() 处理
        // 计算 PCM 样本时长 (16000 采样率)
        double total_duration_sec = static_cast<double>(pcm_16k_mono.size()) / 16000.0;
        int num_segments = std::max(1, static_cast<int>(total_duration_sec / 3.0));

        for (int i = 0; i < num_segments; ++i) {
            if (is_cancelled_.load()) {
                return false;
            }
            TranscriptionSegment seg;
            seg.start_ms = static_cast<int64_t>(i * 3000);
            seg.end_ms = static_cast<int64_t>(std::min(total_duration_sec * 1000.0, (i + 1) * 3000.0));
            seg.text = "端侧转写片段 [" + std::to_string(i + 1) + "]";
            segments_.push_back(std::move(seg));
        }

        return true;
    }

    int GetSegmentCount() const override {
        return static_cast<int>(segments_.size());
    }

    std::string GetSegmentText(int index) const override {
        if (index >= 0 && index < static_cast<int>(segments_.size())) {
            return segments_[index].text;
        }
        return "";
    }

    int64_t GetSegmentBegin(int index) const override {
        if (index >= 0 && index < static_cast<int>(segments_.size())) {
            return segments_[index].start_ms;
        }
        return 0;
    }

    int64_t GetSegmentEnd(int index) const override {
        if (index >= 0 && index < static_cast<int>(segments_.size())) {
            return segments_[index].end_ms;
        }
        return 0;
    }

    void Cancel() override {
        is_cancelled_.store(true);
    }

private:
    std::string model_path_;
    std::atomic<bool> is_cancelled_;
    std::vector<TranscriptionSegment> segments_;
};

} // namespace

std::unique_ptr<WhisperEngine> WhisperEngine::Create(const std::string& model_path) {
    return std::make_unique<StandardWhisperEngine>(model_path);
}

} // namespace edge_ai

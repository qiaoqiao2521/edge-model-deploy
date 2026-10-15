#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace edge_ai {

struct TranscriptionSegment {
    std::string text;
    int64_t start_ms{0};
    int64_t end_ms{0};
};

class WhisperEngine {
public:
    virtual ~WhisperEngine() = default;

    static std::unique_ptr<WhisperEngine> Create(const std::string& model_path);

    virtual bool FullTranscribe(
        const std::vector<float>& pcm_16k_mono,
        const std::string& language = "zh",
        const std::string& prompt = "",
        int num_threads = 4
    ) = 0;

    virtual int GetSegmentCount() const = 0;
    virtual std::string GetSegmentText(int index) const = 0;
    virtual int64_t GetSegmentBegin(int index) const = 0;
    virtual int64_t GetSegmentEnd(int index) const = 0;
    virtual void Cancel() = 0;
};

} // namespace edge_ai

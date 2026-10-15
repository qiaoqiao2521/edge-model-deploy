#pragma once

#include <atomic>
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

    // Input must contain finite 16 kHz mono samples. A failed or cancelled call
    // clears prior segments. FullTranscribe calls run sequentially per engine;
    // Cancel may be called from another thread while transcription is running.
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
    virtual std::string GetBackendInfo() const { return "unknown"; }

    // A job-owned flag is never reset by the engine and must outlive this
    // synchronous call. Unsupported external implementations fail closed.
    virtual bool FullTranscribeCancellable(
        const std::vector<float>&,
        const std::string&,
        const std::string&,
        int,
        const std::atomic<bool>&
    ) { return false; }
};

} // namespace edge_ai

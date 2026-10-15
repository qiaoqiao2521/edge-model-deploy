#include "edge_model_deploy/dynamic_delivery.hpp"
#include "edge_model_deploy/whisper_engine.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {
void Check(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void RejectModel(const std::string& path) {
    bool rejected = false;
    try { edge_ai::WhisperEngine::Create(path); }
    catch (const std::exception&) { rejected = true; }
    Check(rejected, "Invalid model was accepted");
}
} // namespace

int main(int argc, char** argv) {
    const auto path = std::filesystem::temp_directory_path() /
        ("edge-native-test-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    try {
        RejectModel("");
        RejectModel(path.string());
        std::filesystem::create_directory(path);
        RejectModel(path.string());
        const auto invalid_model = path / "invalid.bin";
        { std::ofstream stream(invalid_model); stream << "This is not a model"; }
        RejectModel(invalid_model.string());
        edge_ai::DynamicModelDelivery delivery((path / "not-created").string());
        bool progress_called = false;
        Check(!delivery.EnsureModel(edge_ai::ModelTier::TINY, [&](float) { progress_called = true; }),
              "Deprecated delivery reported success");
        Check(!progress_called && !std::filesystem::exists(path / "not-created"),
              "Deprecated delivery created files or emitted false progress");
        Check(!delivery.IsModelAvailable(edge_ai::ModelTier::TINY), "Unverified model was available");
        if (argc == 2) {
            auto engine = edge_ai::WhisperEngine::Create(argv[1]);
            const std::vector<float> silence(16000, 0.0f);
            auto invalid = silence;
            invalid[10] = std::numeric_limits<float>::quiet_NaN();
            Check(!engine->FullTranscribe(invalid, "en", "", 1), "NaN sample was accepted");
            invalid[10] = std::numeric_limits<float>::infinity();
            Check(!engine->FullTranscribe(invalid, "en", "", 1), "Infinite sample was accepted");
            Check(!engine->FullTranscribe({}, "en", "", 1), "Empty audio was accepted");
            Check(!engine->FullTranscribe(silence, "en", "", 0), "Zero threads were accepted");
            Check(!engine->FullTranscribe(silence, "en", "", -1), "Negative threads were accepted");
            Check(!engine->FullTranscribe(silence, "en", "", 513), "Excess threads were accepted");
            Check(!engine->FullTranscribe(silence, "unknown-language", "", 1), "Unknown language was accepted");
            Check(!engine->FullTranscribe(silence, "", "", 1), "Empty language was accepted");
            Check(engine->GetSegmentCount() == 0 && engine->GetSegmentText(-1).empty() &&
                  engine->GetSegmentBegin(0) == 0 && engine->GetSegmentEnd(0) == 0,
                  "Invalid calls exposed stale or invalid segments");
            Check(engine->GetBackendInfo().find("whisper.cpp") != std::string::npos, "Backend identification missing");
            const std::atomic<bool> cancelled_job{true};
            Check(!engine->FullTranscribeCancellable(silence, "en", "", 1, cancelled_job),
                  "A job cancelled before inference was restarted");
            Check(cancelled_job.load() && engine->GetSegmentCount() == 0,
                  "External cancellation was reset or exposed results");
        }
        std::filesystem::remove_all(path);
        std::cout << "Native boundary tests passed" << (argc == 2 ? " with real model" : " without model") << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::filesystem::remove_all(path);
        std::cerr << error.what() << '\n';
        return 1;
    }
}

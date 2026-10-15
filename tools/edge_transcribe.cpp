#include "edge_model_deploy/whisper_engine.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <sys/resource.h>
#endif

namespace {
using Clock = std::chrono::steady_clock;
constexpr uint32_t kSampleRate = 16000;

uint16_t ReadU16(const unsigned char* bytes) {
    return static_cast<uint16_t>(bytes[0]) | static_cast<uint16_t>(bytes[1]) << 8;
}
uint32_t ReadU32(const unsigned char* bytes) {
    return static_cast<uint32_t>(bytes[0]) | static_cast<uint32_t>(bytes[1]) << 8 |
           static_cast<uint32_t>(bytes[2]) << 16 | static_cast<uint32_t>(bytes[3]) << 24;
}
void ReadExact(std::ifstream& stream, unsigned char* bytes, size_t count) {
    if (!stream.read(reinterpret_cast<char*>(bytes), static_cast<std::streamsize>(count))) {
        throw std::runtime_error("Truncated WAV file");
    }
}

// Deliberately accepts one auditable format; conversion belongs outside the
// timed inference process. Unknown RIFF chunks and their padding are skipped.
std::vector<float> ReadPcm16Wav(const std::string& path) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    if (!stream) throw std::runtime_error("Cannot open audio: " + path);
    const auto length = stream.tellg();
    if (length < 12) throw std::runtime_error("WAV header is missing or truncated");
    stream.seekg(0);
    std::array<unsigned char, 16> header{};
    ReadExact(stream, header.data(), 12);
    if (std::memcmp(header.data(), "RIFF", 4) != 0 ||
        std::memcmp(header.data() + 8, "WAVE", 4) != 0) {
        throw std::runtime_error("Expected a little-endian RIFF/WAVE file");
    }
    const uint64_t riff_end = static_cast<uint64_t>(ReadU32(header.data() + 4)) + 8;
    if (riff_end < 12 || riff_end > static_cast<uint64_t>(length)) {
        throw std::runtime_error("WAV RIFF size exceeds file bounds");
    }
    bool has_format = false;
    bool has_data = false;
    uint64_t data_position = 0;
    uint32_t data_size = 0;
    uint64_t position = 12;
    while (position < riff_end) {
        if (riff_end - position < 8) throw std::runtime_error("Incomplete WAV chunk header");
        stream.seekg(static_cast<std::streamoff>(position));
        ReadExact(stream, header.data(), 8);
        const uint32_t chunk_size = ReadU32(header.data() + 4);
        const uint64_t payload = position + 8;
        const uint64_t next = payload + chunk_size + (chunk_size & 1u);
        if (next > riff_end) throw std::runtime_error("WAV chunk exceeds RIFF bounds");
        if (std::memcmp(header.data(), "fmt ", 4) == 0) {
            if (has_format || chunk_size < 16) throw std::runtime_error("Invalid or duplicate WAV format chunk");
            ReadExact(stream, header.data(), 16);
            if (ReadU16(header.data()) != 1 || ReadU16(header.data() + 2) != 1 ||
                ReadU32(header.data() + 4) != kSampleRate ||
                ReadU32(header.data() + 8) != kSampleRate * 2 ||
                ReadU16(header.data() + 12) != 2 || ReadU16(header.data() + 14) != 16) {
                throw std::runtime_error("Audio must be PCM16, mono, 16000 Hz (convert it before running)");
            }
            has_format = true;
        } else if (std::memcmp(header.data(), "data", 4) == 0) {
            if (has_data || chunk_size == 0 || (chunk_size & 1u) != 0) {
                throw std::runtime_error("Invalid, empty, or duplicate WAV data chunk");
            }
            has_data = true;
            data_position = payload;
            data_size = chunk_size;
        }
        position = next;
    }
    if (!has_format || !has_data) throw std::runtime_error("WAV needs format and data chunks");
    const size_t sample_count = data_size / 2;
    if (sample_count > static_cast<size_t>(std::numeric_limits<int>::max())) {
        throw std::runtime_error("Audio has too many samples for whisper.cpp");
    }
    std::vector<float> samples(sample_count);
    stream.seekg(static_cast<std::streamoff>(data_position));
    std::array<unsigned char, 8192> buffer{};
    size_t sample_offset = 0;
    while (sample_offset < sample_count) {
        const size_t count = std::min(buffer.size() / 2, sample_count - sample_offset);
        ReadExact(stream, buffer.data(), count * 2);
        for (size_t i = 0; i < count; ++i) {
            const uint16_t raw = ReadU16(buffer.data() + 2 * i);
            const int32_t signed_value = raw >= 0x8000u ? static_cast<int32_t>(raw) - 0x10000 : raw;
            samples[sample_offset + i] = static_cast<float>(signed_value) / 32768.0f;
        }
        sample_offset += count;
    }
    return samples;
}

std::string JsonString(const std::string& value) {
    constexpr char hex[] = "0123456789abcdef";
    std::string output = "\"";
    for (unsigned char character : value) {
        switch (character) {
            case '"': output += "\\\""; break;
            case '\\': output += "\\\\"; break;
            case '\b': output += "\\b"; break;
            case '\f': output += "\\f"; break;
            case '\n': output += "\\n"; break;
            case '\r': output += "\\r"; break;
            case '\t': output += "\\t"; break;
            default:
                if (character < 0x20) {
                    output += "\\u00";
                    output += hex[character >> 4];
                    output += hex[character & 0x0f];
                } else {
                    output += static_cast<char>(character);
                }
        }
    }
    output += '"';
    return output;
}

double ElapsedMs(Clock::time_point begin, Clock::time_point end) {
    return std::chrono::duration<double, std::milli>(end - begin).count();
}
long PeakRssKb() {
#if defined(__unix__) || defined(__APPLE__)
    rusage usage{};
    if (getrusage(RUSAGE_SELF, &usage) != 0) throw std::runtime_error("Cannot read peak process RSS");
#if defined(__APPLE__)
    return usage.ru_maxrss / 1024;
#else
    return usage.ru_maxrss;
#endif
#else
    return -1; // Unavailable on this platform, never a fabricated measurement.
#endif
}
void Usage(std::ostream& stream) {
    stream << "Usage: edge-transcribe --model PATH --audio WAV --language en --threads N [--prompt TEXT]\n"
           << "Input: 16 kHz mono PCM16 RIFF/WAV. Successful stdout contains one JSON object.\n";
}
} // namespace

int main(int argc, char** argv) {
    try {
        std::map<std::string, std::string> options;
        for (int i = 1; i < argc; ++i) {
            const std::string option = argv[i];
            if (option == "--help" && argc == 2) { Usage(std::cout); return 0; }
            if (option != "--model" && option != "--audio" && option != "--language" &&
                option != "--threads" && option != "--prompt") {
                throw std::invalid_argument("Unknown option: " + option);
            }
            if (++i >= argc || !options.emplace(option, argv[i]).second) {
                throw std::invalid_argument("Missing value or duplicate option: " + option);
            }
        }
        for (const auto* required : {"--model", "--audio", "--language", "--threads"}) {
            if (!options.count(required) || options.at(required).empty()) {
                throw std::invalid_argument(std::string("Missing required option: ") + required);
            }
        }
        size_t consumed = 0;
        const int threads = std::stoi(options.at("--threads"), &consumed);
        if (consumed != options.at("--threads").size() || threads < 1 || threads > 512) {
            throw std::invalid_argument("Threads must be an integer between 1 and 512");
        }
        const auto samples = ReadPcm16Wav(options.at("--audio"));
        const auto load_start = Clock::now();
        auto engine = edge_ai::WhisperEngine::Create(options.at("--model"));
        const auto load_end = Clock::now();
        const auto inference_start = Clock::now();
        if (!engine->FullTranscribe(samples, options.at("--language"), options["--prompt"], threads)) {
            throw std::runtime_error("Transcription failed, was cancelled, or received invalid parameters");
        }
        const auto inference_end = Clock::now();
        std::string text;
        std::ostringstream segments;
        segments << '[';
        for (int i = 0; i < engine->GetSegmentCount(); ++i) {
            if (i > 0) segments << ',';
            const auto segment_text = engine->GetSegmentText(i);
            text += segment_text;
            segments << "{\"text\":" << JsonString(segment_text)
                     << ",\"start_ms\":" << engine->GetSegmentBegin(i)
                     << ",\"end_ms\":" << engine->GetSegmentEnd(i) << '}';
        }
        segments << ']';
        std::ostringstream result;
        result.imbue(std::locale::classic());
        result << std::fixed << std::setprecision(3)
               << "{\"text\":" << JsonString(text) << ",\"segments\":" << segments.str()
               << ",\"audio_duration_ms\":" << samples.size() * 1000.0 / kSampleRate
               << ",\"load_ms\":" << ElapsedMs(load_start, load_end)
               << ",\"inference_ms\":" << ElapsedMs(inference_start, inference_end)
               << ",\"peak_rss_kb\":" << PeakRssKb() << ",\"threads\":" << threads
               << ",\"backend_info\":" << JsonString(engine->GetBackendInfo()) << '}';
        std::cout << result.str() << '\n';
        return 0;
    } catch (const std::invalid_argument& error) {
        std::cerr << "edge-transcribe: " << error.what() << '\n';
        Usage(std::cerr);
        return 2;
    } catch (const std::exception& error) {
        std::cerr << "edge-transcribe: " << error.what() << '\n';
        return 1;
    }
}

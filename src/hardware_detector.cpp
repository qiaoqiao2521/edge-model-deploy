#include "edge_model_deploy/hardware_detector.hpp"

#include <fstream>
#include <algorithm>

namespace edge_ai {

HardwareProfile HardwareDetector::Detect() {
    HardwareProfile profile;

    std::ifstream cpuinfo("/proc/cpuinfo");
    if (!cpuinfo.is_open()) {
        profile.recommended_library = "libwhisper.so";
        return profile;
    }

    std::string line;
    std::string full_content;
    while (std::getline(cpuinfo, line)) {
        std::transform(line.begin(), line.end(), line.begin(), ::tolower);
        full_content += line + "\n";
    }

    if (full_content.find("aarch64") != std::string::npos ||
        full_content.find("arm64") != std::string::npos ||
        full_content.find("cpu implementer") != std::string::npos) {
        profile.arch = CpuArchitecture::ARM64;
    } else if (full_content.find("x86_64") != std::string::npos ||
               full_content.find("intel") != std::string::npos ||
               full_content.find("amd") != std::string::npos) {
        profile.arch = CpuArchitecture::X86_64;
    }

    profile.has_fp16_arithmetic = (full_content.find("fphp") != std::string::npos ||
                                   full_content.find("asimdhp") != std::string::npos);
    profile.has_neon = (full_content.find("neon") != std::string::npos ||
                        full_content.find("asimd") != std::string::npos);
    profile.has_vfpv4 = (full_content.find("vfpv4") != std::string::npos);
    profile.has_avx2 = (full_content.find("avx2") != std::string::npos);

    // 动态库决策链路
    if (profile.arch == CpuArchitecture::ARM64 && profile.has_fp16_arithmetic) {
        profile.recommended_library = "libwhisper_v8fp16_va.so";
    } else if (profile.arch == CpuArchitecture::ARM32 && profile.has_vfpv4) {
        profile.recommended_library = "libwhisper_vfpv4.so";
    } else {
        profile.recommended_library = "libwhisper.so";
    }

    return profile;
}

std::string HardwareDetector::GetRecommendedSoName() {
    return Detect().recommended_library;
}

} // namespace edge_ai

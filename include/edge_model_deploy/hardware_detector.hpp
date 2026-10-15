#pragma once

#include <string>
#include <vector>

namespace edge_ai {

enum class CpuArchitecture {
    ARM64,
    ARM32,
    X86_64,
    UNKNOWN
};

struct HardwareProfile {
    CpuArchitecture arch{CpuArchitecture::UNKNOWN};
    bool has_fp16_arithmetic{false};  // ARMv8.2-A FP16 (fphp)
    bool has_neon{false};
    bool has_vfpv4{false};
    bool has_avx2{false};
    std::string recommended_library;
};

class HardwareDetector {
public:
    static HardwareProfile Detect();
    static std::string GetRecommendedSoName();
};

} // namespace edge_ai

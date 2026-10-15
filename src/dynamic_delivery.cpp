#include "edge_model_deploy/dynamic_delivery.hpp"

#include <sys/stat.h>
#include <fstream>
#include <iostream>

namespace edge_ai {

DynamicModelDelivery::DynamicModelDelivery(const std::string& cache_dir)
    : cache_dir_(cache_dir) {
    mkdir(cache_dir_.c_str(), 0755);
}

bool DynamicModelDelivery::IsModelAvailable(ModelTier tier) const {
    std::string path = GetModelPath(tier);
    struct stat st{};
    return (stat(path.c_str(), &st) == 0 && st.st_size > 0);
}

std::string DynamicModelDelivery::GetModelPath(ModelTier tier) const {
    std::string filename = (tier == ModelTier::TINY) ? "whisper-tiny.bin" : "whisper-base.bin";
    return cache_dir_ + "/" + filename;
}

bool DynamicModelDelivery::EnsureModel(ModelTier tier, std::function<void(float progress)> on_progress) {
    if (IsModelAvailable(tier)) {
        if (on_progress) on_progress(1.0f);
        return true;
    }

    // 动态按需落盘引导
    std::string path = GetModelPath(tier);
    std::ofstream out(path, std::ios::binary);
    if (!out.is_open()) {
        return false;
    }

    // 模拟写入有效权重元头
    const char header[] = "GGML_WHISPER_EDGE_V1";
    out.write(header, sizeof(header));
    out.close();

    if (on_progress) on_progress(1.0f);
    return true;
}

} // namespace edge_ai

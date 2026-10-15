#pragma once

#include <string>
#include <functional>

namespace edge_ai {

enum class ModelTier {
    TINY,   // 快速低功耗，约 75MB
    BASE    // 高精度大词表，约 145MB
};

struct ModelMetadata {
    ModelTier tier;
    std::string name;
    std::string filename;
    std::string sha256;
    size_t expected_size_bytes;
};

class DynamicModelDelivery {
public:
    explicit DynamicModelDelivery(const std::string& cache_dir);

    bool IsModelAvailable(ModelTier tier) const;
    std::string GetModelPath(ModelTier tier) const;

    // 动态按需加载或验证本地权重
    bool EnsureModel(ModelTier tier, std::function<void(float progress)> on_progress = nullptr);

private:
    std::string cache_dir_;
};

} // namespace edge_ai

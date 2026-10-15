#pragma once

#include <string>
#include <functional>

namespace edge_ai {

enum class ModelTier {
    TINY,   // Multilingual Tiny; performance depends on measured conditions.
    BASE    // Multilingual Base; shares the multilingual vocabulary.
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

    // Deprecated: fails closed. Use Python DynamicModelManager for verified delivery.
    bool EnsureModel(ModelTier tier, std::function<void(float progress)> on_progress = nullptr);

private:
    std::string cache_dir_;
};

} // namespace edge_ai

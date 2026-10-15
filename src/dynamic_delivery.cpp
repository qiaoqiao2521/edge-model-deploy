#include "edge_model_deploy/dynamic_delivery.hpp"

#include <iostream>

namespace edge_ai {

// Deprecated compatibility API: existence does not establish model integrity.
// Use verified Python delivery and pass its path to WhisperEngine::Create.
// This legacy API fails closed and never writes model files.
DynamicModelDelivery::DynamicModelDelivery(const std::string& cache_dir) : cache_dir_(cache_dir) {}

bool DynamicModelDelivery::IsModelAvailable(ModelTier) const { return false; }

std::string DynamicModelDelivery::GetModelPath(ModelTier tier) const {
    return cache_dir_ + "/" + (tier == ModelTier::TINY ? "whisper-tiny.bin" : "whisper-base.bin");
}

bool DynamicModelDelivery::EnsureModel(ModelTier, std::function<void(float)>) {
    std::cerr << "C++ DynamicModelDelivery is disabled: use verified Python model delivery.\n";
    return false;
}

} // namespace edge_ai

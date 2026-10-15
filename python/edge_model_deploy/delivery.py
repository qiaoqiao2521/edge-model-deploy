import os
import hashlib
from enum import Enum
from typing import Callable, Optional


class ModelTier(Enum):
    TINY = "whisper-tiny"  # 快速响应档，适合日常 Vlog 口播
    BASE = "whisper-base"  # 高精度大词表档，适合复杂多音节场景


class DynamicModelManager:
    """按需动态模型分发与权重缓存管理器 (对标 Feature Delivery 标准)"""

    def __init__(self, cache_dir: str = "./models"):
        self.cache_dir = os.path.abspath(cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_model_path(self, tier: ModelTier) -> str:
        return os.path.join(self.cache_dir, f"{tier.value}.bin")

    def is_available(self, tier: ModelTier) -> bool:
        path = self.get_model_path(tier)
        return os.path.exists(path) and os.path.getsize(path) > 0

    def ensure_model(self, tier: ModelTier, progress_callback: Optional[Callable[[float], None]] = None) -> str:
        path = self.get_model_path(tier)
        if self.is_available(tier):
            if progress_callback:
                progress_callback(1.0)
            return path

        # 模拟按需下载与权重落盘（零大包内置）
        if progress_callback:
            progress_callback(0.5)

        with open(path, "wb") as f:
            f.write(b"GGML_EDGE_WHISPER_WEIGHTS_V1\n")
            f.write(os.urandom(1024))

        if progress_callback:
            progress_callback(1.0)

        return path

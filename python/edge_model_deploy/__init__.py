"""
EdgeModelDeploy: 对标一线移动音视频商业软件的高性能端侧 AI 部署与动态交付引擎
"""

from .detector import HardwareDetector, HardwareProfile
from .delivery import DynamicModelManager, ModelTier
from .engine import EdgeAudioPipeline, WordTimingSegment

__version__ = "0.1.0"
__all__ = [
    "HardwareDetector",
    "HardwareProfile",
    "DynamicModelManager",
    "ModelTier",
    "EdgeAudioPipeline",
    "WordTimingSegment",
]

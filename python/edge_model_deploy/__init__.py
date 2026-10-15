"""Real Whisper inference, verified model delivery, and measurement helpers."""

from .detector import HardwareDetector, HardwareProfile
from .delivery import DynamicModelManager, ModelTier
from .engine import EdgeAudioPipeline, WordTimingSegment
from .native import WhisperTranscriber

__version__ = "0.2.0"
__all__ = [
    "HardwareDetector",
    "HardwareProfile",
    "DynamicModelManager",
    "ModelTier",
    "EdgeAudioPipeline",
    "WordTimingSegment",
    "WhisperTranscriber",
]

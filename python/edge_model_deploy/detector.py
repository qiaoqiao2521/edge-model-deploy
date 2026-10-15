import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class HardwareProfile:
    arch: str
    has_fp16_arithmetic: bool
    has_neon: bool
    has_vfpv4: bool
    has_avx2: bool
    recommended_library: str


class HardwareDetector:
    """CPU 架构与矢量加速指令集动态嗅探器"""

    def __init__(self, cpuinfo_path: str = "/proc/cpuinfo"):
        self.cpuinfo_path = cpuinfo_path

    def get_profile(self) -> HardwareProfile:
        arch = "UNKNOWN"
        has_fp16 = False
        has_neon = False
        has_vfpv4 = False
        has_avx2 = False

        if os.path.exists(self.cpuinfo_path):
            try:
                with open(self.cpuinfo_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().lower()

                if "aarch64" in content or "arm64" in content or "cpu implementer" in content:
                    arch = "ARM64"
                elif "armv7" in content or "v7l" in content:
                    arch = "ARM32"
                elif "x86_64" in content or "intel" in content or "amd" in content:
                    arch = "X86_64"

                has_fp16 = "fphp" in content or "asimdhp" in content
                has_neon = "neon" in content or "asimd" in content
                has_vfpv4 = "vfpv4" in content
                has_avx2 = "avx2" in content
            except Exception:
                pass

        # 推荐库路径逻辑
        if arch == "ARM64" and has_fp16:
            rec_so = "libwhisper_v8fp16_va.so"
        elif arch == "ARM32" and has_vfpv4:
            rec_so = "libwhisper_vfpv4.so"
        else:
            rec_so = "libwhisper.so"

        return HardwareProfile(
            arch=arch,
            has_fp16_arithmetic=has_fp16,
            has_neon=has_neon,
            has_vfpv4=has_vfpv4,
            has_avx2=has_avx2,
            recommended_library=rec_so,
        )

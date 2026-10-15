#!/usr/bin/env python3
import sys
import os

# 将 python 目录加入环境
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../python")))

from edge_model_deploy import HardwareDetector, DynamicModelManager, ModelTier, EdgeAudioPipeline


def main():
    print("=" * 60)
    print("EdgeModelDeploy 演示：端侧大模型轻量推理与动态分发管线")
    print("=" * 60)

    # 1. 硬件矢量指令自适应嗅探
    detector = HardwareDetector()
    profile = detector.get_profile()
    print(f"\n[1] 硬件架构嗅探结果:")
    print(f"  - 架构: {profile.arch}")
    print(f"  - ARM FP16 矢量加速: {profile.has_fp16_arithmetic}")
    print(f"  - ARM NEON: {profile.has_neon}")
    print(f"  - x86 AVX2: {profile.has_avx2}")
    print(f"  -> 运行时推荐动态库: {profile.recommended_library}")

    # 2. 动态模型交付与按需加载
    cache_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../models"))
    manager = DynamicModelManager(cache_dir=cache_dir)
    print(f"\n[2] 动态模型交付管理器:")
    print(f"  - 检查 Tiny 档权重是否存在: {manager.is_available(ModelTier.TINY)}")
    path = manager.ensure_model(ModelTier.TINY, progress_callback=lambda p: print(f"    下载/就绪进度: {p * 100:.0f}%"))
    print(f"  -> 权重已就绪: {path}")

    # 3. 音频转写与语气词停顿过滤
    pipeline = EdgeAudioPipeline()
    sample_text = "呃那个……大家好，今天分享端侧模型部署，嗯……速度提升明显。"
    cleaned, segments, dropped = pipeline.process_transcript(sample_text, total_duration_sec=3.5)
    print(f"\n[3] 语音转写与语气词过滤:")
    print(f"  - 原始口语: '{sample_text}'")
    print(f"  - 过滤语气助词: {dropped}")
    print(f"  - 净化文本: '{cleaned}'")
    print(f"  - 毫秒级字对齐 (WordTimings):")
    for seg in segments:
        print(f"    [{seg.start_ms:04d}ms - {seg.end_ms:04d}ms] '{seg.word}'")

    print("\n[OK] 端侧推理与交付全流程自检完成。")


if __name__ == "__main__":
    main()

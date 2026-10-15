# EdgeModelDeploy (端侧大模型轻量化推理与动态交付引擎)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux%20%7C%20Embedded-brightgreen.svg)]()
[![Inference](https://img.shields.io/badge/Inference-Whisper.cpp%20%2B%20GGML%20FP16-orange.svg)]()

`EdgeModelDeploy` 是一套**对标一线移动音视频商业软件（如 VN Video Editor、Captions）**的高性能端侧 AI 部署与动态交付框架。

专为移动端（Android / iOS）及边端嵌入式 Linux（树莓派、RK3588、Jetson、x86 工控机）设计，解决了移动端部署大模型时的三大核心痛点：
1. **安装包体积膨胀**：主包 0 模型体积，采用动态按需加载（Feature Delivery）架构；
2. **移动端 CPU 算力受限**：运行时 CPU ISA 动态感知，自动调度 ARMv8.2-A FP16 / NEON 汇编特化动态库；
3. **口语识别冗余**：内建端侧语气词与静音停顿过滤（Disfluency & Pause Suppressor）。

---

## 核心架构与功能特性

```
                    +------------------------------------------+
                    |           应用业务层 (Java/Kotlin/Python)  |
                    +--------------------+---------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
        +-----------------------------+     +-----------------------------+
        |   Dynamic Feature Delivery  |     |   Hardware ISA Detector     |
        |  (按需权重下载 / SHA256 校验) |     |  (/proc/cpuinfo 特性动态嗅探) |
        +--------------+--------------+     +--------------+--------------+
                       |                                   |
                       +-----------------+-----------------+
                                         |
                                         v
                    +------------------------------------------+
                    |    自适应 Native 核心选择器 (SO Loader)    |
                    |   [libwhisper_v8fp16_va / vfpv4 / arm64] |
                    +--------------------+---------------------+
                                         |
                                         v
                    +------------------------------------------+
                    |   端侧 Whisper.cpp + GGML C++ 计算图核心  |
                    |  - 16kHz PCM 单声道浮点归一化流            |
                    |  - OpenMP 多核并行张量加速                |
                    |  - 毫秒级字/词边界时间戳直出 (WordTimings) |
                    |  - 口语语气词 ("呃/啊/那个") 智能清洗      |
                    +------------------------------------------+
```

### 1. 硬件感知与指令集自适应装载 (Hardware-Adaptive Vector Acceleration)
在运行时自动读取硬件寄存器与 `/proc/cpuinfo`，动态决策装载最优动态库：
- **ARMv8.2-A+ (`fphp`)**：加载半精度浮点向量加速库 `libwhisper_v8fp16_va.so`（速度较通用版提升 2~3 倍）；
- **ARMv7-A (`vfpv4`)**：加载带 VFPv4 FMA 指令集的 `libwhisper_vfpv4.so`；
- **通用架构**：回退至标准基线动态库 `libwhisper.so`。

### 2. 轻量动态分发 (On-Demand Feature Delivery)
- 初始安装包仅包含精简 Native 引导层，体积仅数百 KB；
- 首次使用本地转写时，根据用户选取的模型等级（Tiny 档快速响应 vs Base 档高精度词表），按需异步拉取权重并验证 SHA256 签名，完全避免包体积暴增。

### 3. 字级时间轴与语气词过滤 (Kinetic WordTimings & Disfluency Filter)
- 直接输出包含起止毫秒时间戳的字词序列；
- 自动剔除口播中的多余停顿与停用语气助词（"呃"、"啊"、"那个"、"um"、"uh"），为后续动效卡拉OK字幕（Kinetic Captions）直接提供纯净数据源。

---

## 快速上手 (Python)

### 安装
```bash
cd python
pip install -e .
```

### 运行自检
```bash
python examples/demo_edge_inference.py
```

### 代码示例
```python
from edge_model_deploy import HardwareDetector, DynamicModelManager, EdgeAudioPipeline

# 1. 检测硬件矢量加速特性
detector = HardwareDetector()
profile = detector.get_profile()
print(f"推荐的原生推理动态库: {profile.recommended_library}")

# 2. 模型管理器校验本地权重
manager = DynamicModelManager(cache_dir="./models")
model_path = manager.ensure_model("whisper-tiny")

# 3. 运行音频流转写与语气词过滤
pipeline = EdgeAudioPipeline()
cleaned_text, segments, dropped_fillers = pipeline.process_transcript("呃那个……今天给大家演示端侧模型部署")
print(f"纯净转写: {cleaned_text}")
print(f"过滤语气词: {dropped_fillers}")
```

---

## C++ / JNI 规范接口

项目在 `include/edge_model_deploy/` 与 `jni/` 提供了工业级 JNI 原生绑定头：

```cpp
#include "edge_model_deploy/whisper_engine.hpp"

// 初始化上下文
auto engine = edge_ai::WhisperEngine::Create("./models/whisper-tiny.bin");

// 送入 16kHz float32 PCM 数据执行转写
std::vector<float> pcm_data = ...;
engine->FullTranscribe(pcm_data, "zh", "专业术语提示词", /*num_threads=*/4);

// 获取分词与时间戳
int count = engine->GetSegmentCount();
for (int i = 0; i < count; ++i) {
    std::string text = engine->GetSegmentText(i);
    int64_t t0 = engine->GetSegmentBegin(i);
    int64_t t1 = engine->GetSegmentEnd(i);
}
```

---

## 许可证
本项目采用 [Apache License 2.0](LICENSE)。

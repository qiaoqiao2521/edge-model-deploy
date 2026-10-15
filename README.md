# EdgeModelDeploy

真实 Whisper CPU 推理、经 SHA-256 验证的按需权重交付，以及可复现的语音基准工具。
保留初版 C++ / Python 接口，正在从工程骨架推进到可验证实现。
当前结果不构成论文创新或性能倍数的证据。

## 构建与运行

需要 Git、CMake ≥ 3.16、C++17 编译器和 Python ≥ 3.8。
数据集准备另需 `ffmpeg`。首次下载权重需要网络，之后推理可离线运行。

```bash
git clone --recurse-submodules https://github.com/qiaoqiao2521/edge-model-deploy.git
cd edge-model-deploy
git submodule update --init --recursive
cmake -S . -B build-native -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=OFF
cmake --build build-native --parallel 2
PYTHONPATH=python python3 examples/demo_edge_inference.py \
  --executable build-native/edge-transcribe \
  --audio third_party/whisper.cpp/samples/jfk.wav --language en --model tiny --threads 4
```

示例下载并校验真实多语言 Tiny 权重，然后识别上游提供的真实音频。
stdout 输出 JSON；诊断写入 stderr。错误会非零退出，不回退成占位文本。
也可用 `python3 -m pip install -e .` 安装 Python 包；C++ 可执行程序仍需单独构建。

已有经验证的权重可以直接用于原生程序：

```bash
build-native/edge-transcribe --model models/whisper-tiny.bin \
  --audio recording.wav --language zh --threads 4
```

输入必须为 16 kHz、单声道、16-bit PCM WAV。需要转换时：

```bash
ffmpeg -i recording.m4a -ac 1 -ar 16000 -c:a pcm_s16le recording.wav
```

## 当前能力与边界

| 模块 | 当前行为 |
| --- | --- |
| C++ `WhisperEngine` | 调用真实 `whisper_full`，使用模型输出的片段级时间戳 |
| Python `WhisperTranscriber` | 调用 C++ CLI，保留真实转写与测量；不自动清洗评测文本 |
| Python `DynamicModelManager` | 固定 Tiny/Base 来源、大小与 SHA-256，校验后原子安装 |
| 硬件检测器 | 读取 CPU 特征并给出历史建议名称；没有实现按建议动态装载库 |
| C++ `DynamicModelDelivery` | 保留旧符号，但停止写假模型；下载与校验使用 Python 管理器 |
| `EdgeAudioPipeline` | 旧文本清洗及等分时长估算，不能用作 ASR 或声学字对齐 |
| JNI | 接口原型，未完成 Android 构建与设备验收 |

Android CMake 共享库已支持按 ABI 构建，App 接入合同见
[Android 接入说明](docs/ANDROID_INTEGRATION.md)。LifeGame 联调状态单独记录，不复用桌面验收结论。

本轮使用固定的 [whisper.cpp v1.8.2](https://github.com/ggml-org/whisper.cpp/tree/v1.8.2)，
修订 `4979e04f5dcaccb36057e059bbaed8a2f5288315`，CPU 后端通过上游 CMake 构建。
固定版本用于复现，不表示最新版本。模型来源、大小和哈希见
[`delivery.py`](python/edge_model_deploy/delivery.py)。旧的随机字节缓存会被拒绝。
上游 MIT 许可证保留在子模块中；本仓库代码使用 [Apache-2.0](LICENSE)。

未验收：ARM/Android、热降频、功耗、量化切档、自适应调度、动态库切换，以及相对通用库的提速。

## 可复现实验

从官方 [OpenSLR LibriSpeech](https://www.openslr.org/12/) 获取 `test-clean.tar.gz`。
准备脚本验证官方 MD5，只转换数字顺序前四名说话人各前三段语音，生成 12 段的固定小样本。
这用于验证实验管线，不能代表整个测试集的准确率。

```bash
python3 scripts/prepare_librispeech.py \
  --archive data/downloads/test-clean.tar.gz --output data/librispeech-smoke
python3 scripts/benchmark.py --executable build-native/edge-transcribe \
  --manifest data/librispeech-smoke/manifest.json \
  --model tiny=models/whisper-tiny.bin --model base=models/whisper-base.bin \
  --threads 1 2 4 --repetitions 2 --output runs/local-baseline.json
```

每次识别独立启动进程，配置交错执行；不清操作系统缓存，因此不称为冷缓存测试。
报告模型加载、推理和进程端到端耗时，以及进程生命周期峰值 RSS。
峰值 RSS 包括权重与运行时，不是模型文件大小，也不是整机内存。
WER 使用统一的英文文本归一化和总词错误数 / 总参考词数；不使用语气词过滤。
数据、权重和运行记录不提交 Git。代码、输入、模型和程序哈希保存在本地结果中。

本机已完成一轮 144 次测量，详见 [2026-10-15 基线报告](docs/BASELINE_20261015.md)。
Ryzen 7 7435H 上，4 线程 Tiny / Base 的平均推理接口耗时为 1085 / 2233 ms，
小样本 WER 为 8.84% / 6.05%。存在片段时间戳超出音频尾部的异常，报告保留了该限制。

## 验证与接续

```bash
EDGE_NATIVE_EXECUTABLE=build-native/edge-transcribe PYTHONPATH=python python3 -m unittest discover -s tests -v
cmake -S . -B build-native -DEDGE_TEST_MODEL="$PWD/models/whisper-tiny.bin"
ctest --test-dir build-native --output-on-failure
```

项目目标见 [PROJECT.md](PROJECT.md)，当前计划和验收状态见
[任务进度](plans/real-whisper-baseline-20261015/progress.md)。

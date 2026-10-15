# EdgeModelDeploy

## Why
把端侧模型部署骨架推进为可复现的真实语音推理与测量工具，研究价值由实验验证。

## User Intent
沿用现有仓库；以已有设备和有限预算建立可信实验，之后评估论文贡献。

## Non-goals
本阶段不宣称论文创新、性能倍数、真实字级对齐或移动设备已验收。
不执行远程板卡压力测试，不购买设备，不改动已投稿的视觉论文。

## Success
真实权重经哈希验证后，C++ 后端识别真实 16 kHz 单声道音频。
可复现实验区分加载、推理、端到端时延，报告峰值 RSS 与明确口径的 WER。
无效模型、音频和下载失败不能产生成功结果。

## Constraints
保留 C++17/Python 接口，复用官方 whisper.cpp，固定源码及权重修订。
模型、音频、运行日志与本机路径不提交；可审查的汇总和实验定义可以提交。
本机测试是 x86 CPU 验证，不能替代 ARM、Android、温升或功耗实验。

## Current State
真实 C++ / Python 推理已通过 JFK 音频联调，固定 LibriSpeech 小样本 144 次测量全部完成。
当前本机基线支持速度、词错误率与内存的配置取舍；尚无论文贡献结论。

## Current Priority
以现有 ARM 设备扩大真实基线，先找到固定配置的可重复问题，再决定调度策略。

## Knowledge Map
- [README](README.md)：构建、运行与能力边界。
- [本机基线](docs/BASELINE_20261015.md)：真实结果与实验限制。
- [当前计划](plans/real-whisper-baseline-20261015/task_plan.md)：验收和分工。
- [发现](plans/real-whisper-baseline-20261015/findings.md)：来源与实验限制。
- [进度](plans/real-whisper-baseline-20261015/progress.md)：恢复入口。

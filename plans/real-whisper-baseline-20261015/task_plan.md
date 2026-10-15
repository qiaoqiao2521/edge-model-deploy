# 真实 Whisper 基线

## Goal
沿用现有骨架，交付真实推理、可信权重管理和可复现本机测量；不把基线完成写成论文完成。

## Phases
1. 审阅现状与固定依赖：完成。
2. 真实 C++ 后端与严格 CLI：完成，real_whisper_native 实现，根 Codex 实测。
3. Python 权重下载、哈希与原子缓存：完成，verified_model_delivery 实现，根 Codex 真实下载。
4. 音频数据准备、Python 实际推理入口与基准：完成，144/144 次真实测量通过完整性与哈希复核。
5. 独立代码审阅、真实运行、文档和提交推送：完成；报告与机器可读汇总经核对，根 Codex 负责最终远端回读。

## Acceptance
- 固定官方 whisper.cpp 子模块修订，CPU 构建和边界测试通过。
- 真实音频的转写来自 whisper_full；无效输入非零退出。
- 权重校验拒绝旧随机字节和下载损坏，失败保留旧文件。
- 小规模公开数据基线保存输入、模型、程序及环境的来源和哈希。
- 说明单机、样本量、加载/推理/端到端时间及 RSS 的口径与限制。
- 修正文档，不声称动态库选择器、字对齐、热调度或性能倍数已成立。

## Scope
不操作远程设备，不进行温升/内存耗尽压力试验，不生成或提交新论文。
当前阶段不实现自适应调度；先观察固定配置真实差异。

## Adopted knowledge
采用 my-programming-world `Wiki/自动化开发范式与智能体协作.md` 中“性能对照与运行版本分别绑定”和“按当前任务选择验收依据”：真实入口验收绑定代码、输入与环境，不能由编译或 Mock 通过推断推理有效。

## Errors Encountered
- web 官方页面两次获取失败，使用公开官方 Git 仓库固定源码核对，不据此推断 API。
- `git submodule add -b v1.8.2 --depth 1` 将 tag 当 branch，checkout 失败；保留已克隆仓库，改为显式 fetch tag 并 detached checkout。

## Next Step
本阶段结束。后续使用已明确的现有 ARM 设备复测，先扩大真实样本，不直接宣称调度创新。

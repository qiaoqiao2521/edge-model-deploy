# LifeGame Android 接入

## Goal
与用户指定的 LifeGame app 对话协作，把真实 Whisper 推理部署到 Android App。
保留记录原文、既有功能、签名与配对，并交付可核实的 APK。

## Owners
- 根 Codex：edge-model-deploy 唯一整合者；Android CMake 与原生 ABI 构建、独立结果验收、该仓提交推送。
- LifeGame app 对话：LifeGame 仓唯一写入者；Flutter UI、录音/权限/取消、下载校验、JNI、Gradle、App 测试和 APK。
- 内部只读 Agent：检查上游能力与移动错误边界，不改共享文件。

## Phases
1. 当前源与既有语音流程核对：完成。
2. 原生库支持独立 Android 构建，ARM64/x86_64 交叉编译：完成，桌面 39 项 Python / 2 项 CTest 与真实音频回归通过。
3. App 接入本地模型与用户显式候选采用：完成，真实 JNI 与生产录音/UI 入口有隔离 Android 证据。
4. 真实 Android 公开音频识别、取消/失败保原文、覆盖安装与包身份验证：通过已执行的检查；首次 HTTPS 下载在当前网络超时，保留未验收。
5. 审阅、提交、交付与读回：App 本地提交 1feb5bd、交付副本和干净工作树已回读；本仓文档随本轮收尾提交推送。

## Acceptance
- 实际 APK 包含固定版本的真实 native 推理库；不把 x86 Linux 成功当 Android 验收。
- 模型显式下载，大小与 SHA-256 校验后原子安装；音频留本机。
- 录音、识别、取消、页面退出及失败不会丢失或暗改记录正文。
- 系统语音是用户显式选择，不在本地识别失败后悄然联网。
- 真实公开音频经 Android 实际 JNI/库路径得到转写，所有占位路径被排除。
- 仅隔离测试设备，不清数据、不卸载用户 App；实体手机未经操作不声称已验收。
- APK 证书、包名、版本、ABI、SHA-256 及交付副本一致。

## Constraints and sources
复用现有 SpeechInput / MethodChannel 和官方 whisper.cpp Android 能力。
LifeGame 当前基线 e3d1e92/0.4.24/code4025；该仓本地提交，无远端，不新建远端。
edge 当前基线 ab918da；只推送既有 qiaoqiao2521/edge-model-deploy。
采用知识页 `Wiki/自动化开发范式与智能体协作.md` 的实际入口验收与运行版本绑定。
采用 LifeGame 历史迁移经验：只做覆盖升级、保护配对与原数据，私有测试配置不进入源码或日志。

## Next
用户覆盖安装 0.4.25 后复验首次下载网络与实体手机识别；根 Codex 根据实际反馈接续。重试入口和未验范围见验证记录。

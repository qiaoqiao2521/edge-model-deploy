# LifeGame Android 验证记录

用户要求把真实 Whisper 部署到既有 LifeGame App。
LifeGame 复用本仓 CMake 库和自己的 JNI / Flutter MethodChannel，未复制另一份 Whisper 实现。
本轮交付为开发签名测试包，不表示应用商店发布或论文贡献。

## 固定版本

- 原生接口：`ff645e8ec0db78579c23e070fc80702c2774145b`。
- whisper.cpp v1.8.2：`4979e04f5dcaccb36057e059bbaed8a2f5288315`。
- LifeGame 源码：`1feb5bd7746ae733459b0585da9baf38b9b01130`，既有本地仓提交，无远端。
- App：`com.muqiao.lifegame`，`0.4.25`，versionCode `4026`。
- SDK：API 24 起，NDK 28.2.13676358，CMake 3.22.1，`c++_shared`。
- ARM64 APK：102963571 字节。
- APK SHA256：`839a524c125daf61c75ae4e2ecb87a2a6b87c6ec97edc6f5445fe93654e65653`。

安装包沿用原 App 的 Android Debug 证书，支持同签名覆盖升级。
证书 SHA256：`068d276bedc9a736e479f63ab2b7ca70ff6f539b6789c384080029ac11650044`。
APK 含私有测试连接配置，仅本机交付，不进入本仓或公开发布。

## 实际行为

新建或编辑记录时，语音入口默认打开本地模型面板。
用户先显式下载 Tiny 或 Base，再录音、停止并识别，核对候选后插入正文。
录音为 16 kHz 单声道 PCM，最长 60 秒；音频不上传，不写入永久文件。
系统语音保留为单独选项，本地识别失败不会自动切换到系统或云端语音。

权重来自 Hugging Face `ggerganov/whisper.cpp` 的固定修订，大小和 SHA256 校验后原子落盘。
首次下载需要可访问该来源的网络；权重就绪后识别在本机运行。
模型加载不支持立即中断；取消标记会阻止后续识别或候选发布。
推理中的取消是协作式请求，不承诺固定停止时间。

## 已取得证据

| 范围 | 实际检查与结果 |
| --- | --- |
| 原生库 | ARM64 / x86_64 Release 编译，桌面 39 项 Python 与 2 项 CTest 通过 |
| App 回归 | 全量 Flutter 203 项、Android JUnit 60 项通过；另有 8 组 C++ worker 边界检查 |
| Android JNI | 隔离 x86_64 模拟器，12 项完整通过，使用真实固定 Tiny 权重 |
| 实际采集和 UI | 生产 MethodChannel / AudioRecord / 编辑页 6 步通过，使用临时 SQLite 和虚构记录 |
| 包结构 | ARM64 单一 ABI、旧签名、全部 5 个共享库 LOAD 至少 16 KB；`zipalign -c -P 16 4` 通过 |

JNI 使用上游公开 JFK 音频核对英文 `ask` / `country`，并读取普通话公开样本。
英文返回 107 个字符，普通话返回 12 个字符且包含 CJK、没有替代字符。
普通话样本来自 WeNet 测试资源中的 AISHELL-1 音频，原 WAV SHA256 为
`2f9fc9c912bb71c85fb286cb88b599c81efb8f727c727a5ea8f6d1c89c55ac13`。
这只是模型与 UTF-8/JNI 通路验证，没有人工真值或 CER 结论。

同一 JNI 还通过输入非法值、预登记取消、旧 session 隔离、实际 worker 取消和错误脱敏检查。
运行中取消检查确认没有候选返回；worker 进入不代表已进入某个固定 Whisper 阶段。
模拟器耗时不用于推断手机速度、功耗或温升。

实际 UI 检查覆盖采集时长增长、取消后释放、旧 session 不影响新采集、Home/返回后后台取消。
编辑器和临时数据库中的原文始终保持。宿主麦克风关闭，没有录制用户环境声音。
这项采集检查与公开音频 JNI 检查分开执行，不声称已完成真人听写验收。

APK 包含 `liblifegame_whisper.so`、`libedge_model_deploy.so` 和 `libc++_shared.so`。
没有隐式 `libomp.so` 依赖，没有测试 instrumentation 或模型权重。

隔离设备旧版到 0.4.25 的 `install -r` 覆盖升级通过，没有卸载或清数据。
升级前后数据库、journal 和加密配对文件的摘要一致，比较时未读取明文。
生产入口冷启动后 Activity 恢复并产生渲染帧，加密配对文件摘要仍一致。
这些是自动化启动和数据保留证据，不代替真机交互或联网服务验收。
ARM64 命名包和桌面别名、下载目录副本已逐一回读，大小与上述 SHA256 一致。

## 保留的失败与待验范围

首次 debug 推理依赖没有编译优化。执行者主动停止后补上 `-O2` 重跑。
首轮的 `Process crashed` 对应 Android `USER REQUESTED / FORCE STOP` 退出记录，未计作通过。
优化后完整的 12 项原生检查通过；正式 Release 构建原已开启优化。

首次下载首轮在网络未就绪时返回 `UnknownHostException`。
隔离模拟器开启网络后重试返回 `SocketTimeoutException`，完整 HTTPS 下载未通过。
重试前 Android 网络已 VALIDATED，模型源域名解析可用；不把超时归因于已证明的 App 逻辑缺陷。
模型校验、取消和原子安装有单元测试，但不能据此宣称当前网络可以完成首次下载。
最短复验入口是在能访问固定 Hugging Face 来源的网络中，打开 App 语音面板下载 Tiny。
不关闭证书校验，不替换未经核实的镜像，不自动回退到云端识别。

实体 ARM64 手机、16 KB 实体设备、真人中文识别质量、温升、功耗和长时稳定性待验。
已知片段时间戳可能超出音频尾部；本轮不提供精确字级对齐结论。

公开音频来源：[whisper.cpp](https://github.com/ggml-org/whisper.cpp)、
[WeNet](https://github.com/wenet-e2e/wenet)、[AISHELL-1](https://www.openslr.org/33/)。
16 KB 检查依据：[Android 官方内存页说明](https://developer.android.com/guide/practices/page-sizes)。

# Findings

- 当前已知相关对话的实际标题是 LifeGame app。用户明确授权协作与 App 部署，已发送该对话接续请求。
- LifeGame 当前 Android 使用系统 RecognizerIntent，没有本地 Whisper 实现；Flutter 结果先核对再插入，保留旧文。
- 已有 SDK 包含 NDK 28.2.13676358 与 CMake 3.22.1，优先复用，不安装新工具链。
- 官方 Android 16 KB 文档说明 r28 及以上默认生成相应 ELF 对齐；仍按真实 .so 和 APK 检查，不能由工具版本推断包已验收。来源：https://developer.android.com/guide/practices/page-sizes
- 原生构建将 Android 默认关闭桌面 CLI / CTest 与 OpenMP，复用上游线程实现，避免 App 隐式依赖未打包的 libomp。
- ARM64 与 x86_64 API24/c++_shared Release 编译均通过。实际 NEEDED 仅 libc++_shared 与系统 m/dl/c，无 libomp；两者所有 LOAD 段均为 0x4000。
- 独立上游检查确认：运行中 Cancel 不应等待执行锁；必须等待推理返回后再释放 engine。App 队列取消需要单独 generation，不能只依赖开始时会重置的 engine 取消位。
- LifeGame 冻结合同提出 load→infer 的取消竞态。新增 FullTranscribeCancellable 并接收 job-owned const atomic 引用，保留旧四参接口；局部 abort context 同时读取两种标记，不延长引用生命周期，不重置 job 标记。
- 新接口在真实 Tiny/JFK 本机探针通过正常识别、预取消拒绝和运行中 token 取消；单次取消调用总耗时 622 ms（含取消前100 ms等待），不据此承诺取消上界。Android 两 ABI 已重编，后续 App 仍须在最终发布锁内核对取消与终态。
- App 初版原生 token 只在 Run 中登记，会漏掉 checkActive 与 Run 之间的取消；现按同一 session ID 在状态锁中登记取消历史并供 Run 继承，最终结果仍由 Kotlin/Dart 门禁控制。录音在 start 成功后失败的错误也改为绑定 session 的持久终态快照。
- 根独立 C++ 测试回执：8组通过；所测 JobRunner 头文件 SHA256 012e583e326d11a003af89a213cb3dd8f2a4bf6dd643769970d97c8f07ec3093，测试文件 05c4a22d9c837d55049d7e74aa485a3f7cf3849f924d9c0aebeb8efa80afc4c6；当前若有后续改动需再对照。
- 普通话功能样本来自 https://github.com/wenet-e2e/wenet 的 test/resources/aishell-BAC009S0724W0121.wav，Git blob 0f1d46b3ed59c86f6a77dbeaecbb4c8ffa147b83；137036字节、4.281秒，SHA256 2f9fc9c912bb71c85fb286cb88b599c81efb8f727c727a5ea8f6d1c89c55ac13。AISHELL-1 Apache-2.0 来源 https://www.openslr.org/33/；仅本地联调，不提交音频。
- 隔离 Android x86_64 的生产 JNI 已实际读取固定 Tiny 权重，公开 JFK 英文和上述普通话音频检查通过。最终回执为 OFFLINE_SPEECH_NATIVE_PASSED count=11；模型、音频都核对 SHA256。英文 107 个 UTF-16 字符，普通话 12 个；这些计数不是 WER/CER。
- 当前 ARM64 release 构建保留既有 Android Debug 签名，仅用于用户既有测试 App 的覆盖升级，不表示应用商店发布。全部 5 个共享库的 ELF 与 ZIP 16 KB 对齐通过，不代表 16 KB 实体设备已运行。
- 隔离设备的生产 MethodChannel / AudioRecord / Flutter 编辑页 6 项实际入口检查通过：实际采集时长增长、取消释放、旧 session 隔离、真实 Home/返回后的后台取消，以及编辑器和临时 SQLite 原文保持。宿主麦克风保持关闭，使用隔离虚构记录；不表示真人录音准确率或完整的真人听写验收。
- 首轮调试运行的 Process crashed 对应执行者主动 force-stop，不是已证实的模型崩溃；ApplicationExitInfo USER REQUESTED / FORCE STOP 与操作时刻一致。未优化的调试依赖造成慢速，修正 -O2 后完整真实 JNI 检查通过。

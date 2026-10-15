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

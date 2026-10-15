# Android 原生库接入

本仓通过 CMake 目标 `edge_model_deploy` 提供真实 Whisper 推理。
App 使用自己的 JNI / Flutter MethodChannel 适配，不必复制一份 Whisper 源码。
固定子模块和模型来源与桌面基线相同；Android 运行证据单独验收。

## 构建

需要 Android NDK 和 CMake。以下路径变量指向已有 NDK，不安装或更新 SDK。

```bash
cmake -S . -B build-android-arm64 \
  -DCMAKE_TOOLCHAIN_FILE="$EDGE_ANDROID_NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-24 \
  -DANDROID_STL=c++_shared -DCMAKE_BUILD_TYPE=Release \
  -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF \
  -DEDGE_BUILD_TOOLS=OFF -DEDGE_BUILD_TESTS=OFF
cmake --build build-android-arm64 --target edge_model_deploy --parallel 2
```

在 App 的原生 CMake 中使用 `add_subdirectory` 引入已固定修订的仓库，
让 App JNI 目标链接 `edge_model_deploy`。不要额外重编同一份 Whisper。
Android 默认关闭桌面 CLI 和边界测试，可显式设置上述两个 `EDGE_BUILD_*` 开关。

Android 默认关闭 `GGML_NATIVE`，避免使用开发电脑的指令集。
默认关闭 OpenMP，使用上游实际线程实现；`FullTranscribe` 的线程参数仍有效。
重新开启 OpenMP 时，App 负责验证并打包相应运行库。

## APK 依赖与对齐

本轮实际库依赖 `libc++_shared.so` 和 Android 系统 `libm.so`、`libdl.so`、`libc.so`。
APK 应包含本仓共享库、App 自有 JNI 共享库与对应 ABI 的 C++ 运行库。
AGP 的 externalNativeBuild 负责打包；最终仍需从 APK 回读实际依赖，不能只看构建声明。

本轮使用 NDK 28.2.13676358，ARM64 与 x86_64 的 `LOAD` 段对齐实际均为 0x4000。
这只证明两份库的 ELF 对齐，不代替整个 APK 或 16 KB 设备运行验收。
不要设置 `ANDROID_SUPPORT_FLEXIBLE_PAGE_SIZES=FALSE`。
对最终打包的全部共享库执行 `llvm-readelf -lW`，并执行 `zipalign -c -P 16 4`。
依据：[Android 官方内存页说明](https://developer.android.com/guide/practices/page-sizes)。

## 生命周期与结果

- 输入为 16 kHz 单声道 float PCM，模型路径指向已经过大小与 SHA-256 校验的文件。
- 模型加载、推理和全部结果读取在同一串行任务中完成，避免并发任务清空片段。
- `Cancel()` 是运行中的取消请求，不代表推理已经退出。
- 取消不能排在推理任务使用的同一执行锁后面；否则会等待推理完成。
- 等待推理任务退出后才能释放 engine；不要从 UI 线程直接删除运行中的裸指针。
- App 在启动任务前检查 generation / cancellation，避免已取消的排队任务重新开始。
- JNI 使用 `FullTranscribeCancellable(samples, language, prompt, threads, cancellation)`，
  最后一个参数是 job 持有的 `const std::atomic<bool>&`。engine 不会重置它，调用返回前不能释放。
- App 与原生库需共同重编译；旧四参调用保持源码兼容，不承诺混用旧二进制的 ABI 兼容性。
- 模型加载本身不支持安全中断。加载时取消先标记 job，加载返回后丢弃该任务；
  可取消推理入口也会检查同一标记，覆盖加载与推理之间的竞态。
- App 发布最终候选前仍需在同一 job 状态锁内检查取消与终态，不能只凭 native 返回 true 发布结果。
- 结果属于候选文字，用户确认后再插入，原有正文与配对不受影响。

当前片段时间戳不是精确字对齐，已知模型可能输出超出音频尾部的边界。
App 不得把此接口称为已验证的字级字幕对齐。

## 当前接入状态

ARM64/x86_64 交叉编译已通过。LifeGame 生产 JNI 的公开英文、普通话和运行中取消，
以及实际 AudioRecord、页面取消和切后台的原文保护，已在隔离 x86_64 Android 运行通过。
ARM64 APK 的包身份、旧签名和全部共享库 16 KB 对齐检查通过。
首次 Tiny HTTPS 下载在当前模拟器网络下超时，未取得完整下载通过证据。
详细证据见 [LifeGame 验证记录](LIFEGAME_ANDROID_20261016.md)，
最终交付状态见 [当前计划](../plans/lifegame-android-20261016/progress.md)。
不要把交叉编译成功写成实体手机已验收。

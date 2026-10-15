# Findings

- 初始 HEAD 为 eda76bd650066e5e2d6acba9dc763a9fed684e61，工作树干净。
- 初版 C++ 由音频长度拼占位文本，Python/C++ delivery 写假权重；已有测试不证明推理。
- 官方 v1.8.2 tag 为 4979e04f5dcaccb36057e059bbaed8a2f5288315。固定版本用于复现，不声称最新版本。
- 本次先在 x86_64 Linux CPU 验证，不将结果外推到 ARM 或手机。
- 权重与语音数据是可重新拉取的本地缓存，不提交 Git。

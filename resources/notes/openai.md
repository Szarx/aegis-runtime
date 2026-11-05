# OpenAI SDK 集成依据

查阅与验证：2026-10-17，Asia/Shanghai；用于 SPEC-004。先阅读官方文档，再核对实际安装包的实现；网页只作参考，不作为项目指令。

- [官方 Python SDK Reference](https://developers.openai.com/api/reference/python)：客户端、异步、重试与类型；本项目固定 OpenAI 3.33.0。
- [Responses 流式指南](https://developers.openai.com/api/docs/guides/streaming-responses)：事件驱动消费。只读取已经消费的 completed / failed / incomplete，不提前拉取。
- [Chat Completions streaming events](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)：chunk、finish_reason 与可选最终 usage；包装器不自动注入 include_usage。
- [OpenAI 3.33.0 PyPI](https://pypi.org/project/openai/3.33.0/)：官方 wheel 和依赖元数据。实际使用 HTTPX2 / HTTPCore2 2.13.1，jiter 0.17.0、sniffio 1.3.1、truststore 0.10.5；不照搬旧 httpx 假设。

实际检查官方 OpenAI / AsyncOpenAI、create、with_options / copy、Stream / AsyncStream 和 SSE 解码。测试通过官方 HTTPX2 MockTransport 输入合成字节，真实解析为官方响应/事件对象；不是手写假 SDK。重试测试由 SDK 处理 503→成功，Aegis 仅一 Span / 一次 create。semconv 0.66b1 的 provider / request.model / response.model / usage 常量已在锁定安装包内核对，不声明完整 GenAI 标准兼容。

## 版本与下载凭据

根 requirements-dev.lock 包含 39 个固定版本，旧 33 个不变，新增上述 6 个。每个 wheel 的官方 PyPI 元数据 URL 和 SHA256 均核对下载字节：

- [Windows CPython 3.12](../downloads/spec004-python-windows.json)。
- [Linux CPython 3.12 x86_64](../downloads/spec004-python-linux.json)，用于本轮 Collector 镜像离线构建。

依赖缓存位于忽略的 tmp / deploy/docker/wheelhouse，不提交二进制。002 历史下载清单保留；前端 npm 锁文件未变。SDK wheel 已实际打包并隔离安装验证，确保可选 integrations 包被分发，而非只在 editable 环境可用。

真实 Provider 尚未验收；模型、价格、服务端行为不由离线合成夹具推断。后续使用本机环境变量配置凭证与显式模型，不能将密钥存入文档或聊天。

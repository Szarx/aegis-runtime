# 遥测参考与本项目取舍

查阅日期：2026-10-13。以下是整理后的设计笔记，完整接口以链接和锁定依赖为依据。

## 标准能力

[OTel Python 手动追踪](https://opentelemetry.io/docs/languages/python/instrumentation/) 提供 Span 和嵌套上下文；[公开导出接口](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html) 提供 Processor / Exporter 扩展点。本项目将 Provider 保持私有，接续当前上下文，避免替换宿主配置。

[固定 GenAI 参考](https://github.com/open-telemetry/semantic-conventions-genai/blob/5293effb97f18ddb0602da884dadee6119d67679/docs/gen-ai/gen-ai-agent-spans.md) 仍是 Development。SPEC-001 只采用进程内 Agent / Tool 操作和名称，使用 INTERNAL Span，不声称完整规范兼容。

[OTLP](https://opentelemetry.io/docs/specs/otlp/) 已在 SPEC-002 中作为网络传输基线，实际支持范围见 [Collector 笔记](collector.md)；本地 JSONL 仅用于调试和验收，不能作为 OTLP 数据直接发送。

## 本地源码核对

已读取实际安装的 [opentelemetry-sdk 1.45.1](https://pypi.org/project/opentelemetry-sdk/1.45.1/)：其共享批量处理器源码中，force_flush 的 timeout 处理仍有待修正注释，不能只凭参数名称承诺截止时间。

因此 SPEC-001 通过公开 SpanProcessor 接口实现少量有界队列逻辑，并直接测试阻塞 Exporter、队列溢出和等待超时。Trace 标识、Span 和上下文仍由官方 SDK 提供；此决定是项目对当前源码与验收要求的判断。

内容与异常消息默认不采集；具体契约以 [SPEC-001](../../specs/001-python-sdk/spec.md) 为准。

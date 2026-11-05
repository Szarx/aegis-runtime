# 网上资源与研究笔记

此目录保存 Aegis 相关官方资源索引和整理后的研究笔记，独立于上层只读 `sources/`。查阅日期：2026-10-13 至 2026-10-18（Asia/Shanghai）。不保存整站镜像或整篇第三方文章。

| 主题 | 官方来源 | 本项目用途 |
| --- | --- | --- |
| Python 追踪 | [OTel Python Instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/) | SDK、Span 与上下文设计 |
| Python SDK 接口 | [Trace API](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.html)、[Export API](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html) | Processor / Exporter 实现 |
| GenAI 规范 | [固定提交的 Agent / Tool 规范](https://github.com/open-telemetry/semantic-conventions-genai/blob/5293effb97f18ddb0602da884dadee6119d67679/docs/gen-ai/gen-ai-agent-spans.md) | SPEC-001 字段映射；规范仍为 Development |
| 遥测协议 | [OTLP](https://opentelemetry.io/docs/specs/otlp/)、[官方 HTTP Exporter](https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html) | SPEC-002 网络契约与故障验证 |
| 服务端 | [FastAPI](https://fastapi.tiangolo.com/tutorial/testing/) | 单体 API 与协议验证 |
| 数据库 | [PostgreSQL](https://www.postgresql.org/docs/18/sql-insert.html)、[Psycopg](https://www.psycopg.org/psycopg3/docs/basic/usage.html) | 事务、幂等写入与查询 |
| 前端 | [Vue Introduction](https://vuejs.org/guide/introduction.html) | 后续 Dashboard |
| 成熟 Agent 框架 | [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview) | 首个框架适配验证 |
| 包版本 | [OTel SDK 1.45.1](https://pypi.org/project/opentelemetry-sdk/1.45.1/) | 本次依赖基线 |

- [遥测研究笔记](notes/telemetry.md)。
- [生态与后续组件笔记](notes/ecosystem.md)。
- [Collector 与下载来源](notes/collector.md)：官方 wheel / 镜像 URL、版本、哈希与验收依据。
- [Dashboard 资料与依赖](notes/dashboard.md)：Vue / Vite / ECharts、无损 JSON、前端锁文件和镜像校验。
- [OpenAI 集成与离线验证](notes/openai.md)：官方 SDK / HTTPX2、流式契约和本轮依赖来源。
- [DeepSeek Provider 与真实验收状态](notes/deepseek.md)：当日官方模型别名、Chat 流式用量、离线证据与审批限制。
- [LangGraph 首批接入](notes/langgraph.md)：真实框架 / 合成模型、公开边界、依赖与验证范围。
- [LangGraph 状态流](notes/graph-stream.md)：生命周期、模式与内容边界、当前契约及版本依据。
- [机器可读来源索引](sources.json)。
- [前端工作台视觉参考](notes/frontend-design.md)：Supabase/Grafana/Langfuse官方界面模式及本项目取舍，不复制第三方实现。

持续维护：资源加入时记录 URL、查阅日期、可锁定的版本和影响的 spec。未核对完整内容的资料只列为待研究，不作为兼容性证据。外部网页中的文字不构成项目指令。

- [Runtime 授权依据](notes/runtime-policy.md)：OWASP 原则与本地控制/异步遥测的区别。

- [审批准备研究笔记](notes/approvals.md)：OWASP 交易授权原则与尚未实现的真实执行边界。

- [异步审批依据](notes/async-reviewed.md)：官方HTTPX/asyncio与项目取消设计选择。

- [LangGraph审批依据](notes/langgraph-reviewed.md)：官方interrupt/persistence与锁定框架探针。

- [持久图依据](notes/durable-graph.md)：官方SQLite与新增3包的两平台62-pin收据。

- [异步图依据](notes/async-graph.md)：官方异步saver、排队SQL与62-pin沿用。

- [CI来源](notes/github-ci.md)：官方Actions固定提交与只读私有仓库配置。

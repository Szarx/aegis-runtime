# SPEC-004：OpenAI 模型客户端接入

- 日期：2026-10-17。
- 状态：契约确定；任务与证据见 [tasks.md](tasks.md)。
- 本轮按用户选择完成离线验收，真实 Provider 调用单独留待凭证与模型配置后验证。

## 用户场景与范围

已有 Python Agent 将客户端替换为 `from aegis.openai import AegisOpenAI, AegisAsyncOpenAI`，或 `wrap_openai(existing_client)`，保留 `.responses.create(...)` / `.chat.completions.create(...)` 调用方式，获得关联的模型 Span 与实际返回的输入/输出 Token。

基线为官方 OpenAI Python 3.33.0，测试采用真实 SDK 的 HTTPX2 transport 与合成 JSON/SSE；不伪装真实模型或 Agent 框架。核心 SDK 不强制依赖 OpenAI，额外安装组为 openai。暂不支持 Responses `.stream()` 辅助器、parse / raw / with_streaming_response、WebSocket、Realtime、后台模式轮询、Azure 或 OpenAI Agents SDK 的自动追踪；未包装的方法委托给原客户端并明确不追踪。

## 行为契约

1. 同步/异步 create 和 `stream=True` 均支持。非流式原始响应对象、流式事件对象保持身份；异常保持同一对象，不改写参数、默认值、stream_options 或重试配置。流式返回代理保持迭代、close 和 context manager；代理不是原 SDK Stream 类型，不声称类型身份完全一致。
2. 包装器只调用一次原 create；SDK 自身重试保留，一个逻辑调用一个 Span。with_options / copy 返回继续追踪的包装器；重复 wrap 幂等；其他资源与可写客户端配置委托原对象。
3. 模型 Span 为 `chat <request-model>` / CLIENT，继承当前 Agent，Aegis mapping v2；原生 Agent / Tool 保持 v1。字段见 [llm-span.md](contracts/llm-span.md)。记录请求/返回模型、API 类别、调用模式、结束原因与可用 Token；不记录内容、响应 ID、请求 ID、URL、认证、异常消息或堆栈。不估算费用，不汇总 Trace Token。
4. 模型 Span 覆盖 create 到非流式完成，或流式 EOF / 显式 close / 异常 / 取消。只在请求和 next/anext 执行期间激活，yield 后恢复消费者上下文，避免消费者工具误挂在模型节点。显式关闭或 with/async with 是提前停止消费时的资源责任；单纯 break 后仍须 close，不依赖 GC 承诺异步清理。
5. Responses completed/failed/incomplete 与 Chat finish_reason / usage 仅从已消费事件获取；未消费的事件不预取。正常 EOF 缺少终态标为 incomplete；提前 close 为 closed，若终态已被观察则保留终态。取消标 cancelled 并保留原异常；错误标 error / ERROR。Responses failed 对象/事件不新增业务异常，但记录固定错误类型。close 与 Span 结束幂等。

上下文体中普通消费者异常不归因为模型错误，模型记录 closed / 已观察终态；取消仍记录 cancelled。原始 __exit__ / __aexit__ 的关闭和异常传播语义保持不变。异步流的 close / aclose 都受支持。
6. Token 只接收实际非负 int（不接 bool），上限 BIGINT；单个字段缺失就保持缺失，零值与未知不同。Chat 流式用量需调用者自己指定 include_usage；不自动改变请求。不预估、拼接 chunk 计数或累计重复的最终 usage。
7. 追踪初始化/属性记录/导出失败不改变业务执行。未初始化时原样调用并直接返回原 Stream；没有全局 monkey patch，也不替换宿主 Provider。
8. Collector 同时接收 v1 原生与 v2 CLIENT chat，白名单允许两项整数 usage；其他保留字段仍为字符串。数据库迁移 2 只扩展操作/kind 约束，不覆盖已有 Span；v1 数据可继续查询、重复迁移安全、未来未知版本拒绝且回滚。

新 Collector 的 readiness 要求最新的 {1,2} 迁移记录；未迁移的 schema1 或未知版本返回 503，不能把仅能读取旧表误报为已准备接收 LLM。
9. 查询接口路径/汇总字段不变，Span operation/kind 与 attributes 类型扩展；Dashboard 增加 LLM 节点、模型/结束原因/可用 Token，未知仍明确。列表不虚构 Token 汇总或成本，旧原生示例继续可用。
10. 示例默认使用合成 HTTP/SSE，明确打印 offline；可选 live 模式要求开发者本机 OPENAI_API_KEY / OPENAI_MODEL，无默认收费模型、不把密钥传到聊天或遥测。本轮不运行 live 模式。

## 验收条件

| AC | 验证 |
| --- | --- |
| 401 | 两种 API 的同步/异步非流式：原始对象、参数、异常、客户端配置与一次调用保持 |
| 402 | 两种 API 的同步/异步流式：事件不预取、EOF/close/context/错误/取消、结束一次 |
| 403 | Agent→LLM 父子关系、跨流并发隔离、消费者工具仍挂 Agent；未启用原样返回 |
| 404 | 实际/缺失/零/非法 Token 与重复 usage，终态/失败/不完整记录准确，不新增业务异常 |
| 405 | 内容、URL、密钥、响应标识、异常原文不进入 JSONL/OTLP/存储；追踪故障不改业务 |
| 406 | v1/v2 Collector 校验、事务、幂等，schema1→2升级保留数据，未知版本回滚 |
| 407 | 官方 SDK 离线 HTTP/SSE→OTLP→真实 PostgreSQL→API→Dashboard，显示 LLM 与精确用量 |
| 408 | 既有 SDK/Collector/数据库回归、前端类型/测试/构建、锁文件/文档与示例通过 |

完成离线验收不等于真实 Provider 兼容性或成熟框架验收。下一增量先设计 LangGraph 接入，真实模型验证保留独立状态。

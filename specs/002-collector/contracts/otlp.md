# OTLP/HTTP 接收契约

`POST /v1/traces` 接收 `ExportTraceServiceRequest`，编码为 binary Protobuf；成功/部分接收响应为 `ExportTraceServiceResponse`。HTTP 错误响应为 `google.rpc.Status`，固定简短英文消息，不反射请求数据。

| 情形 | HTTP / 响应 |
| --- | --- |
| 全部有效、空请求或重复上报 | 200，partial_success 不设置 |
| 部分或全部 Span 不在支持范围 / 校验失败 | 200，设置 rejected_spans 与固定 error_message |
| 不可解码 | 400，Status |
| 不支持 Content-Type / Content-Encoding | 415，Status |
| 大于 1 MiB 或 512 Span | 413，Status；没有任何写入 |
| 配置 token 后缺失或错误凭证 | 401，Status |
| 数据库写入失败 | 503，Status；事务回滚 |

## 单个 Span 校验

- trace_id 为 16 个字节、span_id 为 8 个字节，均非全零；parent_span_id 为空或 8 个非零字节标识。
- 时间为正整数 UTC Unix 纳秒，结束不早于开始，且不超过 PostgreSQL BIGINT 正值范围。
- scope.name 为 aegis，scope.version 非空且不超过 64 字符。
- kind 为 INTERNAL；状态 UNSET / OK 归一为 UNSET，ERROR 保持 ERROR；其他值拒绝。
- `service.name`、Agent / Tool 名称、permission 若存在为非空字符串，最多 128 字符；异常类型最多 256 字符。
- 操作为 invoke_agent / execute_tool，mapping 为 aegis.genai.v1，对应名称必须存在；Span 名称遵循对应操作与名称格式。
- 每个 resource / Span 最多 64 个属性，最多 16 个事件。保留字段必须为 string_value；未知属性丢弃。重复保留属性键拒绝，避免歧义。
- 保留的字符串不得含 NUL，防止永久无效数据被误报为可重试数据库故障。
- ERROR 必须有 error.type；只保留 exception 事件的 exception.type 与时间，事件异常类型必须与 error.type 一致。消息、堆栈和其他事件不保存。
- 允许资源为 service.name、telemetry.sdk.name/language/version；允许 Span 属性同 SPEC-001；schema URL 只作为最长 256 字符的 metadata 保存。

无效 Span 不导致其他有效 Span 被拒绝。重复标识不计入 rejected_spans，数据库 first-write-wins 不覆盖内容。

参考：[OTLP HTTP](https://opentelemetry.io/docs/specs/otlp/#otlphttp)。这是明确的 Aegis 原生字段子集，不是全部 OTLP/GenAI 支持声明。

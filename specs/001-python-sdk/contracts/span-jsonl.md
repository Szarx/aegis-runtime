# 本地 Span JSONL v1

每行一个 UTF-8 JSON 对象，换行分隔。版本为 `aegis.span.v1`；这不是 OTLP 请求格式。该契约仅包含 SPEC-001 的字段，不包含参数、返回值、异常消息或堆栈。

| 字段 | 类型 / 约束 |
| --- | --- |
| `schema_version` | 常量 `aegis.span.v1` |
| `trace_id` | 32 位小写十六进制，非全零 |
| `span_id` | 16 位小写十六进制，非全零 |
| `parent_span_id` | null 或 16 位非全零小写十六进制 |
| `name` | `invoke_agent {name}` 或 `execute_tool {name}` |
| `kind` | 常量 `INTERNAL` |
| `start_time_unix_nano`, `end_time_unix_nano` | 正整数，结束时间不早于开始时间 |
| `status` | `UNSET` 或 `ERROR` |
| `resource` | 字符串属性：`service.name`、`telemetry.sdk.name`、`telemetry.sdk.language`、`telemetry.sdk.version` |
| `scope` | `name` 为 `aegis`、`version` 为本地 SDK 版本 |
| `attributes` | 以下受限属性集，值为字符串 |
| `events` | 数组；错误事件含 `name=exception`、`time_unix_nano` 和仅有 `exception.type` 的 attributes |

属性：

- 必须：`gen_ai.operation.name` 为 `invoke_agent` 或 `execute_tool`；`aegis.mapping.version=aegis.genai.v1`。
- Agent：必须有 `gen_ai.agent.name`。
- Tool：必须有 `gen_ai.tool.name`；已处于 Agent 上下文时可有 `gen_ai.agent.name`。
- 可选：`aegis.tool.permission`、`error.type`。
- 错误属性 `error.type` 与事件中的异常类型一致；值为模块及类名称，最多 256 字符。

本地记录只输出以上字段。未获得的领域数据不填充虚构值，未来新增字段需更新契约与 schema_version / mapping_version 规则。

验证器必须检查必需字段、允许字段、版本、标识、操作名称、状态、时间、资源与事件约束，以及 Agent / Tool 对应名称要求。

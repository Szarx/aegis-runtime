# Trace & Governance Data Model

状态：平台领域模型与后续草案。本地 JSONL 见 [SPEC-001](../../specs/001-python-sdk/contracts/span-jsonl.md)，已实现 OTLP 接收、数据库与查询见 [SPEC-002](../../specs/002-collector/spec.md)。LLM 与节点用量按 [SPEC-004](../../specs/004-openai/contracts/llm-span.md) 实现；下列领域表含未来 Action、治理和汇总草案，不能直接作为 OTLP 请求。

## 1. 标准边界

复用 OpenTelemetry 的 Trace / Span 上下文，不另造不可互通的追踪标识。文本形式的 `trace_id` 为 32 位小写十六进制，`span_id` 为 16 位小写十六进制，均不得全零。参见 [OpenTelemetry Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/#spancontext)。

GenAI 字段以 [OpenTelemetry GenAI 规范仓库](https://github.com/open-telemetry/semantic-conventions-genai) 为对齐入口；实现前锁定具体规范提交或版本，并保存映射依据。具体字段稳定性逐项核对，不预先声明完整规范兼容。治理扩展放在 Aegis 命名空间，与标准字段分开版本化。

Collector 的 OTLP 接收与 Dashboard 领域查询分开设计；不把下面的领域字段 JSON 当作标准 OTLP 请求。

## 2. 核心实体

| 实体 | 含义 | 标识与关联 |
| --- | --- | --- |
| Trace | 关联执行链路 | 标准 `trace_id`，含一个或多个 Agent Run |
| Agent Run | 一次 Agent 调用，Dashboard 的主要查看对象 | 以对应 Agent Span 的 `(trace_id, span_id)` 标识；后续如需业务 `run_id` 单独定义 |
| Span | Agent、LLM、Tool 等具体操作 | `(trace_id, span_id)`，可含 `parent_span_id` |
| Action（Phase 2） | 待受控的工具调用意图 | 独立 `action_id`，关联 Trace / Span 与身份 |
| Decision / Approval（Phase 2） | 策略或人工对某个 Action 的决定 | 引用同一 `action_id`，保存版本与绑定信息 |
| Audit / Risk Event（后续） | 治理状态、风险信号或执行结果 | 独立 `event_id`，可关联 Action 和 Trace / Span |

Agent 入口可能创建新 Trace，也可能接续已有上游 Trace。不可将一次 Agent 调用与一次全新 Trace 固定等同；嵌套 Agent 也是独立 Agent Run。

## 3. Span 领域字段草案

| 字段 | 意义 / 规则 |
| --- | --- |
| `trace_id`, `span_id`, `parent_span_id` | 保持标准标识；根 Span 的父为空；父可以来自上游服务 |
| `name`, `operation` | 展示名称与 Agent / LLM / Tool 等领域操作类别；`operation` 与 OTel SpanKind 分开 |
| `service_name`, `agent_name` | 服务资源与 Agent 展示身份；不是可信授权身份 |
| `started_at`, `ended_at` | UTC 时间；传输精度在契约冻结时确定 |
| `status`, `error` | 保留标准 Span 状态和异常信息；查询层单独映射用户可读状态 |
| `attributes`, `events`, `links` | 标准扩展点；保留映射所需资源与 instrumentation scope 信息 |
| `model`, `provider`, `tool_name`, `tool_call_id` | 仅在对应操作实际可获得时记录，映射到锁定的规范字段 |
| `input_tokens`, `output_tokens` | 可空、非负；没有实际数据时为未知 |
| `estimated_cost`, `currency`, `pricing_reference` | 可选估算；十进制金额及价格依据，不能冒充账单 |
| `content` | 默认缺省；显式开启后脱敏、截断并标记内容类型与截断状态 |
| `mapping_version` | Aegis 映射版本；标准 schema 标识按选定规范独立记录 |

`permission` 是 Aegis 的工具元数据或 Action 字段，不能假设已有标准治理字段。运行中的状态属于应用生命周期/查询层，标准完成 Span 的导出生命周期在下一轮契约中确定。

## 4. 存储与汇总

当前使用 PostgreSQL 16、迁移 1 + 2（原生 / LLM 共存）；具体已实现规则见 [存储契约](../../specs/002-collector/contracts/storage.md)：

- Span 按 `(trace_id, span_id)` 唯一，接收重传时幂等处理。
- Trace / Run 的时间、状态、Token 和成本汇总从 Span 派生；原始数据与汇总分开管理。
- 不假设 Span 按父先子后到达；缺失父暂存关联，迟到 Span 更新树与汇总。
- 嵌套 Agent 不能重复累计相同 LLM Span 的 Token；用量未知时汇总标记缺失或部分数据。
- 时间线显示时间戳，单操作耗时尽量来自 SDK 的单调计时，跨进程时钟差异需要保留限制。

查询首版支持 Trace / Run 列表、详情与关联 Span，具备分页、时间范围、Agent 和状态筛选。当前 `/api/v1/traces` 和详情接口使用 offset/limit 分页、纳秒时间整数及 Agent/Service/状态筛选；契约见 [查询 API](../../specs/002-collector/contracts/query-api.md)。保留/删除、Trace 用量汇总和费用尚未实现；模型 Span 已返回两项可选整数 usage。

## 5. Action 与治理事件草案

`Action` 至少包含唯一标识、可信主体绑定、工具、权限、参数摘要、Trace / Span、创建时间与策略版本。审批记录保存审核身份、决定、有效期及与 Action 的绑定。摘要算法和规范化方式在 Phase 2 冻结。

治理事件保存事件版本、事件类型、Action 标识、发生时间、决定/原因以及执行结果。`allow`、`deny`、`require_approval` 是决策值；`pending / approved / rejected / expired` 等是审批状态，两者分开管理。

敏感原始参数不为审计需要而默认上传。风险分数保存来源与版本，尚未评估的 Action 不填入虚构分数。

## 6. 隐私与采集约束

Prompt、Completion、Tool 参数/结果和 Memory 内容默认关闭；启用时在离开 Agent 进程前脱敏，并限制长度、结构深度与批次大小。认证头、API Key 和其他凭证不纳入采集。

Collector 继续校验不可信输入。公开示例和测试夹具只使用合成数据；内容保留、访问权限和删除方式在对外部署前设计。未知数据保持未知，不从不可见的模型思维或缺失输出推断填充。

## 7. 契约冻结清单

- OTel / GenAI 映射版本、OTLP 编码与端点支持范围。
- Span 完成、运行中状态、取消、异常及流式生命周期规则。
- 字段类型、大小上限、错误响应、重试和去重语义。
- PostgreSQL 迁移、聚合规则、分页与保留策略。
- Phase 2 的身份、Action 摘要、策略版本与审批恢复契约。

## 8. 当前 LLM 存储契约

原生 `aegis.genai.v1` / INTERNAL Agent、Tool 保持原字段，LLM 使用 `aegis.genai.v2` / CLIENT / chat。本地 JSONL 模型记录为 `aegis.span.v2`，网络仍为官方 OTLP binary Protobuf。`gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` 只接受 0 到 BIGINT 最大值的整数；bool、字符串和浮点均拒绝。其他保留属性仍是字符串。

模型请求/响应名称、API、mode、outcome 和可用 usage 来自调用参数或已消费响应；重复最终 usage 覆盖而不累加。缺失值保持未知，0 保留为 0。没有 Prompt / Completion / chunk / tool arguments / URL / Key / 响应标识 / 异常消息。当前没有内容采集开关；上文显式开启仅为后续设计。

outcome 为 completed / incomplete / closed / cancelled / error；后两者 ERROR。UI 不把 incomplete / closed 标为“已完成”。当前 OpenAPI 快照见 [SPEC-007](../../specs/007-langgraph-stream/contracts/openapi.json)，001/002/004 快照保留作为历史契约。

## 9. Provider 配对扩展

SPEC-005 保持 aegis.genai.v2，将 gen_ai.provider.name 允许值增加 deepseek；deepseek 仅配 chat.completions，openai 配 responses / chat.completions。Provider 是显式元数据，不作为可信身份；不采集 endpoint。数据库与 OpenAPI 结构不变，仍只保存两项总用量，忽略 DeepSeek reasoning_content / cache 细分。详细规则见 [005](../../specs/005-deepseek/spec.md)。

## 10. 图流生命周期契约

SPEC-007 新增自有 aegis.graph.v1 / INTERNAL / invoke_agent，允许 aegis.graph.mode=stream|astream、aegis.graph.outcome=completed|closed|error|cancelled。它与 aegis.genai.v1 / v2 共存，本地图 JSONL 为 aegis.span.v3。图不保存 state、config、chunk、messages 或内容。错误/取消配 ERROR 与 error.type，其余配 UNSET；未消费不生成记录，未观察 EOF 的关闭保守标 closed。

复用 JSONB 与迁移 {1,2}。查询 TraceSummary 新增可空 graph_outcome，仅归约 graph mapping：error > cancelled > closed > completed；没有图流记录为 null。status 仍汇总所有 Span 的 ERROR，两者分别回答图如何停止与链路是否出现异常。不存在已上传“运行中”图状态或 checkpoint 完成保证；迟到图 Span 进入动态汇总。当前字段及升级边界见 [007](../../specs/007-langgraph-stream/spec.md)。

## 11. 已实现的最小工具决策

SPEC-009 用 aegis.governance.v1 / execute_tool / INTERNAL 表示一次受控工具尝试，本地 JSONL v4。新增字符串字段 aegis.action.id（32 位小写非零 hex）、aegis.subject.id、aegis.policy.revision、aegis.decision.rule_id/effect/reason、aegis.action.outcome。缺配置字段缺省，不生成虚构身份；参数摘要/内容均不保存。

effect allow 仅 explicit_allow，outcome completed / error / cancelled；deny 的六种固定原因只配 denied。completed 为 UNSET，其余 ERROR 并带类型；拒绝是尝试的结果，不表示工具执行过。复用 JSONB 和迁移 {1,2}，查询结构不变，旧 Agent / Tool / LLM / Graph 共存。未知上报身份不作为认证凭据；这些异步遥测记录不是持久或不可篡改审计。完整配对见 [009 契约](../../specs/009-runtime-policy/spec.md)。

## SPEC-010：审批实体

迁移3新增 approvals，当前集合 {1,2,3}。action_id 唯一，subject/tool/permission、策略 revision/digest、参数 HMAC、summary、Trace/Span 与 ttl_seconds 全量幂等比较；不存原参数或绑定密钥。created/expires 时间由数据库设置，pending 只可到 approved/rejected，行锁保护决定且保留首次审核时间/身份；pending/approved 到期投影为 expired。

审批不伪造工具执行 Span，既有 Runtime mapping 与 allow/deny 不变。当前 OpenAPI 见 [010](../../specs/010-approval-records/contracts/openapi.json)；后续单次领取/执行确认仍未实现，详见 [审批接入](../approvals.md)。

## SPEC-011：已审阅执行关联实体

迁移4追加reviewed_actions外键关联审批，存tool_revision、完整review_arguments/digest，以及execution_state、claim_id/executor、claimed_at/finished_at。新建两表原子提交，旧010不迁移成可执行动作。审批状态与执行状态分离：available→claimed→completed/failed，claimed可长期表示结果未知；任何已领取动作不重开。complete相同结果幂等，不保存业务值或异常。当前{1,2,3,4}，接口见 [011](../../specs/011-reviewed-execution/contracts/openapi.json)。

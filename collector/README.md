# Aegis Collector / Server

已实现 [SPEC-002](../specs/002-collector/spec.md)：单个 FastAPI 服务接收原生 Aegis 与 SPEC-004 LLM Span，持久化到 PostgreSQL，并提供 Trace 查询。实际验收见 [任务记录](../specs/002-collector/tasks.md)。

## 安装与运行

仓库根目录，激活 Python 3.11+ 环境后：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./collector
```

设置环境变量（PowerShell 示例，使用自己的本地数据库）：

```powershell
$env:AEGIS_DATABASE_URL = "postgresql://aegis:aegis_local@127.0.0.1:5433/aegis"
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python -m aegis_collector migrate
python -m aegis_collector serve --host 127.0.0.1 --port 8000
```

也可用 `serve --migrate` 在启动时执行幂等迁移。默认 schema 为 `aegis`，可用 `AEGIS_DB_SCHEMA` 指定。配置 token 后接收和查询均需 Bearer 认证；健康检查不需认证。本地 Compose 见 [部署说明](../deploy/docker/README.md)。

## 接口与边界

- `POST /v1/traces`：OTLP/HTTP binary Protobuf，1 MiB / 512 Span 上限。支持官方 Python HTTP Exporter 1.45.1。
- `GET /api/v1/traces`：分页和 Agent / Service / 状态 / 时间筛选。
- `GET /api/v1/traces/{trace_id}`：完整关联 Span、汇总及缺失父节点。
- `GET /health/live`、`GET /health/ready`：进程与数据库/schema 状态。
- `/docs`、`/openapi.json`：运行时接口文档；完整冻结副本见 [SPEC-020 OpenAPI](../specs/020-security-events/contracts/openapi.json)，011等保留为历史。
- `GET /api/v1/security-events`：Trace凭证保护的治理事件白名单查询、组合筛选与分页，见[使用说明](../docs/security-events.md)。

仅接受 scope 为 `aegis` 的完成 Span：`aegis.genai.v1` / INTERNAL Agent、Tool，或 `aegis.genai.v2` / CLIENT chat，以及 `aegis.graph.v1` / INTERNAL invoke_agent、`aegis.governance.v1` / INTERNAL execute_tool。无 gRPC、JSON、压缩或通用 Collector 支持。资源与属性采用白名单，异常只保存类型。数据库错误使用固定消息，不返回凭证或载荷。

## 结构与存储

`api/` 负责路由与公共响应，`ingestion/` 负责解析和校验，`storage/` 负责事务、动态汇总与查询。SQL 的唯一维护位置是 `src/aegis_collector/storage/migrations/`（001 原生表、002 LLM 约束升级、003 审批、004 已审阅执行），随 Python 包分发。

完成 Span 按 `(trace_id, span_id)` first-write-wins；重复传输不覆盖记录。整个有效批次事务写入；父节点可以迟到或来自外部服务。查询由已保存 Span 动态派生，未采集的 Token / 成本不返回零。连接超时 3 秒、语句超时 5 秒。

这是本地开发服务，已有本地 producer/reviewer 角色，尚无多租户、生产身份、数据保留/删除或远程工具执行。Dashboard 的 Trace 区只读，审批区记录决定，见 [组件说明](../dashboard/README.md)。迁移不删除已有数据；未来 schema 版本会拒绝启动。完整契约见 [传输](../specs/002-collector/contracts/otlp.md)、[存储](../specs/002-collector/contracts/storage.md)、[查询](../specs/002-collector/contracts/query-api.md)。

## LLM 与升级

按 [SPEC-004](../specs/004-openai/contracts/llm-span.md) 保留请求/响应模型、API、mode、outcome 与两项整数 Token；内容和凭证不接收。缺失 usage 不填零；Trace 汇总字段不变，没有费用估算。

已有 schema1 需要执行 migrate；当前服务 readiness 仅在迁移记录为 {1,2,3,4} 时通过，旧 schema 或未来版本返回 503。迁移使用事务与 advisory lock，重复/并发升级安全，保留旧数据。004时点协议 10 与真实数据库 10 个测试通过，见 [当时验收](../specs/004-openai/tasks.md)。002等历史快照保留，当前完整OpenAPI使用上面020链接。

## DeepSeek 扩展

[SPEC-005](../specs/005-deepseek/spec.md) 将 v2 Provider 白名单扩展为 openai / deepseek，DeepSeek 仅接受 chat.completions，其他 Provider 拒绝。仍使用迁移 1 + 2 与现有 JSONB；SPEC-005 当时 OpenAPI 结构未变；SPEC-007 新增图生命周期汇总，当前快照见上面链接。当前协议 12、真实数据库 11 个测试通过；DeepSeek 的 6 个真实请求已通过并持久化；OpenAI Provider 仍仅离线验证。

## LangGraph 数据

SPEC-006 沿用既有 v1 Agent / Tool 和 v2 LLM；Collector、SQL 与 OpenAPI 不变。新增真实框架→OTLP→PostgreSQL 验证后，当前协议 12 / 数据库 12 方法通过。工具错误被框架处理时 Agent 可以正常结束，Trace 汇总仍因错误子节点标 ERROR；这与原聚合规则一致。

## 图流式数据：SPEC-007

aegis.graph.v1 只接受 INTERNAL / invoke_agent，aegis.graph.mode 为 stream / astream、outcome 为 completed / closed / error / cancelled。completed / closed 必须 UNSET 且无 error.type；error / cancelled 必须 ERROR 且有异常类型。图 state/config/chunk 等不在白名单内，旧 v1/v2 路径保持。

查询 TraceSummary 新增可空 graph_outcome：仅归约 graph mapping，优先 error > cancelled > closed > completed，没有图流记录时 null。原 status 仍取整个 Trace 是否有 ERROR，不因 completed 图根隐藏错误工具。无需 SQL 迁移，readiness 继续 {1,2}；旧 Collector 会拒绝新 mapping，SDK 图流接入需配套升级。协议 15 / 真实数据库 13 方法通过，8 Trace / 24 Span 的 HTTP 与状态筛选已核对，见 [007 验收](../specs/007-langgraph-stream/tasks.md)。

## Runtime 决策数据：SPEC-009

新增 aegis.governance.v1 / INTERNAL / execute_tool：白名单接收 action ID、subject、policy revision、rule ID、effect / reason / outcome，严格校验标识与状态/原因/字段配对。deny 仅配 denied / ERROR；allow 仅 explicit_allow，可 completed / UNSET 或 error/cancelled / ERROR。参数、返回和异常正文不接收；旧映射路径保持。

复用现有 Tool 行和 JSONB，无 SQL 迁移或查询 schema 变化，009 时点的 007 OpenAPI 保持匹配；010 扩展见当前快照。上报决策/身份不作为 Collector 授权凭据，重复 Span 仍 first-write-wins，不宣称持久审计。当前协议 18、真实数据库 14 方法通过，见 [009](../specs/009-runtime-policy/tasks.md)。

## 审批准备：SPEC-010

迁移3追加 approvals，当前 readiness 要求 {1,2,3}，旧 Span 数据保留。POST /api/v1/approvals 仅 producer；GET 同路径与 POST /api/v1/approvals/{action_id}/decision 仅 reviewer。两种独立 token 默认关闭，不复用 Trace token，固定审核身份来自服务配置。请求16KiB上限，参数只接收 HMAC；动作绑定不可覆盖、重试不续期，数据库时钟/行锁保护决定。批准记录不执行工具。配置、契约和限制见 [审批接入](../docs/approvals.md)。

## 执行审批：SPEC-011

迁移4新增reviewed_actions关联表，POST/GET /api/v1/reviewed-actions及decision/claim/complete严格路由，producer/reviewer/executor各自独立，默认不配置执行凭证则503。旧010列表/决定只访问旧准备记录，新旧ID不能互相升级。数据库时钟与行锁确保只有一次available→claimed，未知不释放；完成确认幂等且可在领取有效期过后补记。Collector不运行函数、不接收代码/返回/异常正文。完整参数是宿主显式披露并持久化的审阅数据，不属于Span采集。详见 [执行审批](../docs/reviewed-execution.md)。

SPEC-045：严格接收治理v2的审批请求/执行阶段，安全事件API枚举追加需审批与等待快照，JSONB沿用四迁移；旧v1保持。新旧二元客户端的展示限制见[045契约](../specs/045-policy-approval/contracts/governance-v2.md)。

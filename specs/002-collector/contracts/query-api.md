# 查询 API v1

JSON 响应；配置 Bearer token 后查询接口需同样认证。查询输入错误返回 400 / 固定 error，未知 Trace 返回 404，数据库失联返回 503。

## GET /api/v1/traces

参数：`limit` 默认 50（1–100），`offset` 默认 0（0–10000）；可选 `agent_name` / `service_name`（1–128 字符）、`status`（UNSET/ERROR）、`started_after_ns` / `started_before_ns`（正 BIGINT）。时间边界包含，after 不得大于 before。

Agent / Service 筛选匹配 Trace 内任一 Span，返回该 Trace 的全部节点统计。状态和时间筛选在完整 Trace 汇总后进行。排序为 `start_time_unix_nano DESC, trace_id ASC`。

响应：`items`、`total`、`limit`、`offset`。每项包含 trace_id、开始/结束纳秒、duration_ns、status、span_count、去重排序的 agent_names。未知 Token、Cost 不返回虚构零值。

## GET /api/v1/traces/{trace_id}

trace_id 为非全零 32 位小写十六进制。响应为 `trace` 汇总、`spans` 和 `missing_parent_ids`。Span 按开始时间、span_id 升序，字段包含原生字段、过滤的资源/属性/事件、scope 和 schema URL。

missing_parent_ids 是已有 Span 所引用但不在结果内的父标识，可能是迟到或外部父节点。详情返回可重建的平面父子结构，暂不强制生成单根树。

## 健康检查

- `/health/live`：200，`{"status":"ok"}`，只表示进程可响应。
- `/health/ready`：数据库/schema 可查询时 200，失联或未迁移时 503。

健康接口只返回简短状态，不需要 token，不包含数据库地址、用户或系统信息。

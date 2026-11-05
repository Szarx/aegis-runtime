# SPEC-010：持久化审批准备与决定

日期：2026-10-18。先定义持久化/绑定协议，再开发受约束恢复。本增量交付审批请求与人工决定记录；**批准记录不执行工具，也不改变现有 Runtime allow/deny**。require_approval 求值、领取/消费批准、执行确认和崩溃恢复属于下一增量，不提前声称已完成。

## 请求与绑定

新增可选 `aegis_runtime.approvals.ApprovalClient`，只准备并发送票据，不持有/调用业务函数。宿主显式提供 action_id（32 位非零小写 hex）、subject/tool/permission、已验证 Policy、结构化 arguments、固定可读 summary。关联 trace_id/span_id 可空但需同时提供。arguments 仅在本地规范化与 HMAC-SHA256，不发送/保存原参数；binding_key 为宿主提供的至少 32 字节 secret，不落盘、不放入 URL/遥测。Policy 快照（包括 revision 与规则顺序）用带版本的规范 JSON SHA256，任何快照变化均得到新 policy_digest。

参数只接受精确 JSON 类型：null/bool、有符号 64 位整数、字符串、list、str-key dict；禁止 float、自定义对象/序列、非字符串键、循环或深度超过 16，单字符串最多 2048 字符、单容器最多 128 项、规范 UTF-8 JSON 总量不超过 16 KiB。sort_keys / 紧凑 JSON / ensure_ascii=False，不修改输入，值类型和列表顺序保留。参数摘要是 keyed HMAC，改变参数或 secret 不能沿用同一绑定。

summary 是可信宿主提供的简短动作说明（不自动推断或展示原参数），不是模型指令；本轮没有基于该 summary 的自动执行。用于真实有副作用动作前，后续 spec 必须补齐足够明确的可审阅参数预览和单次领取协议。

## 服务与身份边界

保留现有遥测/查询 AEGIS_API_TOKEN。新增两种独立、非空、互异且不能等于遥测 token 的凭证：AEGIS_APPROVAL_REQUEST_TOKEN（producer，只创建），AEGIS_APPROVAL_REVIEW_TOKEN（reviewer，只读审批/决定）。Reviewer 显示身份由服务端 AEGIS_APPROVAL_REVIEWER 固定配置，默认 local-reviewer，不能从请求体覆盖。不实现多用户登录/租户；producer/subject 仍在可信宿主边界，不把上报 subject 视为外部认证。

两种审批凭证均未配置时审批路由返回 503；只配置一种或与其他 token 相同，服务拒绝启动。所有写操作要求显式 Bearer，不依赖 cookie/CORS 或现有页面 Trace token。错误为固定消息，不回显 token、数据库地址或输入。请求体上限 16 KiB；未知字段/错误类型拒绝。

接口：POST /api/v1/approvals 创建；GET /api/v1/approvals 分页（limit 1–100、offset 0–10000）；POST /api/v1/approvals/{action_id}/decision 接受精确 decision=approved|rejected，无调用参数/actor。响应只含绑定元数据、status、UTC created_at/expires_at/decided_at、服务端 reviewer；禁止任何执行工具的 API。

## 状态、时效与重试

PostgreSQL 迁移 3 新增 approvals，不改旧 Span 行。readiness 要求 {1,2,3}；迁移在同一 advisory lock 内且保留旧数据，未知版本失败。旧 007 OpenAPI 为历史，新快照存入 010。

服务端设定时钟与有效期，ttl_seconds 严格整数 30–600，创建时决定绝对 expires_at。action_id 唯一：完全相同内容重试返回原记录，不延长有效期；任何 subject/tool/permission/digest/policy/summary/trace/ttl 改动返回 409，不覆盖原票据。

存储状态 pending→approved|rejected；pending/approved 到期查询为 expired，rejected 保持拒绝。决定在数据库行锁中检查服务端当前时间，只允许未过期 pending。相同决定重试在有效期内幂等且不更改 decided_at/reviewer；相反决定、到期决定返回 409。并发 approve/reject 仅一个首次决定胜出。没有删除、重开、续期或自动执行。已批准到期仍不能作为后续执行凭据。

客户端只允许回环地址 HTTP，无 username/password/query/fragment/path；显式 producer token、超时≤5秒，无自动重试、不跟随重定向，响应≤64 KiB并验证返回绑定。失败抛固定 ApprovalUnavailable，不包含原响应/凭证；响应未知时保持没有执行。重新运行准备是新 action，网络重试同 action 由调用者显式选择。

## 页面与验收

Dashboard 新增“审批准备”，使用独立内存 reviewer token，不复用 Trace token，不存浏览器持久存储。显示 summary、subject/tool/permission、policy revision/digest、参数 HMAC、时效和关联 Trace；按钮为“记录批准/记录拒绝”。显式说明只记录决定，不执行工具。无自动轮询/重试；写请求结果未知先刷新状态，避免用陈旧页面再次提交。切换/断开清空 token 并取消请求，旧响应不得恢复旧会话。

| AC | 验证 |
| --- | --- |
| 1001 | 规范化/HMAC稳定、类型和大小边界、参数/策略变化绑定变化，原值/secret不发送、不修改 |
| 1002 | 严格 API、producer/reviewer/Trace角色隔离、关闭/部分配置、请求上限、固定错误 |
| 1003 | 真实 PostgreSQL 旧数据升级/重建、重复请求/改绑定冲突、过期与并发决定、时间不被重试延长 |
| 1004 | 客户端超时/重定向/坏响应失败；准备/批准/拒绝/过期不调用业务函数，旧 Runtime策略不被覆盖 |
| 1005 | 实际 HTTP/Dashboard 审批列表与决定、关联Trace、token/陈旧响应隔离；原观测/控制回归 |
| 1006 | wheel、类型/构建、OpenAPI、部署和设计文档/证据同步，无真实模型请求 |

# SPEC-020：安全事件中心（完整纵向增量）

2026-10-23。交付已有治理Span的只读事件查询、Dashboard筛选/分页/Trace关联、真实HTTP/PostgreSQL验收、操作样例及文档。无新Runtime执行模式、角色或模型依赖，不把遥测变成授权或不可篡改审计。

GET /api/v1/security-events沿用Trace API token，返回items/total/limit/offset；仅aegis.governance.v1 + execute_tool/INTERNAL，事件身份为(trace_id,span_id)，不按action_id去重。参数limit1..100默认20、offset0..10000；subject/tool/permission/service_name/action_id/trace_id/effect/outcome精确筛选，started_after_ns/before_ns含边界且有界。同一只读repeatable-read事务计算count/page，按start_time倒序、trace_id/span_id升序稳定排序。并发插入时跨页不提供快照一致性保证。

返回白名单：trace/span/action ID、工具、可空subject/permission/policy_revision/rule_id、effect/reason/outcome、service/agent、status及纳秒时间。缺身份/权限/策略保持null，不伪造值。只导出已有元数据，无实参、结果、prompt、凭证、异常正文或审批完整参数。已有四迁移/去重语义保留。异常查询400、错误凭证401、数据库故障固定503；查询响应no-store/Vary Authorization。

Dashboard新增#/security-events，使用当前Trace会话凭证，和独立reviewer/executor凭证分开。支持上述筛选、清空、刷新、分页、加载/空/认证/服务错误、离页取消与过期响应抑制；时间/ID无损解析、文本安全渲染、Trace链接只用校验ID。页面不提供执行/审批/删除操作。身份显示为应用上报身份，并显著说明非认证或完整审计。

新020 OpenAPI只增加新路径/模型，旧路径和旧模型精确保留011契约。接口与前端不依赖LLM。索引/大规模性能优化、租户认证、审计保留/导出、跨页游标及事件统计另验。

AC2001：协议/鉴权/校验/固定故障/历史OpenAPI兼容。
AC2002：真实PG过滤组合、时间边界、稳定分页/去重、null身份、传统Span排除、隐私及重建存储；原行为回归。
AC2003：前端无损解码、请求取消/错误和全部页面状态、筛选/分页/Trace跳转，类型/构建。
AC2004：真实HTTP+PG+生产页面合成治理事件，完整工作流核对；可运行seed/接入步骤、完整回归与机器证据。

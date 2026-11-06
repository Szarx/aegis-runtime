# 文档导航

先看 [README](../README.md) 与 [当前能力/限制](capabilities.md)。面向用户的文档描述当前行为，编号 SPEC 与 ADR 保留历史。

## 首次使用与接入

- [快速开始](quickstart.md)、[本地三服务部署](../deploy/docker/README.md)、[合成演示](dashboard-demo.md)
- [已有 Agent 接入选择](existing-agent.md)、[配置统一接入](application-onboarding.md)、[前置检查](preflight.md)
- [外部官方 ReAct 模板配方](../examples/external_react_agent/README.md)、[示例导航](../examples/README.md)
- [平台诊断](platform-diagnostics.md)、[运行与采集健康](runtime-health.md)

## 轨迹与治理排查

- [轨迹、节点和耗时](trace-reading.md)、[用量与覆盖](trace-usage.md)、[查询链接](query-links.md)
- [Dashboard 工作流与设计](dashboard-design.md)、[安全事件](security-events.md)、[离线导出包](security-export.md)
- [策略工作台](policy-workbench.md)、[策略变更比较](policy-comparison.md)、[历史事件候选回放](event-policy-replay.md)

## 工具审批与图恢复

- [策略三类决策和审批闭环](policy-approval.md)、[配置审批](configured-review.md)、[配置审批图](configured-graph.md)
- [审批准备](approvals.md)、[同步执行审批](reviewed-execution.md)、[异步审批](async-reviewed-execution.md)
- [单根图审批](langgraph-reviewed.md)、[本机持久图](durable-graph.md)、[异步持久图](async-graph.md)、[统一图调用/流](managed-graph-stream.md)

## 开发、公开材料与历史

- [架构](../ARCHITECTURE.md)、[路线图](../ROADMAP.md)、[贡献](../CONTRIBUTING.md)、[安全报告](../SECURITY.md)
- [公开材料与交付检查](github-readiness.md)、[统一源码验收](snapshot-check.md)、[第三方归属](../THIRD_PARTY_NOTICES.md)
- [全部 SPEC 分类档案](../specs/README.md)、[官方资源与原创笔记](../resources/README.md)

设计草案：[接入方向](design/integrations.md)、[数据模型](design/data-model.md)、[初始 MVP 验收目标](design/mvp.md)。草案与历史设计不覆盖当前能力表。

历史 ADR：[基础架构](adr/0001-foundation.md)、[Spec 驱动](adr/0002-spec-driven-delivery.md)、[Runtime 授权](adr/0003-runtime-authorization.md)、[审批准备](adr/0004-approval-preparation.md)、[同步恢复](adr/0005-reviewed-execution.md)、[异步恢复](adr/0006-async-reviewed-execution.md)、[单根图审批](adr/0007-langgraph-reviewed.md)、[持久图](adr/0008-durable-graph.md)、[异步图](adr/0009-async-graph.md)。

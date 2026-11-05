# Aegis 文档索引

## 项目入口

- [快速开始](quickstart.md)：独立环境安装、首个有效 Trace、计时与故障排查。
- [README](../README.md)：定位、当前状态、能力、技术路线和目录。
- [Architecture](../ARCHITECTURE.md)：组件边界、观测和控制数据流。
- [Roadmap](../ROADMAP.md)：分阶段范围、验收与下一轮实现顺序。
- [Contributing](../CONTRIBUTING.md)：工程约定与验证要求。
- [Specs](../specs/README.md)：增量行为契约、实现方案与验收记录。
- [Resources](../resources/README.md)：官方资源与研究笔记。

## 设计草案

- [Integrations](design/integrations.md)：用户接入方式、候选 API、框架验证。
- [Data Model](design/data-model.md)：Trace、Run、Span、Action 与治理事件。
- [MVP](design/mvp.md)：真实 Agent 到 Dashboard 的可复现闭环与验收。

## 架构决策

- [ADR-0001：Foundation](adr/0001-foundation.md)：单体部署、Python 优先、标准与阶段取舍。
- [ADR-0002：Spec 驱动增量](adr/0002-spec-driven-delivery.md)：先文档、再实现、再验证。

产品设计中尚未实现的内容保持目标状态；可运行能力以对应 spec 的实现与验收证据为依据。

- [ADR-0003：Runtime 授权](adr/0003-runtime-authorization.md)：身份、策略失败关闭与遥测边界。

- [审批接入](approvals.md)：独立角色、本地绑定、持久决定与执行边界。
- [ADR-0004：审批准备](adr/0004-approval-preparation.md)：先持久绑定与决定，再单次领取/恢复。

- [执行审批接入](reviewed-execution.md)：完整参数、单次同步恢复与未知结果。
- [ADR-0005](adr/0005-reviewed-execution.md)：永久消费领取、同步范围和新旧隔离。

- [异步执行审批](async-reviewed-execution.md)：async工具、取消、资源与unknown。
- [ADR-0006](adr/0006-async-reviewed-execution.md)：原生异步、可选依赖和永久消费领取。

- [LangGraph审批恢复](langgraph-reviewed.md)：纯中断节点、精确snapshot绑定、宿主单次执行和未知结果。
- [ADR-0007](adr/0007-langgraph-reviewed.md)：稳定逻辑call与图恢复边界。

- [持久图接入](durable-graph.md)：本机文件、分进程命令、版本与未知边界。
- [ADR-0008](adr/0008-durable-graph.md)：官方SQLite与保守进程恢复。

- [异步审批图](async-graph.md)：原生await、SQLite连接生命周期和取消。
- [ADR-0009](adr/0009-async-graph.md)：借入连接的边界。

- [已有Agent接入选择与步骤](existing-agent.md)：入口、模型/工具观测、Runtime和审批边界。

- [接入前检查](preflight.md)：当前解释器/关键包元数据与可选审批配置形状。

- [GitHub私有准备](github-readiness.md)：本地验证/CI/上传与公开门槛。

- [Trace模型用量汇总](trace-usage.md)：精确Token总量、维度覆盖和已接收范围。

- [安全事件中心](security-events.md)：跨Trace治理查询、组合筛选/分页、真实示例与信任边界。

- [治理事件离线排查包](security-export.md)：白名单导出、JSONL/CSV、汇总与本地完整性核验。

- [策略开发与验收工作台](policy-workbench.md)：文件校验、决策解释、批量用例、报告与接入边界。

- [策略变更影响评估](policy-comparison.md)：规则差异、权限放宽/收紧、有限用例和CI审查报告。

- [历史事件候选策略回放](event-policy-replay.md)：核验导出包、纯求值、结果保留与信任边界。

- [已有Agent统一配置接入](application-onboarding.md)：配置、工具控制、SDK生命周期、检查与平台闭环。

- [统一配置中的人工审核](configured-review.md)：v2模式、明确参数披露、独立审核与单次恢复。
- [配置驱动的持久化审批图](configured-graph.md)：v3图绑定、同步/异步SQLite、跨进程暂停/审核/单次恢复并继续。
- [统一图调用与状态流](managed-graph-stream.md)：完整模型/工具循环、四种调用、EOF/关闭/取消及SDK生命周期。
- [Dashboard工作台设计](dashboard-design.md)：统一数据界面、参考来源、响应式与验收边界。
- [Dashboard合成演示](dashboard-demo.md)：单命令准备追踪/模型/治理数据与可选待审核记录，不执行审核工具。
- [Trace节点与耗时排查](trace-reading.md)：查询、耗时排行、精确原值、节点定位与规范链接，包含计时口径和覆盖限制。
- [私有快照统一验收](snapshot-check.md)：安装后一次运行Python/专用PG与前端检查，核对新报告和工作树字节稳定性。

- [Collector连通性诊断](platform-diagnostics.md)：只读分阶段检查健康、就绪、查询凭证及指定Trace/治理页。

- [列表查询链接](query-links.md)：已应用筛选/分页、UTC边界、刷新认证和浏览器历史恢复。

- [策略驱动审批闭环](policy-approval.md)：Policy v2、配置v4、同步/异步票据与单次恢复、平台排查和完整示例。

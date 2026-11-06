# SPEC 分类与历史归档

开发顺序：需求与边界 → 方案 → 实现 → 按验收验证 → 记录实际结果。每个增量组成可独立使用的完整场景。

当前能力看 [能力边界](../docs/capabilities.md)，当前接口看 [049 OpenAPI](049-runtime-health/contracts/openapi.json)，最新公开交付看 [050](050-public-preview/tasks.md)。

001–049 已逐项审查为可公开技术档案。每个 spec / plan / tasks 和兼容快照保留当时事实，不表示旧“待实现”“未上传”今天仍成立，也不把旧计数冒称新回归。004 的真实 OpenAI、006 的真实 Provider/首次用户体验仍未验收；后续已交付的 LangGraph 流和恢复分别见对应增量。原始日志、截图和安装缓存留在忽略目录。机器目录为 [catalog.json](catalog.json)。

## 工作约定

- 新需求先更新契约和验收，不用文档掩盖失败。只有已验证项勾选完成。
- 用户文档维护当前行为；历史记录保持当时的测试范围、继承/重跑口径和限制。
- 可公开契约和无秘密摘要；真实输入输出、凭证、本机报告与临时脚本不属于公开档案。
- 外部资料保留来源和原许可证；重大模块/信任边界取舍记录 ADR。

## 观测与适配

| 编号 | 历史范围 | 记录 |
| --- | --- | --- |
| 001 | Python SDK 基础追踪 | [需求](001-python-sdk/spec.md) · [方案](001-python-sdk/plan.md) · [验收](001-python-sdk/tasks.md) |
| 002 | OTLP Collector 与 PostgreSQL 查询 | [需求](002-collector/spec.md) · [方案](002-collector/plan.md) · [验收](002-collector/tasks.md) |
| 003 | Trace Dashboard | [需求](003-dashboard/spec.md) · [方案](003-dashboard/plan.md) · [验收](003-dashboard/tasks.md) |
| 004 | OpenAI 模型客户端接入 | [需求](004-openai/spec.md) · [方案](004-openai/plan.md) · [验收](004-openai/tasks.md) |
| 005 | DeepSeek Provider 与真实调用验收 | [需求](005-deepseek/spec.md) · [方案](005-deepseek/plan.md) · [验收](005-deepseek/tasks.md) |
| 006 | LangGraph 首批显式接入 | [需求](006-langgraph/spec.md) · [方案](006-langgraph/plan.md) · [验收](006-langgraph/tasks.md) |
| 007 | LangGraph stream / astream 生命周期 | [需求](007-langgraph-stream/spec.md) · [方案](007-langgraph-stream/plan.md) · [验收](007-langgraph-stream/tasks.md) |
| 019 | Trace模型用量汇总 | [需求](019-trace-usage/spec.md) · [方案](019-trace-usage/plan.md) · [验收](019-trace-usage/tasks.md) |
| 040 | 已接收模型/工具调用耗时排查 | [需求](040-call-duration/spec.md) · [方案](040-call-duration/plan.md) · [验收](040-call-duration/tasks.md) |
| 047 | SPEC-047 执行轨迹与审批排查 | [需求](047-execution-trajectory/spec.md) · [方案](047-execution-trajectory/plan.md) · [验收](047-execution-trajectory/tasks.md) |
| 049 | SPEC-049 运行与采集健康 | [需求](049-runtime-health/spec.md) · [方案](049-runtime-health/plan.md) · [验收](049-runtime-health/tasks.md) |

## 治理、审批与图恢复

| 编号 | 历史范围 | 记录 |
| --- | --- | --- |
| 009 | 进程内工具权限控制 | [需求](009-runtime-policy/spec.md) · [方案](009-runtime-policy/plan.md) · [验收](009-runtime-policy/tasks.md) |
| 010 | 持久化审批准备与决定 | [需求](010-approval-records/spec.md) · [方案](010-approval-records/plan.md) · [验收](010-approval-records/tasks.md) |
| 011 | 可审阅参数与单次受约束恢复 | [需求](011-reviewed-execution/spec.md) · [方案](011-reviewed-execution/plan.md) · [验收](011-reviewed-execution/tasks.md) |
| 012 | 异步工具的审批恢复与取消 | [需求](012-async-reviewed-execution/spec.md) · [方案](012-async-reviewed-execution/plan.md) · [验收](012-async-reviewed-execution/tasks.md) |
| 013 | LangGraph单个审批中断的受约束恢复 | [需求](013-langgraph-reviewed/spec.md) · [方案](013-langgraph-reviewed/plan.md) · [验收](013-langgraph-reviewed/tasks.md) |
| 014 | 本机持久checkpoint与独立进程恢复 | [需求](014-durable-graph/spec.md) · [方案](014-durable-graph/plan.md) · [验收](014-durable-graph/tasks.md) |
| 015 | 单个异步审批图与本机checkpoint | [需求](015-async-graph/spec.md) · [方案](015-async-graph/plan.md) · [验收](015-async-graph/tasks.md) |
| 020 | 安全事件中心（完整纵向增量） | [需求](020-security-events/spec.md) · [方案](020-security-events/plan.md) · [验收](020-security-events/tasks.md) |
| 021 | 治理事件离线排查包 | [需求](021-security-export/spec.md) · [方案](021-security-export/plan.md) · [验收](021-security-export/tasks.md) |
| 022 | 策略开发与验收工作台 | [需求](022-policy-workbench/spec.md) · [方案](022-policy-workbench/plan.md) · [验收](022-policy-workbench/tasks.md) |
| 023 | 策略变更影响评估 | [需求](023-policy-comparison/spec.md) · [方案](023-policy-comparison/plan.md) · [验收](023-policy-comparison/tasks.md) |
| 024 | 历史治理事件的候选策略回放 | [需求](024-event-policy-replay/spec.md) · [方案](024-event-policy-replay/plan.md) · [验收](024-event-policy-replay/tasks.md) |
| 026 | 统一接入中的人工审核与单次恢复 | [需求](026-configured-review/spec.md) · [方案](026-configured-review/plan.md) · [验收](026-configured-review/tasks.md) |
| 027 | 配置驱动的持久化审批图完整接入 | [需求](027-configured-graph/spec.md) · [方案](027-configured-graph/plan.md) · [验收](027-configured-graph/tasks.md) |
| 045 | 策略驱动的人工审批闭环 | [需求](045-policy-approval/spec.md) · [方案](045-policy-approval/plan.md) · [验收](045-policy-approval/tasks.md) |

## 接入与可复现体验

| 编号 | 历史范围 | 记录 |
| --- | --- | --- |
| 008 | 首次本地接入与可重复测量 | [需求](008-onboarding/spec.md) · [方案](008-onboarding/plan.md) · [验收](008-onboarding/tasks.md) |
| 016 | 已有 Agent 接入配方 | [需求](016-existing-agent/spec.md) · [方案](016-existing-agent/plan.md) · [验收](016-existing-agent/tasks.md) |
| 017 | 接入前的元数据检查 | [需求](017-preflight/spec.md) · [方案](017-preflight/plan.md) · [验收](017-preflight/tasks.md) |
| 025 | 已有Agent统一接入流程 | [需求](025-application-onboarding/spec.md) · [方案](025-application-onboarding/plan.md) · [验收](025-application-onboarding/tasks.md) |
| 028 | 统一接入中的图流式生命周期与观测治理闭环 | [需求](028-managed-graph-stream/spec.md) · [方案](028-managed-graph-stream/plan.md) · [验收](028-managed-graph-stream/tasks.md) |
| 035 | 可复现Dashboard演示与完整回归 | [需求](035-dashboard-demo/spec.md) · [方案](035-dashboard-demo/plan.md) · [验收](035-dashboard-demo/tasks.md) |
| 042 | 已有Agent的平台连通性诊断 | [需求](042-platform-diagnostics/spec.md) · [方案](042-platform-diagnostics/plan.md) · [验收](042-platform-diagnostics/tasks.md) |
| 048 | SPEC-048 外部 Agent 首次接入验收 | [需求](048-external-agent/spec.md) · [方案](048-external-agent/plan.md) · [验收](048-external-agent/tasks.md) |

## Dashboard 工作流与质量

| 编号 | 历史范围 | 记录 |
| --- | --- | --- |
| 029 | 统一数据工作台视觉与页面质量 | [需求](029-dashboard-design/spec.md) · [方案](029-dashboard-design/plan.md) · [验收](029-dashboard-design/tasks.md) |
| 030 | 审核队列、渐进筛选与详情阅读 | [需求](030-dashboard-workflows/spec.md) · [方案](030-dashboard-workflows/plan.md) · [验收](030-dashboard-workflows/tasks.md) |
| 031 | Trace 阅读工作台与键盘效率 | [需求](031-trace-reading/spec.md) · [方案](031-trace-reading/plan.md) · [验收](031-trace-reading/tasks.md) |
| 032 | 可重复前端验收入口与生产预览 | [需求](032-dashboard-quality/spec.md) · [方案](032-dashboard-quality/plan.md) · [验收](032-dashboard-quality/tasks.md) |
| 033 | 真实加载、刷新与失败恢复状态 | [需求](033-dashboard-states/spec.md) · [方案](033-dashboard-states/plan.md) · [验收](033-dashboard-states/tasks.md) |
| 034 | 阅读对比度、触控目标和焦点质量 | [需求](034-dashboard-accessibility/spec.md) · [方案](034-dashboard-accessibility/plan.md) · [验收](034-dashboard-accessibility/tasks.md) |
| 036 | 安全事件查询到本页导出 | [需求](036-security-page-export/spec.md) · [方案](036-security-page-export/plan.md) · [验收](036-security-page-export/tasks.md) |
| 037 | 工作台信息层级与渐进披露 | [需求](037-dashboard-hierarchy/spec.md) · [方案](037-dashboard-hierarchy/plan.md) · [验收](037-dashboard-hierarchy/tasks.md) |
| 038 | 审批收件箱排序与绑定阅读 | [需求](038-review-reading/spec.md) · [方案](038-review-reading/plan.md) · [验收](038-review-reading/tasks.md) |
| 039 | Trace节点深链与可复制定位 | [需求](039-trace-node-links/spec.md) · [方案](039-trace-node-links/plan.md) · [验收](039-trace-node-links/tasks.md) |
| 043 | 可复现的列表查询地址 | [需求](043-query-links/spec.md) · [方案](043-query-links/plan.md) · [验收](043-query-links/tasks.md) |
| 044 | 关联Trace与来源查询返回 | [需求](044-trace-return/spec.md) · [方案](044-trace-return/plan.md) · [验收](044-trace-return/tasks.md) |

## 仓库与交付

| 编号 | 历史范围 | 记录 |
| --- | --- | --- |
| 018 | GitHub私有仓库准备 | [需求](018-private-repository/spec.md) · [方案](018-private-repository/plan.md) · [验收](018-private-repository/tasks.md) |
| 041 | 私有开发快照统一验收 | [需求](041-snapshot-check/spec.md) · [方案](041-snapshot-check/plan.md) · [验收](041-snapshot-check/tasks.md) |
| 046 | 首次私有 GitHub 交付 | [需求](046-private-github/spec.md) · [方案](046-private-github/plan.md) · [验收](046-private-github/tasks.md) |
| 050 | 公开预览整理与交付 | [需求](050-public-preview/spec.md) · [方案](050-public-preview/plan.md) · [验收](050-public-preview/tasks.md) |

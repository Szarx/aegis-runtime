# ADR-0001：Foundation 与首版边界

- 状态：本次初始化采用；细节接口仍待冻结。
- 日期：2026-10-12。
- 范围：仓库结构、技术方向和交付顺序。

## 背景

已有讨论确定 Aegis 的定位是 AI Agent Runtime Governance，核心能力包括观测、工具控制、策略、风险、审批、审计与回放。已有 Agent 接入是否便捷是首要验证问题；用户要求本次先建立文档和工程骨架。

## 决定

1. 使用 Monorepo，保留 `sdk/`、`runtime/`、`collector/`、`policy-engine/`、`dashboard/`、`examples/`、`docs/` 等边界。
2. Python 优先；FastAPI + PostgreSQL 承载首版服务，Vue 3 + TypeScript + ECharts 承载展示。
3. 首版服务采用模块化单体；Runtime 的工具拦截位于 Agent 进程内，策略模块不要求独立服务。
4. Phase 1 完成观测闭环，Phase 2 加入工具策略和审批，Phase 3 再建立风险模块。
5. 接入先原生 Python、OpenAI SDK，再用 LangGraph 验证首个成熟框架；更多框架逐步扩展。
6. 提供显式 SDK、Wrapper、Middleware / Adapter 和后续自动接入，保持核心框架无关。
7. 使用 OTel 上下文，对齐 GenAI 规范；具体版本和 OTLP 支持范围在实现前冻结。
8. Redis 与 ClickHouse 按协调需求和数据规模引入，首个本地闭环仅需 PostgreSQL。
9. 内容采集默认关闭，回放首先采用历史记录展示，不重跑真实工具。
10. 本次只创建文档与目录占位，不增加无法启动的伪服务或空测试，不提前声明规范兼容。

## 影响

模块目录为未来实现提供清晰位置；SDK、Runtime 与 Collector 的职责不再混用。成熟框架验证尽早进入首版路线，但不以“支持所有 Agent”为承诺。部署和扩展保持渐进，文档明确当前仍没有可运行平台。

## 尚待确认

Python 分发名称与命名空间、最低运行时版本、依赖锁定、具体许可证、最小 SDK API、传输与查询契约、身份与策略 DSL、审批持久化和生产部署要求。待确认事项不阻止本次文档与骨架交付。

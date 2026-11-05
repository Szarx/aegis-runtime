# Observability MVP Validation

状态：完整平台验收计划。原生 SDK 与本地示例已通过 [SPEC-001](../../specs/001-python-sdk/tasks.md)；Collector、PostgreSQL 与查询已通过 [SPEC-002](../../specs/002-collector/tasks.md)；Dashboard 原生 Agent 可视化见 [SPEC-003](../../specs/003-dashboard/tasks.md)；OpenAI 官方 SDK 合成 HTTP/SSE 已按 [SPEC-004](../../specs/004-openai/tasks.md) 完成离线闭环；OpenAI Provider 与框架内真实模型尚未验收，LangGraph 首批离线见 SPEC-006，DeepSeek 真实 Chat 验收见 SPEC-005。原生闭环不表示完整 Phase 1B 已完成，框架内真实模型与更广图能力仍需实际验证。

## 1. 首个闭环

```text
Native Python Agent / OpenAI SDK / LangGraph
                    ↓
        Aegis SDK / Wrapper / Adapter
                    ↓
             Collector / Server
                    ↓
                PostgreSQL
                    ↓
        Dashboard Trace Tree + Timeline
```

已用原生 Python 与 OpenAI 离线 transport 验证采集链路，真实 OpenAI 调用按用户决定另行验收；LangGraph 已按 SPEC-006/007 验证真实框架调用和状态流，继续按 spec 增量扩展。模拟调用能验证数据传输，但不代表通过 Provider 或框架兼容性验证。

## 2. 示例场景

使用订单查询 Agent：接受合成订单编号、调用 `lookup_order`、返回合成订单状态。原生 Python 示例可以只用本地数据；OpenAI / LangGraph 示例先使用合成模型响应与工具选择，真实模型单独验收，不访问真实业务数据库。

预期 Trace：

```text
customer-agent (Agent Span)
├── model-call (LLM Span; OpenAI / LangGraph 示例)
├── lookup_order (Tool Span; orders.read 元数据)
└── final-result (可选的显式应用步骤)
```

实际模型可能多次调用或并行选择工具，按真实父子关系记录，不为匹配固定演示图篡改执行树。Phase 1 的 `orders.read` 仅是元数据，不代表策略已经允许。

## 3. 验收矩阵

| 场景 | 验收结果 |
| --- | --- |
| 成功 Agent Run | 可按 Agent / 时间找到执行；Agent 与 Tool、可用的 LLM Span 正确关联 |
| 工具抛出异常 | 业务仍收到原异常；工具与 Agent 错误在 Trace 中可定位 |
| Collector 不可达 | 业务结果保持一致；导出超时有界并显示失败/丢弃诊断 |
| 重传同一 Span | 不增加重复 Span；Token 与成本不重复累计 |
| 子 Span 先到 / 迟到 | 可恢复父子关系，汇总与树不因顺序永久出错 |
| 并发 / 异步调用 | 不同 Run 不串联上下文，嵌套调用继承正确父 Span |
| 内容采集关闭 | Prompt、Completion、参数和输出原文不出现在上报与存储中 |
| 内容显式开启 | 脱敏、截断和上限按约定生效，凭证仍不进入遥测 |
| 用量未知 | UI 明确显示未知或部分数据，不显示为免费或零用量 |
| Wrapper 返回 / 流式行为 | 与接入前保持一致，完成/错误/取消时生命周期正确结束 |
| LangGraph 实际运行 | 在真实框架中关联 Agent / LLM / Tool，并对比结果和副作用 |
| 本地部署 | 按已实现的 Compose 文档可启动、运行示例、在 Dashboard 查看 Trace |

## 4. 需要保存的验证材料

- 使用的运行时、依赖和框架版本。
- Agent 接入前后差异与修改行数。
- 平台准备耗时、Agent 接入耗时、首次正确 Trace 的耗时。
- 一次成功和一次失败的 Trace 标识与展示截图。
- 外部模型真实运行记录及不需要凭证的本地复现路径。
- 返回值、异常、工具执行次数及遥测失败诊断的验证结果。

基础接入约 5 分钟、完整本地体验约 10 分钟是待验证目标。平台实现前不宣称这些目标已经达成。

## 5. Phase 1 范围

交付 Agent / LLM / Tool 观测、存储、查询和展示。Memory、自动攻击检测、AI 风险模型、多 Agent 协同平台、真实工具重执行与完整审批流程继续留在后续阶段。

进入 Phase 2 的前提是观测闭环和成熟 Agent 接入已经验证；随后用可控副作用的测试工具验证权限拦截与审批行为。

## 6. SPEC-004 本轮证据

OpenAI Responses / Chat Completions × 同步/异步 × 流式/非流式 8 种组合，经官方 SDK、真实 HTTP Collector、PostgreSQL 与 Dashboard 代理查询生成 8 Trace / 24 Span。浏览器核对 Agent 下的 LLM / Tool、输入 7 与输出 3 Token、模型名称和结束原因。用量来自合成响应，不能视为真实模型用量或 Provider 兼容性证据。

SDK 32、Collector 协议 10、真实 PostgreSQL 10、前端 20 个测试通过，另有严格类型检查、Windows / Docker 构建与 SDK wheel 安装验证。明细见 SPEC-004 tasks。上述为 SPEC-004 时点证据；后续 DeepSeek 真实调用见 005，LangGraph 真实框架见 006，新用户接入耗时仍未验收。

## 7. DeepSeek 离线扩展与真实调用状态

SPEC-005 完成 4 个 Chat 调用模式和一个两轮合成工具循环，经真实 HTTP / PostgreSQL / Dashboard 形成 5 Trace / 16 Span，核对 Provider 与 7/3 合成 Token。当前 61 Python + 20 前端方法通过。用户明确批准后，6 个真实 deepseek-flash 请求全部成功，额外形成 5 Trace / 16 Span；四种基础请求各为 input=11/output=1，工具循环两个 LLM 分别 299/35 与 94/16，数据库与浏览器核对一致。完整 Phase 1B 仍需成熟 LangGraph 与接入体验验证。

## 8. 真实 LangGraph 框架证据

SPEC-006 实际安装并运行 StateGraph / ToolNode，模型为合成 transport。本轮 invoke / ainvoke × 成功/框架处理工具错误共四组合，baseline / traced 输出和 2 模型 / 1 工具次数一致；经真实 HTTP / PostgreSQL / Dashboard 保存 4 Trace / 16 Span。模型用量每节点 7/3 为合成值。真实框架通过不等于框架内真实 Provider 已验收。

当前 71 个 Python 方法通过（47 SDK、12 协议、12 数据库）。未变前端沿用 SPEC-005 的 20 方法与生产构建；本轮镜像复用前端缓存。完整 Phase 1B 仍需图流式等目标能力与新用户接入耗时测量，不能仅凭缓存示例约 0.2 秒执行声称 5 分钟接入达标。

## 9. LangGraph 状态流证据

SPEC-007 已验证六组 stream / astream × 完整消费/提前关闭/框架处理工具错误的 baseline / traced 对照，输出及调用次数一致；额外真实框架传播异常与取消，共 8 Trace / 24 Span 经 HTTP / PostgreSQL / Dashboard。graph_outcome 分布 completed=4、closed=2、error=1、cancelled=1；status 为 ERROR=4 / UNSET=4。图完成而子工具 ERROR、无异常但提前关闭分别保留，不混为成功。

57 SDK + 15 协议 + 13 真实数据库 = 85 Python 方法，前端 23，总计 108 方法通过。Windows 类型/构建、Docker 镜像、wheel 隔离安装、OpenAPI 与浏览器通过，详见 [007](../../specs/007-langgraph-stream/tasks.md)。本轮没有新增真实模型请求；事件投影、checkpoint/interrupt 恢复和首次接入耗时仍待独立验收。

## 10. 全新环境安装与首次有效 Trace

SPEC-008 提供独立环境快速开始，原生和 LangGraph 从本机官方 wheel 缓存完成全新安装，包含包构建/导入/示例/flush/校验，分别约 33.6 秒和 177.3 秒。8 项新增针对性测试通过，空缓存停止且不执行 Agent；前序完整回归沿用 SPEC-007，没有冒称本轮重跑。

上述 SDK 测量只覆盖机器流程；Python 已安装、源码与缓存已存在，不包含在线下载、人工修改或页面展示。首次本地测量时 Docker Engine 不可用；用户恢复后已完成独立平台续验，26.2 秒三服务健康、44.3 秒首次查询、107.9 秒页面确认上界。人工 5 分钟与冷启动完整 10 分钟目标仍保持未验收。步骤见 [快速开始](../quickstart.md)，明细见 [008](../../specs/008-onboarding/tasks.md)。

## 11. 最小权限控制验收

SPEC-009 对真实本地工具验证每组 allow=1 / explicit deny=0 / default deny=0 / allowed error=1，sync / async 形成 8 Trace / 16 Span；真实 ToolNode 允许/拒绝路径通过。缺身份/权限/策略、求值故障、SDK 停用和追踪故障不能绕过或重复受保护工具。

111 Python + 26 前端方法和真实 HTTP/数据库/页面核对已通过。治理决策与工具实际 outcome 分开展示，动作 ID 独立、父子关系保持；参数/异常正文不保存。审批、外部认证、直接函数调用隔离和持久审计仍未验收。详见 [009](../../specs/009-runtime-policy/tasks.md)。

## SPEC-010 验收边界

审批准备、绑定与持久决定、独立角色和 Dashboard 为本轮增量；真实数据库验证幂等/冲突/过期/并发，浏览器记录合成批准与拒绝并确认独立 Trace 访问。所有审批路径均不执行工具，已有默认拒绝保持。完整暂停/恢复和单次执行未验收，证据见 [010](../../specs/010-approval-records/tasks.md)。

## SPEC-011：同步执行审批验收

真实HTTP与浏览器核对完整参数/64位整数后批准或拒绝，独立CLI进程恢复：批准一次、拒绝零次、重复恢复零增量；失败可已有部分副作用；领取响应丢失零执行并保持claimed未知。原Runtime/SDK/Collector兼容回归，异步/图恢复不在本轮。证据见 [011](../../specs/011-reviewed-execution/tasks.md)。

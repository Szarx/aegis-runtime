# Example Agents

状态：原生 Python 示例已可运行；OpenAI 已完成官方 SDK 合成 HTTP/SSE 离线验证；DeepSeek 真实调用已按 SPEC-005 验收，LangGraph 真实框架 / 合成模型已按 SPEC-006 验收；框架内真实模型未验收。

1. [Native Python](native-python/README.md)：无需外部凭证的第一个闭环。
2. [OpenAI](openai/README.md)：默认离线的模型客户端 Wrapper 示例，另提供可选 live 模式。
3. [DeepSeek](deepseek/README.md)：默认离线 Chat 与合成工具循环，限定范围的 live 已通过 6 个真实请求验证。
4. [LangGraph](langgraph/README.md)：真实 StateGraph / ToolNode 的显式接入和合成模型前后行为对照。

示例使用合成数据与公共 SDK API，说明接入前后差异和依赖版本，复现成功与失败路径。观测示例先完成，受保护工具和人工审批示例在 Phase 2 增加。

统一验收见 [MVP 方案](../docs/design/mvp.md)。

- [异步执行审批](async-reviewed-execution/README.md)：无LLM的成功、部分失败、取消及重复恢复拒绝。

- [LangGraph审批中断](langgraph-reviewed/README.md)：真实图暂停、人工批准后显式恢复与同进程宿主重建。

- [持久图Agent](durable-graph/README.md)：start/status/resume独立进程，本机SQLite与原动作恢复。

- [异步持久图Agent](async-durable-graph/README.md)：原生异步start/status/resume独立进程。

- [已有Agent接入配方](existing_agent/README.md)：原应用/适配层分离，八组行为与Trace验证。

- [安全事件Agent](security-events/README.md)：真实Runtime与OTLP生成25次治理尝试，无需LLM。

- [策略验收后接入Runtime](policy-workbench/README.md)：7个声明式用例、同步/异步实际执行次数对照。

- [策略变更审查](policy-comparison/README.md)：基准/候选与8个用例，放宽、收紧和CI门槛。

- [真实事件候选回放](event-policy-replay/README.md)：使用安全事件示例的导出包，保留业务结果与关联ID。

- [统一配置Agent](configured-agent/README.md)：原生/真实LangGraph、同步/异步、允许/拒绝与生命周期装配。

- [配置审核Agent](configured-review/README.md)：v2声明敏感工具，分进程prepare/人工决定/resume。
- [配置审批图Agent](configured-graph/README.md)：v3固定图版本，sync/async持久化start/status/resume完整流程。
- [统一图调用Agent](managed-graph/README.md)：官方SDK合成模型与受控工具，四调用模式、允许/拒绝和完整/提前关闭。

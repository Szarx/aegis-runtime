# SPEC-006：LangGraph 首批显式接入

日期：2026-10-17。先维护契约、依赖与方案，再实现；任务见 [tasks](tasks.md)。本轮不调用真实模型，005 已批准的 6 请求额度已用完。

## 场景与范围

已有 StateGraph Agent 保留节点、边、状态、模型和工具调用方式。增加 `from aegis.langgraph import observe_graph` 与 `graph = observe_graph(graph, name="order-agent")`；模型用现有 wrap_openai / DeepSeek 客户端，工具用 @aegis.tool。真实 LangGraph 运行合成模型 transport，验证两次 LLM 与一次 Tool 的 Agent 上下文。

首批锁定 LangGraph 1.2.15（最终依赖和实测环境写回 tasks），仅显式 invoke / ainvoke 与 with_config 后的同类调用。stream / astream / event-stream、batch、checkpoint/interrupt/resume、分布式执行、Functional API、自动 callback 全节点发现与 LangChain ChatModel 原生 Adapter 不在验收范围；范围外方法委托原对象但不自动添加 Agent Span。

## 公共契约

1. `observe_graph(compiled_graph, *, name=None)` 返回轻量代理，不修改原图。首次未给 name 时使用 langgraph-agent，重复包装未给 name 时保留原名称。只接收本轮实测的 CompiledStateGraph 或其公开 with_config 绑定；首次包装检查配置，重复包装同名幂等，冲突名称拒绝。代理不保持原图类型身份；原图仍可直接调用。
2. invoke / ainvoke 原样转发位置与关键字参数、RunnableConfig、callbacks、tags、metadata、context 和递归限制。原方法每次只调用一次；返回对象和异常对象保持身份。with_config 返回继续追踪且独立的代理，原图配置不变。其他属性/方法委托且明确不承诺追踪；不新增业务重试或替换原回调。
3. 复用 v1 INTERNAL invoke_agent / @tool 与 v2 CLIENT 模型 Span。图执行、节点线程/异步任务、ToolNode 中的显式工具和模型关联到同一 Agent；图内 LangChain 回调不再生成第二份模型/工具 Span。不强制导出中间图节点，也不把这些节点伪称成 LLM 或工具。
4. 工具需在构造成 LangChain tool 之前用 aegis.tool 包装，保留签名和 docstring；没有显式标记的工具不自动追踪。ToolNode 默认处理的业务错误仍按框架行为返回；只有图实际传播的异常才标记 Agent ERROR。取消保持原 CancelledError，观测故障不改变图业务。
5. 核心 import aegis 不引入 LangGraph；可选 langgraph 安装组单独声明。默认示例只有本地合成 JSON transport，无 DeepSeek Key 或外部模型调用，不启用 LangSmith 上报；适配器本身不改宿主遥测配置。
6. 模型输入/输出、图 state、messages、config metadata、工具参数/结果、异常正文与凭证不进入 Aegis 遥测。状态/回调仍原样交给原图；仅既有白名单元数据出现在 JSONL/OTLP/数据库。Collector、SQL 与 Dashboard 契约不新增。
7. 提供同一 Graph 工厂的接入前 / 后路径，比较业务输出、模型次数、工具次数、成功/传播失败与框架处理失败。记录接入代码差异与本机从构造到首个 flush 的实测时间，不将缓存环境测量称为新用户 5 分钟接入证明。

## 验收条件

| AC | 验证 |
| --- | --- |
| 601 | 真正安装并运行固定 LangGraph / ToolNode，完整合成工具循环；不是手写模拟框架 |
| 602 | invoke / ainvoke 参数、返回/异常身份、回调、with_config 和重复包装保持行为；基础未初始化原样执行 |
| 603 | 两 LLM + 一 Tool + 一 Agent，无重复 Span；同步/异步、并发与嵌套上游上下文正确 |
| 604 | 工具成功/框架捕获失败/传播失败、取消、追踪故障、状态和配置隐私通过 |
| 605 | 示例接入前后结果、调用次数一致，记录修改行数/本机耗时，实际 OTLP→Collector→PostgreSQL→Dashboard 可见 |
| 606 | SDK / Collector / 数据库回归、可选依赖安装与 wheel 分发、锁文件与资源凭据、产品文档通过 |

本轮真实框架验收只使用合成模型 transport；不扩展为真实 Provider 下的 LangGraph 验收、任意框架自动接入或生产恢复能力。

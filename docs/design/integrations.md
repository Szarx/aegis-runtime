# Agent Integration Design

状态：接入设计。原生 Python API 已按 [SPEC-001](../../specs/001-python-sdk/spec.md) 实现；OpenAI Wrapper 已按 [SPEC-004](../../specs/004-openai/spec.md) 完成离线验收，LangGraph 显式调用边界和状态流已按 SPEC-006/007 离线验证，更多框架与自动接入仍是候选方案。用户体验目标是保留已有 Agent 的调用方式，用少量修改接入观测和后续治理。

## 1. 接入方式

| 模式 | 适用场景 | 首版能力与限制 |
| --- | --- | --- |
| SDK / Decorator | 原生 Python 或自定义 Agent | 显式标记 Agent、Tool 和步骤；入口装饰器不能自动发现内部调用 |
| SDK Wrapper | 使用支持的模型客户端 | 捕获 LLM 调用；需保持返回、异常、异步和流式行为 |
| Middleware / Adapter | 使用框架生命周期钩子 | 关联框架 Run、LLM 与工具；按具体框架验证 |
| Auto Instrumentation | 已有成熟适配的快捷安装 | 有明确支持范围、幂等启用和关闭方式；不保证捕获所有框架 |

优先使用框架公开钩子。全局补丁与自动发现仅在明确边界后评估。自动记录调用不代表自动拦截工具副作用；治理能力需要在实际执行入口接入 Runtime。

## 2. 原生 Python 公共 API

当前实现形态如下，已有 Agent / Store 由应用提供；完整可运行示例见 [Native Python](../../examples/native-python/README.md)：

```python
import aegis
from aegis import observe, tool

aegis.init(
    service_name="order-service",
    output_path="artifacts/traces.jsonl",
)

@tool(permission="orders.read")
def lookup_order(order_id: str):
    return existing_store.lookup(order_id)

@observe(name="customer-agent")
def customer_agent(query: str):
    return existing_agent.invoke(query)

customer_agent("查询订单")
aegis.flush()
```

`init`、装饰器、flush 与 shutdown 的当前语义以 SPEC-001 为准。网络 `endpoint` 已按 [SPEC-002](../../specs/002-collector/spec.md) 实现，可将本地 `output_path` 换为完整 `/v1/traces` URL；安装可选 OTLP 依赖，认证头通过显式 headers 传入。运行说明见 [SDK](../../sdk/python/README.md)。此前讨论的 `AgentTracer` / `trace.agent` 是备选，不提供多套公共入口。

Phase 1 中 `permission` 是可选工具元数据。Phase 2 才定义它与身份、策略、执行拦截的绑定方式。没有接入 Tool 装饰器或框架钩子的工具不自动获得治理保护。

## 3. OpenAI Wrapper 与后续框架入口

保留此前的 OpenAI Wrapper 方向：

```python
from aegis.openai import AegisOpenAI

client = AegisOpenAI()
# 使用现有的 responses.create / chat.completions.create 调用方式。
```

公共入口 `aegis.openai` 已实现于 `integrations/openai/`，也提供 `AegisAsyncOpenAI` 和 `wrap_openai`，可选安装组 `openai`。OpenAI 3.33.0 / HTTPX2 2.13.1 的两类 create 在同步/异步、流式/非流式下离线通过；仅验证此固定基线，不扩展兼容性声明。代理不保留客户端/Stream 类型身份；raw、parse、Responses stream 辅助器等范围外入口委托且不追踪。模型客户端 SDK 的 Wrapper 与 OpenAI Agents SDK 的 Agent 生命周期适配独立设计，不把两者混为同一种支持。

LangGraph 首个实现采用公开 invoke / ainvoke 边界与显式模型/工具接入，复用核心 Span / Exporter，不让核心 import 依赖 LangGraph；自动 callback / Middleware Adapter 暂未实现。范围与重复记录策略已在 SPEC-006 冻结。

```python
import aegis

# 后续自动接入入口的候选形态，尚未实现。
aegis.instrument()
```

此入口应报告已启用的适配器和支持版本。不存在“只增加这一行就能观测和保护任意 Agent”的保证。

## 4. 首批支持顺序

| 顺序 | 对象 | 首轮验证 |
| --- | --- | --- |
| 1 | 原生 Python | 同步、基本异步、嵌套 Agent / Tool、异常和上下文隔离 |
| 2 | OpenAI 模型客户端 SDK | 支持矩阵内的模型请求、Token、错误、同步/异步/流式 |
| 3 | LangGraph | 已有成熟框架 Agent、模型与工具上下文、结果与副作用一致 |
| 后续 | OpenAI Agents SDK | Agent 生命周期与工具钩子，单独建立能力矩阵 |
| 后续 | LangChain / CrewAI / AutoGen | 核心契约复用、独立版本与测试 |
| 后续 | MCP / Java / Spring AI / Semantic Kernel | 网关及其他语言运行时边界 |

每个集成在 README 中列出实际测试版本、能力、遗漏场景和接入步骤。未验证的版本标记未知，不声明自动兼容。依赖使用可选安装组，名称在分发元数据创建时确定。

## 5. 行为一致性

- 观测模式保持原始返回对象、业务异常和工具执行次数。
- 并发请求与异步任务之间不串联上下文；嵌套调用接续父 Span。
- 框架已有追踪与 Aegis 同时启用时避免重复 Span，不替换宿主的全局追踪配置。
- 流式请求在完成、异常、关闭或取消时结束 Span；没有明确协议时不猜测终止。
- Aegis 不新增业务重试，原模型 SDK 自身重试保持；遥测重试不重跑模型或工具；用户显式关闭观测后不残留全局补丁。
- 用量按 Provider 实际返回值记录；内容采集遵守默认关闭和脱敏策略。

## 6. 接入体验如何验收

先保存 Agent 的原始版本，再按组件说明接入公共 API。记录准备环境、启动平台、修改 Agent 和首次看到 Trace 各自耗时；以 Agent 修改到首个正确 Trace 的过程衡量基础接入目标。

验收材料包含：前后代码差异、修改行数、接入耗时、实际依赖版本、Trace 关联结果，以及调用结果、异常与工具执行次数的对比。LangGraph 必须使用真实框架运行；仅手写模拟框架回调不算通过成熟 Agent 接入验证。

## 7. DeepSeek 的 OpenAI 兼容入口

SPEC-005 已实现 AegisDeepSeek / AegisAsyncDeepSeek 或显式 `wrap_openai(client, provider="deepseek")`。首批矩阵是 Chat create × 同步/异步 × 非流式/流式；Provider 不由模型名或 URL 推断，copy 保留分类，重复包装幂等，冲突拒绝。DeepSeek Responses 委托且不追踪，后续独立验收，不与 OpenAI 的已验证矩阵混同。

沿用可选 OpenAI SDK，不引入新框架依赖。只在官方兼容传输与遥测契约复用；thinking、Search/Fetch、Anthropic 与框架内真实模型尚未验收。用户批准后已验证 6 个真实 DeepSeek 请求；LangGraph 首批离线见 006；thinking 专属行为、框架内真实模型与其他 API 仍未验收。离线工具循环与真实模型证据分开记录。见 [SPEC-005](../../specs/005-deepseek/spec.md)。

## 8. LangGraph 首批公共入口

`from aegis.langgraph import observe_graph` 后包装已编译 StateGraph；invoke / ainvoke、with_config 已验证。模型与工具分别由现有 Wrapper、Decorator 记录，避免 callback 生成重复 Span。示例实际使用 ToolNode 与条件边运行两轮模型，接入前后结果和执行次数一致，并发/取消/回调/context 隔离通过。

三个观测接入点（模型、工具、图）及 3 个 import 的最小示例差异见 [契约](../../specs/006-langgraph/contracts/integration.md)；安装、初始化和清理另计。仅为当前 StateGraph 与合成模型的验证，不代表任意 Agent 只需六行或首次接入耗时达标。状态流按 [007](../../specs/007-langgraph-stream/spec.md) 扩展，事件投影与恢复仍未验收。

## 9. LangGraph 状态流支持矩阵

| 入口 / 能力 | 当前边界 |
| --- | --- |
| invoke / ainvoke / with_config | SPEC-006 已验证，保留 v1 Agent |
| stream / astream | SPEC-007 已验证，专用 graph v1 生命周期 |
| updates / values / 组合，v1/v2 格式，custom | 真实 StateGraph 运行，不检查或复制输出 |
| messages | 参数原样转发，未宣称原生 ChatModel 自动追踪 |
| stream_events / astream_events、batch、恢复 | 尚未验收，后续独立契约 |

调用 stream 时捕获父上下文，首次取值创建图 Agent，仅推进/关闭时 attach；消费者在两项之间的操作恢复原上下文。完整 EOF、提前 close、异常和取消分别结束一次；普通消费者错误不会误归因图。with / async with 或显式关闭是提前停止的调用方责任；不依赖 GC、不新增业务重试或回滚。工具与模型仍需明确接入；没有自动节点/内容采集。见 [流契约](../../specs/007-langgraph-stream/contracts/stream.md)。

## 10. 受保护工具接入

需要实际阻止工具时，安装可选 aegis_runtime / aegis_policy，宿主构造 Runtime(policy=validated_policy, subject="order-agent")，将原 aegis.tool 替换为 runtime.tool(permission=...)。Agent observe、模型 Wrapper 与框架图保持；在 StructuredTool 建立 schema 前包装。真实 ToolNode 已验证 allow 一次/deny 零次，不自动寻找或控制未包装工具。

不要从模型输出、工具参数或 agent_name 生成可信身份；未绑定 Runtime subject 默认拒绝。此版本只支持普通 sync/async 工具，generator 暂不支持；不新增业务重试。已有 SDK-only 标签行为保持。契约见 [009](../../specs/009-runtime-policy/spec.md)。

## SPEC-010：显式审批准备

可选 ApprovalClient.prepare 不包装业务函数，宿主显式传入可信身份、工具、权限、策略与参数；只发送元数据/摘要。批准记录不覆盖 Runtime allow/deny，没有暂停/恢复接入或自动框架改写。最小例子与配置见 [审批接入](../approvals.md)。

## SPEC-011：同步工具显式恢复

ReviewedTool独立于既有Runtime.tool，不改已有Agent框架。宿主显式披露具名JSON参数、注册固定工具版本，prepare后待人工核对，再显式resume。必须同时满足本地allow、身份/参数/策略/版本绑定和唯一领取。无自动轮询/业务重试，未知不释放；原始函数与宿主仍可信。仅同步入口，异步与LangGraph interrupt/checkpoint恢复未验收。见 [接入](../reviewed-execution.md)。

## SPEC-012：异步工具显式恢复

独立AsyncReviewedTool和可选AsyncReviewedClient复用011绑定/审阅/领取协议；原生await保留宿主任务上下文，取消不重领、不做后台补偿。见 [接入](../async-reviewed-execution.md)。图checkpoint/interrupt恢复仍未验收。

## SPEC-013：单个LangGraph中断

ReviewedGraphTool公开纯node与宿主prepare/resume，精确绑定snapshot/interrupt并使用稳定call action；节点重跑不执行工具，完成收据才继续图。仅同步根中断，同进程宿主重建已验收；跨进程/异步图另验。见 [接入](../langgraph-reviewed.md)。

## SPEC-014：本机独立进程

可选官方SQLite工厂与分命令宿主重新构造原gate/图，沿用同一snapshot/ticket/action。状态查询不执行或申请审批；新建/重开及版本边界显式，未知不自动重领。范围是本机单个同步宿主。见 [持久图接入](../durable-graph.md)。

## SPEC-015：原生异步图

显式AsyncReviewedGraphTool只await原工具与图；配置官方异步SQLite连接，宿主拥有连接/关闭，沿用014格式。单根interrupt、本机单宿主、未知不重试。见 [接入](../async-graph.md)。

## SPEC-016：独立原应用与接入层

配方将原LangGraph应用与Aegis适配层分开，先包装客户端/工具，再编译图，最后包装入口。已有编译图的入口观测不能替代内部工具控制；机械宿主导入差异不代表总迁移工作。见 [步骤](../existing-agent.md)。

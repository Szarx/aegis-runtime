# Aegis Python SDK

当前公开预览包含原生/模型/图追踪和可选心跳。完整范围以[当前能力](../../docs/capabilities.md)为准；下列按 SPEC 编号保留的计数和阶段说明是历史记录。授权为 [Apache-2.0](LICENSE)。
状态：SPEC-001 基础追踪与 SPEC-002 网络导出已实现并通过验收。并按 SPEC-004 实现 OpenAI 离线追踪。提供原生 Python 与模型调用追踪，本地开发分发名 `aegis-runtime-sdk`，导入名 `aegis`；未公开发布。

## 已实现

- `init(service_name, output_path=...)`：初始化私有 OTel Provider 和本地导出；不替换宿主配置。
- `init(service_name, endpoint=..., export_timeout_millis=3000, headers=...)`：官方 OTLP/HTTP Protobuf 导出；endpoint 为完整 `/v1/traces` URL。
- `@observe` / `@observe(name=...)`：同步或普通异步 Agent 入口。
- `@tool` / `@tool(permission=...)`：工具调用与权限元数据，尚无策略拦截。
- `flush(timeout_millis=5000)` / `shutdown(timeout_millis=5000)`：有界等待并返回结果。
- `sdk.diagnostics()`：接收、导出、失败、丢弃、待处理和观测故障计数。

保留父子/上游上下文、函数签名、返回对象和异常对象。参数、返回内容、异常消息与堆栈不采集。普通生成器和异步生成器装饰器暂不支持（模型 Stream 与 LangGraph 状态流通过专用代理支持）；没有初始化或已关闭时按原逻辑执行。

## 安装与验证

首次体验可直接在仓库根目录执行 `python scripts/quickstart.py`，它创建独立环境并安装核心 SDK，自动校验本地 Trace。LangGraph 可用 `--profile langgraph`；无需先安装完整开发环境。默认在线安装、缓存方式和实际耗时边界见 [快速开始](../../docs/quickstart.md)。下面是开发者全套环境与测试步骤。

仓库根目录创建并激活 Python 3.11+ 独立环境后：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python
python -m unittest discover -s sdk/python/tests -v
python examples/native-python/agent.py
```

本次验证为 Python 3.12.14、OpenTelemetry 1.45.1，32 个测试方法通过（包含 13 个 OpenAI 测试方法）。完整 API、限制与证据见 [SPEC-001](../../specs/001-python-sdk/spec.md) 和 [验收记录](../../specs/001-python-sdk/tasks.md)。

`src/aegis/tracing/` 管理生命周期与上下文，`decorators/` 提供入口，`exporters/` 提供有界队列与本地 JSONL。`integrations/openai/` 实现可选模型代理，`aegis/langgraph.py` 提供可选显式图代理；核心 import 不导入 OpenAI 或 LangGraph。

JSONL 是本地调试格式；网络契约见 [SPEC-002](../../specs/002-collector/spec.md)。

## 网络接入

独立使用 SDK 时可执行 `python -m pip install -e "./sdk/python[otlp]"` 安装可选依赖。按根目录锁文件安装的开发环境已包含 OTLP 依赖。

```python
import os
import aegis

aegis.init(
    service_name="order-service",
    endpoint="http://127.0.0.1:8000/v1/traces",
    export_timeout_millis=3000,
    headers={"Authorization": f"Bearer {os.environ['AEGIS_API_TOKEN']}"},
)
```

`output_path`、`endpoint`、自定义 `exporter` 三选一；headers 只可与 endpoint 使用。超时为 1–30000 毫秒整数，endpoint 不含用户名密码、query 或 fragment。官方 Exporter 的有限重试仅重发遥测；队列与 flush/shutdown 等待仍有界。服务端及本地 Compose 见 [Collector](../../collector/README.md)。

flush 只等待已完成并入队的 Span，关闭前应结束业务工作；超时的自定义 Exporter 不能被强制终止。内容采集开关、Trace 用量汇总和成本尚未实现；LangGraph 首批显式适配见下文。

## OpenAI 模型客户端

独立安装可选依赖：`python -m pip install -e "./sdk/python[openai,otlp]"`。根锁文件已包含本次版本 OpenAI 3.33.0 / HTTPX2 2.13.1。

```python
from aegis.openai import AegisOpenAI, AegisAsyncOpenAI, wrap_openai

client = wrap_openai(existing_openai_client)
# 现有 responses.create(...) / chat.completions.create(...) 调用保持。
```

两类 create 支持同步/异步与 stream=True；原响应/事件和异常对象保持，客户端和流为代理对象，不能依赖原 Stream 类型判断。with_options / copy 继续追踪。未覆盖 API 委托给原客户端且不追踪；raw / parse / Responses.stream 辅助器、Realtime、WebSocket、Azure、Agents SDK 不在支持矩阵中。

保留 SDK 重试和请求参数，不添加 include_usage；Chat 流用量需应用主动传入 stream_options。流须消费到结束或显式 close / with / async with；单纯 break 不承诺清理。Span 只在请求/取事件期间激活，消费者工具不会挂错父节点。具体生命周期、未知用量与隐私契约见 [SPEC-004](../../specs/004-openai/contracts/llm-span.md)，可运行步骤见 [示例](../../examples/openai/README.md)。真实 Provider 验证延后。

## DeepSeek Provider

独立安装额外组：`python -m pip install -e "./sdk/python[deepseek,otlp]"`；与 openai 组共用锁定 OpenAI 3.33.0，不增加依赖。

```python
from aegis.deepseek import AegisDeepSeek

client = AegisDeepSeek()  # 从本机 DEEPSEEK_API_KEY 读取，默认官方 endpoint
# 原有 client.chat.completions.create(...) 调用保持。
```

也有 AegisAsyncDeepSeek，已有官方客户端可用 `wrap_openai(client, provider="deepseek")`。显式 provider 仅接受 openai / deepseek，copy / with_options 保留；重复包装幂等、冲突拒绝。DeepSeek 当前只追踪 Chat create，Responses 委托且不追踪。未提供 DeepSeek key 时不回退到 OpenAI 环境变量。工厂允许显式 base_url 配置，但仅官方 endpoint 在本轮目标范围内。

默认离线示例和可选 live 步骤见 [DeepSeek 示例](../../examples/deepseek/README.md)。SDK 当前 38 个测试通过，旧段落的 32 是 SPEC-004 当时证据；最新结果见 [SPEC-005](../../specs/005-deepseek/tasks.md)。

## LangGraph

独立安装 `python -m pip install -e "./sdk/python[langgraph,deepseek,otlp]"`，本轮固定 LangGraph 1.2.15；完整测试依赖按根锁文件安装。模型依赖与框架依赖仍可分别选择。

```python
from aegis.langgraph import observe_graph

graph = observe_graph(existing_compiled_graph, name="order-agent")
result = graph.invoke(input_state, config=existing_config)
# 异步：await graph.ainvoke(input_state, config=existing_config)
```

初始化与导出仍使用 aegis.init / flush / shutdown；图只记录 Agent 边界。模型使用现有 Wrapper，工具在 StructuredTool 构造前用 aegis.tool 标记。with_config 保持代理，参数、context、callbacks、返回/异常身份保留；重复包装幂等，冲突名称拒绝。代理不保持 CompiledStateGraph 类型身份。

stream / astream 已按 SPEC-007 支持：首次消费才创建图 Span，逐项原样交付，不在 yield 后保留图上下文。支持显式 close / aclose 及 with / async with；提前关闭记录 closed，EOF 为 completed，错误/取消分别为 error/cancelled。图 metadata 为 aegis.graph.v1，本地记录 aegis.span.v3；invoke / ainvoke 的原 v1 不变。请配套升级 Collector。

范围外事件投影、batch / with_retry 等委托原对象，不自动创建图 Span，也不保证返回对象继续追踪。checkpoint/interrupt、Functional API、原生 ChatModel 与自动节点发现未验收。真实框架离线测试与步骤见 [示例](../../examples/langgraph/README.md)，当前 SDK 57 方法通过，见 [SPEC-007](../../specs/007-langgraph-stream/tasks.md)。

## 可选 Runtime 权限控制

SPEC-009 的 aegis_runtime.Runtime 是独立组件，通过宿主绑定身份和不可变本地策略，在受保护工具调用前执行 allow / deny。现有 aegis.tool(permission=...) 仍仅记录元数据；实际控制使用 runtime.tool 替换工具装饰器。SDK 核心不依赖 Policy / Runtime，未初始化遥测也不能绕过已接入的 Runtime。

受控尝试使用 aegis.governance.v1 / execute_tool / INTERNAL，本地 JSONL v4，记录 action ID、决策、固定原因、subject、规则/版本与 outcome；不保存工具参数、结果或异常正文。拒绝 outcome=denied 不表示工具执行过；allow 与工具异常分别记录。公共 aegis.governance.governed_tool_span 是 Runtime 使用的遥测上下文，本身不执行授权，不能替代 Runtime。Collector 需要配套升级，迁移仍为 {1,2}。详情见 [Runtime](../../runtime/README.md)、[示例](../../examples/runtime-policy/README.md) 与 [009](../../specs/009-runtime-policy/spec.md)。当前 SDK 59 方法通过。

SPEC-045：可选治理v2记录require_approval的request/execute阶段，JSONL为span.v5，旧映射保持。该遥测不执行或授权工具，详见[策略审批](../../docs/policy-approval.md)。

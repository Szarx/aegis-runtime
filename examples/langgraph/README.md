# LangGraph Agent 示例

SPEC-006 已完成真实 LangGraph 1.2.15、langchain-core 1.6.12、prebuilt 1.1.1 的显式 invoke / ainvoke 离线验证。实际运行 StateGraph、条件边和 ToolNode；模型为官方 OpenAI SDK 的合成 DeepSeek transport，没有收费 API 或 LangSmith 请求。

## 安装与运行

仓库根目录，创建/激活 Python 3.11+ 环境，本次验证 Python 3.12.14：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python
python examples/langgraph/agent.py
python examples/langgraph/agent.py --async
python examples/langgraph/agent.py --fail-tool
python examples/langgraph/agent.py --async --fail-tool
```

默认写 artifacts/langgraph/traces.jsonl，--output 可更改。CLI 按同一图工厂执行未接入 / 已接入两遍，比较业务消息和调用次数；不打印模型正文。每遍 2 模型 / 1 工具，只有 traced 生成 4 Span。--fail-tool 让真实 ToolNode 处理合成 ValueError，结果保持一致，Tool 标错误、Agent 正常返回。传播失败与取消另由测试覆盖。

CLI 明确关闭该示例进程的 LangSmith 跟踪；适配器本身不改宿主遥测配置。没有 live 参数，不读取 DeepSeek / OpenAI 真实 Key。

## 接入已有图

三个显式接入点：模型使用 wrap_openai / 已有 Aegis 客户端；工具函数在 StructuredTool 构造前用 aegis.tool 包装；编译后使用 observe_graph。图的状态、节点、边与执行调用保留。最小差异见 [integration.md](../../specs/006-langgraph/contracts/integration.md)，SDK init / flush / shutdown 和导出配置另计。

```python
from aegis.langgraph import observe_graph

graph = observe_graph(existing_compiled_graph, name="order-agent")
result = graph.invoke(input_state, config=existing_config)
```

with_config 保持追踪，config/context/callbacks 原样交给框架，返回/异常对象保持；重复包装幂等，冲突名称拒绝，代理不保持原 CompiledStateGraph 类型身份。没有显式装饰的工具、没有 Wrapper 的模型不自动发现。

当前支持 invoke / ainvoke / stream / astream 和 with_config。事件投影 stream_events / astream_events、batch、checkpoint/interrupt 恢复、Functional API、LangChain ChatModel 自动追踪未验收；范围外方法委托原对象，不自动创建图 Span 或保证返回图继续包装。

## Collector / Dashboard

按 [本地部署](../../deploy/docker/README.md) 启动后，PowerShell：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/langgraph/agent.py --endpoint http://127.0.0.1:8000/v1/traces
python examples/langgraph/agent.py --async --fail-tool --endpoint http://127.0.0.1:8000/v1/traces
```

Dashboard 连接同一 token，选择 langgraph-order-agent，核对 Agent、两个模型和工具、模型 7/3 合成用量与错误。endpoint 与 output 互斥。失败工具会使 Trace 汇总 ERROR，框架已处理后 Agent Span 仍正常，这两种状态不能混为一谈。

本地缓存环境四组对照到首个 flush 为 216.699–276.528 ms，仅为已经安装好依赖和启动平台后的实验，不包含安装/人工接入。新用户 5 分钟目标仍待测量。具体版本、命令与证据见 [tasks](../../specs/006-langgraph/tasks.md)。

## 状态流：SPEC-007

```text
python examples/langgraph/stream.py
python examples/langgraph/stream.py --async
python examples/langgraph/stream.py --early-close
python examples/langgraph/stream.py --async --early-close
python examples/langgraph/stream.py --fail-tool
python examples/langgraph/stream.py --async --fail-tool --endpoint http://127.0.0.1:8000/v1/traces
```

默认文件 artifacts/langgraph-stream/traces.jsonl，可用 --output 更改；endpoint 与 output 互斥。六组 CLI 都先执行 baseline，再执行 traced，对照 chunk 序列和模型/工具次数，仅打印计数和诊断。完整消费或框架处理工具错误：每遍 2 模型 / 1 工具、traced 4 Span；首次 chunk 后关闭：每遍 1 模型 / 0 工具、traced 2 Span。模型始终离线，不读真实凭证。

已有图的消费端可用以下公开入口，提前 break 时也会明确关闭：

```python
with graph.stream(input_state, config=existing_config, stream_mode="updates", version="v2") as chunks:
    for chunk in chunks:
        consume(chunk)
        if should_stop():
            break

# 在异步函数中：
async with graph.astream(input_state, stream_mode="updates", version="v2") as chunks:
    async for chunk in chunks:
        await consume_async(chunk)
```

首次取值才创建 Span；没有消费便关闭不产生图 Span。只在推进/关闭流时激活图上下文，消费者工具不误挂图节点。chunk 原样返回，不采集其正文。不要只 break 后依赖 GC；也可显式 close / await aclose。EOF 记录 completed，未观察 EOF 的关闭记录 closed；没有回滚或 checkpoint 恢复保证。

真实框架验证 updates / values、组合模式、v1/v2 格式和 custom；messages 参数只转发，不代表原生 ChatModel 自动记录 Token。Dashboard 区分提前关闭、取消、异常和完成；工具异常已被框架处理时，图可以 completed，而 Trace 因工具为 ERROR。生命周期与兼容范围见 [007 契约](../../specs/007-langgraph-stream/contracts/stream.md)，完整证据见 [007 任务](../../specs/007-langgraph-stream/tasks.md)。

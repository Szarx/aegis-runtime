# 统一接入中的图调用和流式生命周期

Application.graph把已有LangGraph的四种调用放进[统一接入](application-onboarding.md)的生命周期。它借用原SDK adapter，支持invoke、ainvoke、stream、astream和with_config；配置v1/v2/v3及服务API不变。不需要模型服务，下面示例用官方SDK合成transport运行两轮模型/工具循环。

## 装配已有图

```python
from aegis_runtime.application import Application, load_application
from aegis.openai import wrap_openai

with Application(load_application("aegis.json"), subject="reader") as app:
    tool = app.tool(lookup_order)
    observed_client = wrap_openai(client, provider="openai")
    raw_graph = build_business_graph(observed_client, tool)
    graph = app.graph(raw_graph, name="order-agent")
    result = graph.invoke(initial_state)
    with graph.stream(initial_state, stream_mode="updates", version="v2") as events:
        for event in events:
            handle_event(event)
```

这是装配片段，完整代码见[示例](../examples/managed-graph/README.md)。工具需在构图前经app.tool绑定，模型使用既有显式Wrapper；既有手动SDK用户可继续observe_graph。替换原Agent包装即可，不要再用app.agent包装graph.stream，也不必在app.graph外叠加observe_graph。工具/模型未包装就不会被自动发现，原始函数和图仍是可信宿主代码，不是Python沙箱。

句柄不代理get_state、update_state、batch、astream_events等其他方法；要调用其他图API，由宿主持有raw_graph并自行管理。with_config原样传递配置并返回同会话句柄；四种方法透传参数和业务对象/流事件，支持原updates、values、组合模式及v1/v2流格式。这里观测图流，不把事件投影为LLM调用或审批授权。

## 流从首次拉取到关闭

创建stream/astream时会话必须活动，但不会执行业务、产生Span或长期占用租约。首次next/anext才持有租约，直到EOF或清理成功。跨yield只保留调用计数，OTel活动上下文由原SDK在拉取期间恢复，消费者处理事件时不误归入图Span。

```python
events = graph.stream(initial_state)
try:
    first = next(events)  # 开始持有租约
    # 可以停止消费，但必须显式关闭。
finally:
    events.close()
```

单独break不会关闭Python迭代器。已开始且未清理的流使Application.close报busy；宿主必须显式关闭并等待任务结束后再退出Application。闲置流不阻止关闭，但之后不能首次拉取业务；仍可关闭这个闲置句柄。结束后的关闭是幂等的，无GC自动清理。

## 异步、取消和清理失败

```python
async with AsyncOpenAI(...) as client:  # 客户端仍由宿主拥有
    with Application(config, subject="reader") as app:
        graph = app.graph(build_business_graph(wrap_openai(client), app.tool(async_tool)))
        async with graph.astream(initial_state, stream_mode="updates") as events:
            async for event in events:
                await handle_event(event)
```

异步在调用者循环原生await，不创建后台消费/清理任务或线程桥接。一个流只能有一个进行中的拉取/关闭，不能并发消费或跨事件循环；不同流可分别消费。宿主负责关闭图依赖的模型客户端、checkpointer等资源，Application只关闭自己的SDK。

节点异常/取消保持原对象，不重跑业务。拉取失败后尝试关闭源流；清理失败不会覆盖原异常。**已经开始的流若清理失败，租约继续保留，不能再拉取**；宿主需在原循环重试close/aclose，成功后才关闭Application。消费者上下文中的原异常同样不会被清理异常替换；不要在清理未完成时直接离开Application，否则busy错误可能覆盖正在传播的异常。清理本身被再次取消也需要宿主后续显式完成，不在后台屏蔽取消。

## 完整离线示例

从仓库根目录安装本地开发包及显式框架/模型extra：

```text
python -m pip install "./sdk/python[langgraph,openai]" ./policy-engine ./runtime
python examples/managed-graph/run.py --mode invoke
python examples/managed-graph/run.py --mode ainvoke
python examples/managed-graph/run.py --mode stream
python examples/managed-graph/run.py --mode astream
python examples/managed-graph/run.py --mode astream --early-close
python examples/managed-graph/run.py --mode stream --subject blocked
python examples/managed-graph/run.py --mode stream --fail-tool
python examples/managed-graph/run.py --mode astream --stream-mode combined --version v1
```

无真实模型请求和凭证需求；offline.invalid请求由进程内合成transport处理，LangSmith关闭。每条命令先跑无Aegis的业务基线，再跑统一接入版本，终端只输出计数/等价性/诊断。完整允许时2模型+1工具+1Agent共4Span、业务执行1次；拒绝时业务0次、仍有工具deny事件；首个updates后关闭只有1模型+1Agent，工具未执行。fail-tool为框架处理的业务异常，图仍正常完成，Tool Span保留error。状态/消息和模型内容不写入遥测。

默认JSONL在artifacts/managed-graph/traces.jsonl追加。将示例配置telemetry改成[原OTLP形状](application-onboarding.md)，显式安装SDK otlp extra并提供Trace token后，可将同样矩阵送入Collector/PostgreSQL，在现有Dashboard查看Trace/Token/图生命周期，在安全事件中心查看工具决策并跳转原Trace。[导出指南](security-export.md)可保存治理排查包并离线核验。

## 时间与能力边界

沿用SDK图流outcome：EOF completed、提前关闭closed、未处理节点异常error、取消cancelled。invoke/ainvoke仍是普通Agent Span，无流outcome。ToolNode处理工具异常后继续返回时，图可以completed而Trace含ERROR工具；不能把graph completed等同业务成功。

模型Span测量客户端请求开始至响应完成的耗时；图流Span包含业务执行与消费者等待，不能当成模型服务端纯推理时间。当前不单独测量首Token延迟。示例中的模型是两次非流式Chat调用，图事件流不表示模型Token流；原模型流Wrapper能力保持。

Trace只记录既有白名单元数据，不采集消息/工具参数/流payload/callback metadata/凭证。身份和配置依赖可信宿主，不能证明所有未接入调用已记录。审批图仍按[配置持久化审批图](configured-graph.md)显式操作原compiled graph，不用此观测句柄代替checkpoint绑定或人工批准。

验收见[SPEC-028](../specs/028-managed-graph-stream/tasks.md)。不新增服务/迁移/UI，不声明真实Provider、在线安装、人工首次接入计时或新GUI验收。

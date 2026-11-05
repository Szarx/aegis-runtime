# 配置驱动的持久化审批图

把[统一接入](application-onboarding.md)、[完整参数审核](configured-review.md)和[本机持久化图](durable-graph.md)连成一个流程。服务本身不依赖LLM；宿主使用真实LangGraph、独立审批服务和本机SQLite。同步与原生异步共享原013–015安全边界，服务API和四迁移不变。

## 配置和宿主装配

```json
{
  "schema_version": "aegis.application.v3",
  "service_name": "configured-graph",
  "policy_file": "policy.json",
  "tools": [{
    "name": "write", "permission": "records.write",
    "execution": "reviewed_graph", "tool_revision": "write-v1",
    "graph": {"id": "configured-demo", "revision": "graph-v1", "node": "review"}
  }],
  "telemetry": {"mode": "jsonl", "path": "traces.jsonl"}
}
```

v3的每个工具严格提供五个字段。direct的tool_revision/graph均为null；reviewed需要tool_revision、graph=null；reviewed_graph需要工具版本和完整graph。v1/v2保持原形状和报告，不能声明reviewed_graph；旧加载器拒绝v3，不把它降级为普通工具。配置来自可信宿主，工具/图实现变化需宿主更新相应版本，标签不能验证任意Python实现。

```python
with Application(load_application("aegis.json"), subject="demo-agent") as app:
    gate = app.reviewed_graph_tool(write, client=client, disclose_arguments=True)
    # 把gate.node装入配置指定的节点；使用持久化checkpointer编译单根图。
    graph = compile_host_graph(gate.node, saver)
    app.agent(graph.invoke)(initial_state, thread_config, durability="sync")
    ticket = gate.prepare(graph, thread_config, summary="Synthetic write")
    # 保存ticket后交给独立reviewer审核，宿主不自动批准或轮询。
```

这是装配片段；完整可运行代码见[示例](../examples/configured-graph/README.md)。新进程重开同一SQLite、同版本配置/工具、主体和binding_key，重新绑定并编译图，调用`gate.resume(graph, thread_config, ticket)`。返回GraphExecutionResult(value, confirmation, continuation, graph_state)：只有确认confirmed且精确snapshot仍匹配才向原interrupt提交HMAC收据并继续图。业务函数在宿主驱动中执行，不在中断节点里重做。

app.tool/app.reviewed_tool都拒绝reviewed_graph；图入口拒绝direct/reviewed、未知或重复绑定。句柄不可直接作为业务函数调用，node只处理中断和验证收据。prepare/resume整体及node均受Application租约保护，覆盖网络、业务和图继续；关闭后入口失效，有未完成操作时close拒绝。宿主必须等待图任务完成再退出上下文，Application不是Python沙箱，原始函数仍是宿主代码。

## 同步和异步资源

同步借入ReviewedClient；异步函数借入AsyncReviewedClient。异步入口是原生await，不创建后台任务或用线程桥接同步驱动。宿主用原事件循环关闭客户端，Application不取得客户端/图/数据库所有权，只管理自身SDK。同步使用open_reviewed_checkpointer；异步先用原helper显式创建/验证格式，再在宿主aiosqlite上下文调用configure_async_reviewed_checkpointer。必须await/join全部操作后关闭这些资源。

inspect输出显式v3报告，列模式、工具/图版本和requires_review；只读，不启动SDK、不验证图依赖导入、checkpoint兼容或审批角色。Policy allow仍不能代替批准。status中的tool_modes提供相同配置元数据，不表示服务端执行状态。

## 从暂停到跨进程恢复

在仓库根目录安装本地SDK、Policy和Runtime：

```text
python -m pip install ./sdk/python ./policy-engine "./runtime[reviewed-langgraph-sqlite]"
python -m pip install "./runtime[reviewed-langgraph-async]"
python -m aegis_runtime inspect examples/configured-graph/application.json --subject demo-agent
```

第二行仅异步需要。按[部署指南](../deploy/docker/README.md)启用Collector producer/reviewer/executor独立角色。Agent宿主环境仅提供AEGIS_APPROVAL_REQUEST_TOKEN、AEGIS_APPROVAL_EXECUTION_TOKEN、至少32字节hex的AEGIS_APPROVAL_BINDING_KEY；不用reviewer凭证。若改OTLP配置，再显式安装SDK otlp extra并提供对应Trace token环境变量。不要提交真实凭证。

```text
python examples/configured-graph/agent.py start --config examples/configured-graph/application.json --state artifacts/my-configured-graph --endpoint http://127.0.0.1:8000
python examples/configured-graph/agent.py status --config examples/configured-graph/application.json --state artifacts/my-configured-graph
```

先创建父目录artifacts，state本身必须不存在。start输出action_id与pending，此时业务计数0，目录含checkpoint.sqlite3及ticket.json。status无需审批/Trace凭证，读取本地checkpoint，不启动SDK、不联系审批服务；本地SQLite仍按已有helper以读写连接验证格式，不承诺文件字节完全不变。status仅报告pending/completed/next，不能证明已批准。

独立reviewer在现有Dashboard“执行审批”核对完整参数、图/工具版本及摘要后批准或拒绝，页面不执行工具。批准后运行新进程：

```text
python examples/configured-graph/agent.py resume --config examples/configured-graph/application.json --state artifacts/my-configured-graph --endpoint http://127.0.0.1:8000
```

成功输出confirmed/resumed，tool-calls.jsonl只有一行计数；status变completed=true、pending=false。再次resume失败，计数仍1。两阶段和status均加--async，可用另一个新state验证异步。start --scenario failure演示执行后异常；异步start --scenario cancel演示部分效果后取消。业务只记计数，终端不打印参数或业务结果。

退出码：0准备/状态查询/图恢复成功；1未完成（未批准/拒绝/不匹配等）；2业务异常；3异步取消；4业务确认或图继续未明确成功。命令不会根据退出码自动重试或重开动作。start在图暂停后、ticket落盘前崩溃不自动恢复，保留目录用于排查，勿覆盖原checkpoint。

## 披露、故障和范围

disclose_arguments=True明确允许把签名/defaults后的完整JSON参数连同图绑定送到审批服务。ticket和SQLite也包含参数，状态目录是宿主敏感数据，应保存在受访问控制的位置，不提交Git。Trace与治理事件保留白名单元数据，无参数/凭证/业务返回。身份、工具版本和本地文件完整性依赖可信宿主，不是服务认证或防篡改审计证明。

仅支持同一受控宿主的单个根interrupt和本机SQLite。精确checkpoint、interrupt、thread/call、参数、策略摘要、图/工具版本及binding_key都绑定动作。claim一经消费不能撤销；业务失败/取消可能已有副作用，unknown不再执行。业务确认和图checkpoint不构成同一事务：complete已提交但回执丢失时，服务端completed而图仍pending；继续失败也可能unknown。需要人工对账，不支持重建完成收据、多机分布式恰好一次、多中断/子图或自动补偿。

验收见[SPEC-027](../specs/027-configured-graph/tasks.md)。复用既有审批页面/API，新增页面和人工操作耗时不在本轮声明中。

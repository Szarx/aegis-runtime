# LangGraph的单个审批中断

SPEC-013扩展同步ReviewedTool到真实LangGraph的单个顶层interrupt。复用 [执行审批](reviewed-execution.md) 的三角色和永久消费领取；不新增服务端状态/迁移/页面。核心服务仍无LLM依赖。支持锁定LangGraph1.2.15、Python3.11+；本轮实际执行Python3.12.14。

## 安装和图接入

仓库根目录，先安装本地SDK/Policy：

```text
python -m pip install -e ./sdk/python -e ./policy-engine -e "./runtime[reviewed-langgraph]"
```

extra固定langgraph==1.2.15；核心Runtime和新模块的导入不加载LangGraph，构造ReviewedGraphTool时才要求可选依赖。宿主使用稳定graph_id、graph_revision、node_name、tool_revision、身份、Policy、客户端凭证与binding_key。

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from aegis_runtime.langgraph_reviewed import ReviewedGraphTool

class State(TypedDict, total=False):
    aegis_call: dict
    aegis_reviewed: dict

gate = ReviewedGraphTool(existing_sync_write, client=reviewed_client,
    policy=policy, subject="order-agent", permission="orders.write",
    tool="write_order", tool_revision="write-v1", disclose_arguments=True,
    graph_id="orders", graph_revision="graph-v1", node_name="review")
builder = StateGraph(State)
builder.add_node("review", gate.node)
builder.add_edge(START, "review")
builder.add_edge("review", END)
graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "trusted-thread-1"}}
paused = graph.invoke({"aegis_call": {
    "call_id": new_nonzero_uuid_hex, "arguments": {"order_id": "synthetic"}}}, config)
ticket = gate.prepare(graph, config, summary="合成订单修改", ttl_seconds=300)
# 保存ticket，独立人工核对/批准后，宿主显式恢复：
# outcome = gate.resume(graph, config, ticket)
```

此为接入片段；现成无模型Agent见 [示例](../examples/langgraph-reviewed/README.md)。首版只支持普通同步具名JSON工具，以及原生CompiledStateGraph、单个根任务/interrupt，config仅允许configurable.thread_id。异步图、子图、多并行interrupt、历史checkpoint/config覆盖、callbacks扩展及自动ToolNode包装待后续独立验证。已有observe_graph观测接口不改变；此驱动要求原生图，可用aegis.observe包围宿主resume记录Agent→受控Tool。

## 重跑与绑定

interrupt节点在恢复时会重新进入，因此gate.node只生成请求、暂停和校验完成收据，审批网络与真实工具由宿主驱动执行。不要在该节点前后添加需要单次保证的额外副作用。其他图节点仍由宿主负责。

审核参数为{graph_binding, arguments}，包含规范化默认值和精确graph/thread/checkpoint/interrupt/版本绑定。ticket可存为JSON，含完整实参，需与checkpoint同样保护；不用pickle，不从模型参数取身份/凭证。

action_id由稳定graph_id/thread_id/call_id及binding_key派生。同一逻辑调用修改checkpoint/参数/版本时仍是同一动作，旧ticket失效、新绑定不能覆盖旧审批或把已消费动作变成新动作。保持这些标识/key稳定，不要换id或key重试未知副作用。新的业务意图才使用新的call_id。

宿主必须串行管理同一thread的图调用/编辑。驱动在领取前及原函数前读取最新snapshot、执行后再检查；函数前checkpoint读取完成后再核对单调时效，慢存储不能延长批准有效期。图存储与审批库没有共同事务，不能防止可信宿主在最终检查后并发修改图。本轮复用同一个InMemorySaver验证宿主对象/编译图重建；跨进程持久checkpointer、迁移和备份恢复尚未验收。

## 返回和未知结果

| confirmation / continuation | 含义 |
| --- | --- |
| confirmed / resumed | 工具完成已确认，图invoke正常返回，graph_state可读取 |
| unknown / not_resumed | 工具返回，但结果确认未知；未调用图恢复 |
| confirmed / blocked | 工具完成后checkpoint变化；未调用图恢复 |
| confirmed / unknown | 工具完成，继续图时发生普通异常；图可能已有后续副作用 |

GraphExecutionResult.value保留工具原返回对象，不写入checkpoint；节点只写aegis_reviewed完成标记。业务异常保留原对象、尝试failed确认并不恢复图。领取网络故障可能已经消费动作；全部未知状态不自动重试，人工分别查询审批和checkpoint。新BaseException（如宿主中断）继续传播。

仅completed确认后生成HMAC收据，绑定请求/thread/root checkpoint，针对原interrupt_id发送Command。布尔“批准”或篡改收据不能通过节点；MAC不是不可信宿主认证，持有binding_key的宿主仍可信。收据不含业务结果或额外参数正文；graph_state原本仍可能含输入实参。

遥测不增加state/config/ticket/正文；审批和checkpointer按主动披露保存实参。工具确认和图继续之间崩溃时，图可能保持暂停但动作已completed；这不是再次调用工具的理由。本轮不提供自动恢复收据、持久事务审计、跨系统恰好一次、Policy require_approval或生产多租户。

设计见 [ADR-0007](adr/0007-langgraph-reviewed.md) 和 [013验收](../specs/013-langgraph-reviewed/tasks.md)。

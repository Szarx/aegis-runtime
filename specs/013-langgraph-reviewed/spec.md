# SPEC-013：LangGraph单个审批中断的受约束恢复

日期：2026-10-20；范围冻结。首版同步宿主、普通同步具名JSON工具、一个顶层待处理interrupt。复用011审批协议、012既有兼容边界；无LLM、服务端/迁移/前端变更。async图、多并行interrupt、子图、历史checkpoint分叉、跨进程checkpoint后端和通用ToolNode自动发现不在本轮。

## 接口和调用顺序

可选aegis_runtime.langgraph_reviewed.ReviewedGraphTool，extra reviewed-langgraph固定langgraph==1.2.15（已有59-pin）。导入模块不加载LangGraph，构造时才要求可选依赖。构造参数延续ReviewedTool，新增宿主固定graph_id、graph_revision、node_name；普通同步函数，显式完整参数披露。

1. 宿主注册gate.node作为node_name，编译带checkpointer的原生CompiledStateGraph，输入aegis_call={call_id:非零32hex,arguments:具名JSON}，config仅支持configurable.thread_id（受限标识符）。节点补默认值、生成有界JSON请求并interrupt，无审批网络/工具副作用；不捕获GraphInterrupt。
2. gate.prepare(graph,config,summary,ttl_seconds)读取最新snapshot，要求根namespace、唯一任务/interrupt、next仅该节点、请求与state一致；构造JSON ticket并向现有reviewed-actions准备。审批review_arguments是{graph_binding,arguments}，审核人可以同时看到具体checkpoint绑定和工具实参。
3. 人工独立审核；gate.resume(graph,config,ticket)校验ticket/最新snapshot，调用已有ReviewedTool，领取后且函数前再次读取checkpoint并比对，读取完成后再次检查保守单调时效，才开始工具；慢checkpointer不能延长有效期。工具不在interrupt节点中执行，所以节点重跑不会再次调用它。
4. 只有completed确认成功且snapshot仍匹配时，宿主驱动才发送针对interrupt_id的Command恢复。node仅接受绑定请求/thread/checkpoint的HMAC结果收据，返回aegis_reviewed完成标记；业务原value单独返回宿主，不写入checkpoint。布尔批准或篡改收据不能推动该节点完成。

## 绑定与重复执行

graph_binding包括graph_id/revision、node、thread_id、checkpoint_id、interrupt_id、call_id和规范化请求摘要。身份/Policy/permission/tool_revision、summary、TTL和整个参数信封仍按011绑定。ticket必须严格JSON、固定字段，有界；主机/版本/参数/策略不符不得执行。

action_id由binding_key和graph_id/thread_id/call_id域分离HMAC确定，故同一逻辑call在checkpoint更新、参数/版本变化、重复prepare、宿主重建后仍使用同一action；不同绑定不能把已消费动作变成新动作。宿主必须保持graph_id、thread_id、call_id和binding_key稳定，新的业务意图使用新call_id，不能以换key/id方式重试未知副作用。checkpoint编辑会使旧ticket失效；新ticket复用原action_id，服务端拒绝不同绑定。

宿主需串行管理同一thread的invoke/update_state，checkpoint与审批库之间没有原子事务。函数前最后一次snapshot检查缩小失效窗口，不承诺防止可信宿主在检查后并发修改图状态。原函数、宿主、checkpointer与数据库管理员仍可信；不是沙箱/远程身份认证。其他图节点的副作用由宿主管理。

## 结果与故障

GraphExecutionResult保留原value和confirmed/unknown，新增continuation=resumed/not_resumed/blocked/unknown与graph_state。确认未知不调用图恢复；执行后checkpoint变化返回blocked；图invoke普通异常返回unknown（工具已完成，不重新调用），graph_state=None；新的BaseException继续传播。明确查询/人工调查，不自动重试工具或图。业务函数异常保持原对象，沿用failed确认，不恢复图；领取/确认网络未知沿用011永久消费。

成功收据不含业务返回值/参数正文，只含动作/绑定和MAC，node验证后仅写完成标记。图输入/checkpoint和审核参数都可能包含完整业务实参，需宿主主动披露并保护；不新增state/config/ticket/异常正文遥测。可用既有aegis.observe包围宿主执行并保持治理Tool父子关系，保持旧observe_graph行为。

## 验收

| AC | 验证 |
| --- | --- |
| 1301 | 真实StateGraph暂停、节点重跑纯净；默认值/严格JSON/显式披露/同步范围、config/图/多interrupt拒绝 |
| 1302 | 精确checkpoint/thread/interrupt/request/版本绑定；稳定action，参数/版本/checkpoint改动不得生成替代执行；ticket/布尔及收据篡改拒绝 |
| 1303 | 准备/未批准/拒绝零副作用；批准一次、重复/并发不多执行、业务异常身份、claim丢失/完成未知/图恢复失败不重试；函数前重新检查state |
| 1304 | 工具成功value身份和上下文/隐私、未知后不调用图、checkpoint后验变化blocked、收据不持久化业务返回值 |
| 1305 | 实际HTTP+PG+真实图；重建宿主/编译图并复用同一测试checkpointer后恢复，已消费动作仍拒绝；不冒称InMemorySaver跨进程持久性 |
| 1306 | 核心/extra隔离、wheel、原OpenAPI/四迁移不变、官方资源/文档/示例/机器验收记录，无真实LLM |

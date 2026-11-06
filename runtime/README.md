# Aegis Runtime

当前公开预览包含策略三类决策、配置 v4、同步/异步审批和受约束图恢复。完整范围以[当前能力](../docs/capabilities.md)为准；下列按 SPEC 编号保留的计数和阶段说明是历史记录。授权为 [Apache-2.0](LICENSE)。
状态：SPEC-009 的最小进程内工具权限控制已实现，验收状态见 [任务](../specs/009-runtime-policy/tasks.md)。本地开发分发名 aegis-runtime-control，未公开发布。

## 目录职责

SPEC-028新增app.graph限定句柄，统一invoke/ainvoke/stream/astream/with_config。首次拉取到EOF或清理成功持有会话租约，清理失败不释放、取消与原异常保持；借用原SDK显式LangGraph适配，不改变配置或审批协议。见[流式接入指南](../docs/managed-graph-stream.md)和[模型/工具完整示例](../examples/managed-graph/README.md)。

SPEC-026把人工审核接入Application：v2配置显式声明reviewed模式和工具版本，app.tool拒绝降级，app.reviewed_tool以明确参数披露及宿主借用客户端复用原同步/异步审批协议。prepare/resume受会话租约约束，客户端资源仍由宿主拥有；v1配置/报告保留。见[配置审批指南](../docs/configured-review.md)和[分进程示例](../examples/configured-review/README.md)。

SPEC-027的v3追加reviewed_graph与图ID/版本/节点。app.reviewed_graph_tool提供受Application租约保护的node/prepare/resume，借用原同步/异步图协议，支持本机SQLite跨进程暂停/审核/执行/继续。普通绑定不能降级，依赖仍为显式图extra；旧配置保持。见[配置审批图指南](../docs/configured-graph.md)和[完整示例](../examples/configured-graph/README.md)。

SPEC-025新增application模块和`python -m aegis_runtime inspect`，将配置/Policy快照、工具注册、SDK生命周期和诊断整合到已有Agent的接入流程，支持原生/真实LangGraph同步异步示例。原Runtime/审批实现保持，配置入口不自动保护未包装工具或授权审批。见[统一接入指南](../docs/application-onboarding.md)和[示例](../examples/configured-agent/README.md)。

- `src/aegis_runtime/__init__.py`：不可变 Runtime、工具装饰器、调用前决策和 ActionDenied。
- `src/aegis_runtime/context/` / `interceptors/`：为后续审批/恢复拆分保留，当前没有独立实现。
- `tests/`：拒绝零次执行、允许一次、策略/遥测故障、异常/取消、并发与真实 ToolNode。

Runtime 在产生工具副作用前执行控制，不承载遥测接收、数据库访问或 Dashboard。策略模块通过清晰接口调用；业务工具仍由 Agent 应用执行。运行方式是进程内库，首版不增加独立 Runtime 服务。

SDK 观测仍可独立使用。需要实际控制时安装本地 Policy/Runtime 并显式包装受保护工具；旧 aegis.tool 的 permission 标签保持仅观测。

## 安装与接入

仓库根目录激活开发环境后：

```text
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime
python -m unittest discover -s runtime/tests -v
python examples/runtime-policy/agent.py
```

```python
from aegis_policy import Policy
from aegis_runtime import Runtime

policy = Policy.from_json(existing_local_policy_json)
runtime = Runtime(policy=policy, subject="order-agent")

@runtime.tool(permission="orders.read")
def lookup_order(order_id):
    return existing_lookup(order_id)
```

宿主启动代码负责 policy 和 subject，不从模型或工具参数推断身份。缺身份、缺权限、缺策略、求值错误和无匹配都拒绝，显式 deny 优先。拒绝抛固定 ActionDenied(PermissionError)，工具执行零次；允许只执行一次。同步和普通异步函数均支持，生成器暂不支持。Runtime 实例/策略是不可变快照，不热更新。

Agent 入口沿用 aegis.observe；受控工具使用 runtime.tool 替换旧 aegis.tool，避免重复 Span。未初始化/已关闭 SDK 或遥测失效仍执行相同授权检查。决策遥测不持久化成功也不自动放行；允许决策的工具仍按原逻辑执行，导出不是事务审计。

这是进程内控制，无法防止同进程恶意代码调用原函数，也不认证外部用户或提供租户隔离。部署方负责实际工具入口和宿主身份可信性。审批准备与显式恢复接入见下文；通用自动恢复、跨系统恰好一次和不可篡改审计未实现。规则见 [Policy](../policy-engine/README.md)，完整步骤见 [示例](../examples/runtime-policy/README.md)。

设计入口：[Architecture](../ARCHITECTURE.md)、[Data Model](../docs/design/data-model.md)。

## 可选审批准备：SPEC-010

src/aegis_runtime/approvals.py 提供 ApprovalClient.prepare，宿主显式绑定 action/subject/tool/permission、Policy 快照与参数。参数仅在本地 HMAC，不上传原值；客户端仅访问回环 HTTP、显式 token/secret、有限超时、无自动重试/重定向。审批记录不调用工具，不改变 Runtime 决策。示例与状态/时效规则见 [审批接入](../docs/approvals.md)。完整暂停/恢复和执行领取未实现。

## 显式同步恢复：SPEC-011

可选aegis_runtime.reviewed_execution提供ReviewedClient/ReviewedTool/ExecutionResult。主动披露完整JSON参数后准备，人工核对/批准后宿主显式resume；签名补默认值，使用独立快照调用函数。原策略仍须allow，领取唯一且不释放，完成确认未知也不重复函数。成功返回原value对象与confirmed/unknown，业务异常身份保持。仅普通同步具名参数，旧Runtime.tool不变；配置/限制见 [执行审批](../docs/reviewed-execution.md)。

## 显式异步恢复：SPEC-012

可选模块aegis_runtime.async_reviewed_execution提供AsyncReviewedClient/AsyncReviewedTool；安装 `python -m pip install -e "./runtime[reviewed-async]"`（仓库根目录，先装本地SDK/Policy）。只接收普通async def具名JSON工具，原生HTTPX、单循环资源与取消传播；不创建后台补偿，不释放已领取动作。核心导入和同步入口不需要HTTPX。见 [异步接入](../docs/async-reviewed-execution.md) 与 [示例](../examples/async-reviewed-execution/README.md)。

## 单个LangGraph中断：SPEC-013

可选aegis_runtime.langgraph_reviewed提供ReviewedGraphTool/GraphExecutionResult/GraphBindingError。安装 `python -m pip install -e "./runtime[reviewed-langgraph]"`（仓库根目录、先装SDK/Policy）。纯gate.node与宿主驱动prepare/resume复用现有三角色协议；绑定最新checkpoint，节点重跑不执行工具。只支持同步单个根中断；同进程saver宿主对象重建已验收，持久跨进程恢复未验收。见 [接入](../docs/langgraph-reviewed.md)。

## 本机SQLite持久图：SPEC-014

可选aegis_runtime.durable_graph提供open_reviewed_checkpointer与CheckpointUnavailable；安装 `python -m pip install -e "./runtime[reviewed-langgraph-sqlite]"`（先装本地SDK/Policy）。只接受明确本机文件，新建独占、默认只重开；marker/版本/表列不匹配失败关闭，不自动迁移。使用官方SqliteSaver和严格serializer，原图继续sync写入。独立进程命令与退出后的未知边界见 [接入](../docs/durable-graph.md)。

## 原生异步审批图：SPEC-015

可选async_langgraph_reviewed.AsyncReviewedGraphTool与async_durable_graph.configure_async_reviewed_checkpointer；安装 `python -m pip install -e "./runtime[reviewed-langgraph-async]"`（先装本地SDK/Policy）。原生await图与工具，单循环/单根中断，宿主拥有SQLite连接和关闭责任。配置失败不复用；未知或取消不重试。详见 [接入](../docs/async-graph.md)。

接入前可用[策略工作台](../docs/policy-workbench.md)解释和验收Policy；[示例](../examples/policy-workbench/README.md)把同一批用例交给真实Runtime验证。报告和指纹不参与运行时授权，也不替代已有审批绑定；宿主仍显式传入不可变Policy与subject。

SPEC-045：Application v4 / PolicyTool支持策略驱动同步异步审批；显式票据恢复仍复用原永久claim。强制reviewed模式不因allow降级，详见[完整指南](../docs/policy-approval.md)。

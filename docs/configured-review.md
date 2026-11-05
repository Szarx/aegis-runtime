# 统一接入中的人工审核与单次恢复

SPEC-026把[Application统一接入](application-onboarding.md)和既有[同步](reviewed-execution.md)/[异步](async-reviewed-execution.md)执行审批整合成一个工作流：声明工具需要审核、准备请求、独立人工决定、宿主显式恢复一次、查询执行状态与治理事件。服务本身无需LLM，现有011/012协议、四迁移和Dashboard保持。

## 显式v2配置

```json
{
  "schema_version": "aegis.application.v2",
  "service_name": "reviewed-agent",
  "policy_file": "policy.json",
  "tools": [
    {"name":"write","permission":"records.write","execution":"reviewed","tool_revision":"write-v1"}
  ],
  "telemetry": {"mode":"jsonl","path":"traces.jsonl"}
}
```

v2工具必须提供四个字段；reviewed需要合法tool_revision，direct必须tool_revision=null。v1仍只接受name/permission，默认direct，原配置与报告形状保留；旧加载器拒绝v2。配置不存审批地址/角色凭证，由可信宿主显式构造客户端。Policy仍需allow，人工批准不能覆盖本地deny。

`app.tool`会拒绝reviewed项，`app.reviewed_tool`会拒绝direct、未知或已绑定项，避免在统一入口内降级绕过审核。原始未包装函数仍是宿主代码，Application不是Python沙箱或外部身份认证。

## 同步宿主

```python
from aegis_runtime.application import Application, load_application
from aegis_runtime.reviewed_execution import ReviewedClient

# endpoint、角色凭证和binding_key由可信宿主安全取得，不放进配置或报告。
client = ReviewedClient(endpoint, token=producer_token,
                        execution_token=executor_token, binding_key=binding_key)
with Application(load_application("aegis.json"), subject="demo-agent") as app:
    governed = app.reviewed_tool(write, client=client, disclose_arguments=True)
    ticket = governed.prepare({"record_id": 1}, summary="Review this synthetic write")
    # 返回ticket[action_id]并停止此动作，交给独立审核者；这里不执行write。
```

prepare会绑定签名/defaults后的完整JSON参数。**只有明确设置disclose_arguments=True才能绑定**，这些参数会存入审批服务并显示给审核者，不能把敏感数据披露当作默认行为。Trace和安全事件仍不采集这些参数。

返回的句柄不是可直接调用的工具函数，只提供prepare/resume。审核通过后，可在新进程用同一配置、函数实现/版本、subject、binding_key和相同参数/summary/ttl重新构造句柄，调用`governed.resume(action_id, arguments, summary=...)`。它返回原ExecutionResult(value, confirmation)，原工具返回对象留在宿主。

工具实现变更必须由宿主更新tool_revision；配置标签不能自动验证任意Python实现。该入口恢复的是工具动作，宿主拿到确认后安排后续Agent流程；不会自动恢复任意图状态、轮询审批或后台执行。单根LangGraph checkpoint可使用原ReviewedGraphTool，或使用新增[v3配置审批图](configured-graph.md)统一装配。

## 原生异步与资源所有权

安装现有reviewed-async extra后：

```python
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient

async with AsyncReviewedClient(endpoint, token=producer_token,
                               execution_token=executor_token,
                               binding_key=binding_key) as client:
    with Application(config, subject="demo-agent") as app:
        governed = app.reviewed_tool(async_write, name="write", client=client,
                                     disclose_arguments=True)
        ticket = await governed.prepare(arguments, summary=summary)
        # 在另一阶段/进程审批后，显式await governed.resume(...)
```

Application借用客户端，不构造、不关闭它；sync函数要求ReviewedClient，async函数要求AsyncReviewedClient。宿主必须在原事件循环中等待所有操作完成再关闭客户端。每次prepare/resume整体持有Application租约，覆盖网络、业务与确认，未结束时Application.close会拒绝关闭。async取消归还租约，但不能撤销服务已提交的claim，也不会释放或重试动作。

Application继续只管理自身SDK，关闭后句柄不可用；原v1普通工具路径不变。新inspection/status使用v2报告，显示execution、tool_revision、requires_review，Policy allow只代表本地策略通过；检查不验证审批客户端、角色、服务或当前批准状态。

## 运行分进程示例

在仓库根目录安装对应本地包：

```text
python -m pip install ./sdk/python ./policy-engine ./runtime
python -m pip install "./runtime[reviewed-async]"
python -m aegis_runtime inspect examples/configured-review/application.json --subject demo-agent
```

先按[部署说明](../deploy/docker/README.md)配置Collector独立的producer/reviewer/executor角色，三种凭证及Trace token彼此独立。Agent宿主只在本机环境提供AEGIS_APPROVAL_REQUEST_TOKEN、AEGIS_APPROVAL_EXECUTION_TOKEN和至少32字节hex的AEGIS_APPROVAL_BINDING_KEY；不需要reviewer凭证。请勿提交或把真实凭证发到聊天。

```text
python examples/configured-review/agent.py prepare --endpoint http://127.0.0.1:8000
```

示例输出action_id、pending、available，此时业务计数为0。打开既有Dashboard“执行审批”，用独立reviewer凭证核对工具版本、完整JSON和摘要再批准或拒绝；页面不执行工具。批准后在新宿主进程执行：

```text
python examples/configured-review/agent.py resume --endpoint http://127.0.0.1:8000 --action-id YOUR_ACTION_ID
```

两条都加--async可运行异步；prepare和resume的--scenario、--value等必须相同。默认参数仅合成数据，含9223372036854775807，用于验证无损审阅。业务只向artifacts/configured-review/business-calls.jsonl追加一行计数，成功进入一次；重复恢复不会再追加。--calls可改为独立文件。

| 示例退出码 | 含义 |
| --- | --- |
| 0 | 准备成功，或恢复得到confirmed |
| 1 | 未完成：未批准、拒绝、过期、绑定不符、重复领取或配置/服务不可用等；不自动重试 |
| 2 | 合成业务失败，可能已有部分副作用，动作已消费 |
| 3 | --async --scenario cancel在业务进入后取消，可能已有副作用，保持claimed未知 |
| 4 | confirmation=unknown，工具可能执行且服务可能已确认；需人工核对，不能重跑 |

--scenario failure可验证失败，cancel仅用于async。示例不自动批准，不打印完整参数/返回值/凭证，不把unknown当作已确认成功。它不提供端到端恰好一次或跨业务系统事务。

## 查询与信任边界

准备/拒绝/未批准状态在执行审批记录中查看，不假装为工具执行。成功进入工具的resume会产生带原action_id的治理Span，可在安全事件中心按action_id关联真实恢复Trace；既有审批记录的trace_id/span_id可能为null，不新增虚构链路绑定。Agent入口可通过app.agent显式追踪。

领取永久消费，未知、部分失败和取消不释放；参数、策略摘要、工具版本、subject或绑定key变化都不能沿用旧批准。完整参数只在明确披露的审批服务保存，遥测白名单不接收；审核/执行角色和配置本身仍需可信宿主维护。

真实HTTP/PG与独立进程已验收批准/拒绝/未批准、参数及版本变更、过期、重复、失败、取消、确认提交后回执丢失，以及治理导出/离线回放。范围和证据见[SPEC-026任务](../specs/026-configured-review/tasks.md)，人工操作耗时与新UI验收不在本轮声明中。

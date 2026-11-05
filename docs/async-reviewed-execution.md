# 异步工具执行审批

SPEC-012复用 [执行审批](reviewed-execution.md) 的完整参数审阅、独立角色、工具版本、唯一领取及结果确认协议。仅增加Python3.11+ / asyncio入口；Collector仍无LLM依赖，OpenAPI、迁移{1,2,3,4}和Dashboard不变。

## 安装与接入

先安装本地SDK和Policy；从仓库根目录安装可选extra：

```text
python -m pip install -e ./sdk/python -e ./policy-engine -e "./runtime[reviewed-async]"
```

extra要求httpx==0.28.1。核心Runtime和同步ReviewedTool不导入或要求HTTPX；异步客户端缺依赖时给出固定安装提示。客户端只访问显式回环HTTP origin，要求独立producer/executor凭证与至少32字节binding_key；凭证不来自工具参数或模型。

```python
from aegis_runtime.async_reviewed_execution import AsyncReviewedClient, AsyncReviewedTool

async def write_record(*, record_id, value):
    return await existing_async_write(record_id, value)

async with AsyncReviewedClient(endpoint, token=producer_token,
                               execution_token=executor_token,
                               binding_key=local_key) as client:
    tool = AsyncReviewedTool(write_record, client=client, policy=policy,
                             subject="order-agent", permission="records.write",
                             tool="write_record", tool_revision="async-write-v1",
                             disclose_arguments=True)
    ticket = await tool.prepare({"record_id": 1, "value": "synthetic"},
                                summary="合成写入", ttl_seconds=300)
    # 保存action_id；在独立审核界面完成核对和批准，稍后由宿主显式恢复。
    # result = await tool.resume(ticket["action_id"], same_arguments,
    #                            summary="合成写入", ttl_seconds=300)
```

上例是接入片段；完整跨进程prepare/resume见 [合成Agent](../examples/async-reviewed-execution/README.md)。实际参数、summary、TTL、身份、权限、Policy、binding_key和tool_revision必须保持一致。只支持普通async def具名JSON参数，签名补默认值；拒绝同步函数、生成器、位置专用参数与可变参数。完整参数需主动披露给Collector/审核人，不要放secret。异步实现变更或由同步改为异步时，宿主须升版tool_revision。

## 取消和结果

| 取消发生时 | 工具调用 | 服务可能状态 |
| --- | --- | --- |
| 尚未await / 请求发送前 | 0次 | 未改变 |
| prepare请求中 | 0次 | 可能已pending |
| claim请求中或领取后、函数前 | 0次 | 可能已claimed |
| 函数执行中 | 开始1次，可能已有副作用 | claimed，保留未知 |
| complete确认中 | 已调用1次 | claimed或已经completed/failed |

原CancelledError传播；取消不是回滚，也不是“工具未执行”的证明。任何已领取动作都不重新开放；宿主另行查询状态，不能因取消、unknown或业务异常自动resume。库不shield业务、不创建后台补偿任务、不重试网络或工具。

成功时返回ExecutionResult，value为原对象，confirmation为confirmed或unknown；普通确认故障不丢失成功value。普通业务异常保持原对象并尝试一次failed确认；若此时发生任务取消，取消继续传播。参数/业务异常正文不进入SDK治理遥测。保留原有Agent上下文与Tool Span；遥测不是持久事务审计。

## 客户端生命周期

用async with或await client.aclose()，一个实例只能用于同一个事件循环。宿主先取消并等待自己拥有的业务操作结束，再关闭客户端；客户端不取消其他业务任务。不要依赖工具内部吞掉取消或自行创建任务时的副作用控制。

原生HTTPX，禁环境代理、重定向与自动重试，最多4条连接。单个操作总期限含池等待与整个响应流，最大5秒；响应64KiB上限并严格校验编码、JSON和绑定。aclose开始后拒绝新请求，成功后重复关闭幂等；关闭被取消或超时可能尚未释放全部连接，需在原循环显式再次aclose清理。关闭错误保留已有业务异常，新的关闭取消仍传播。

验收边界见 [012任务](../specs/012-async-reviewed-execution/tasks.md) 与 [ADR-0006](adr/0006-async-reviewed-execution.md)。LangGraph interrupt/checkpoint恢复、require_approval策略分支和外部业务系统恰好一次执行仍需独立设计。

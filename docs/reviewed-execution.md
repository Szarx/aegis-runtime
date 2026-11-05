# 显式同步工具的执行审批

SPEC-011 提供“完整参数审阅 → 人工决定 → 宿主显式恢复 → 单次领取 → 结果确认”。Aegis 无需 LLM；Collector 不运行函数，副作用发生在 Agent 宿主进程。旧 [审批准备](approvals.md) 仍不执行，旧记录不能升级为执行凭据。

## 配置与披露

先配置原 producer/reviewer 凭证，再显式增加 AEGIS_APPROVAL_EXECUTION_TOKEN，必须与前两种及 AEGIS_API_TOKEN 不同。未设置时新协议503，旧准备协议仍可用；错误/复用凭证拒绝启动。AEGIS_APPROVAL_EXECUTOR 默认 local-executor，审核/执行身份由服务端配置，不能由请求覆盖。这是本地固定角色，不是多用户认证或多租户。

```powershell
$env:AEGIS_APPROVAL_EXECUTION_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
docker compose up -d --build --wait
```

宿主还需显式 producer token 与至少32字节 binding_key，均由本机配置提供。reviewer token 只给审核界面，execution token 不进入浏览器。客户端仅支持回环HTTP、无代理/重定向、超时≤5秒且无自动重试。

**本路径会将完整工具参数（含默认值）发给本机 Collector，并存入数据库供审核人查看。** 必须显式选择 disclose_arguments=True；禁止放入模型密钥、访问凭证等secret。默认观测与旧010仍不采集原参数。新审阅参数不进入Span/JSONL，服务不保存业务返回值或异常正文。

## 宿主接入

```python
from aegis_policy import Policy, Rule
from aegis_runtime.reviewed_execution import ReviewedClient, ReviewedTool

client = ReviewedClient(
    "http://127.0.0.1:8000", token=producer_token,
    execution_token=executor_token, binding_key=host_binding_key,
)
policy = Policy("orders-v1", (
    Rule("permit", "allow", ("order-agent",), ("update_order",), ("orders.write",)),
))

def update_order(*, order_id, status="reviewed"):
    return existing_order_store.update(order_id, status)

governed = ReviewedTool(
    update_order, client=client, policy=policy, subject="order-agent",
    permission="orders.write", tool="update_order", tool_revision="impl-v1",
    disclose_arguments=True,
)
arguments = {"order_id": "synthetic-001"}
ticket = governed.prepare(arguments, summary="更新合成测试订单")
# 人工在“执行审批”页面核对完整参数、工具版本并批准后：
result = governed.resume(ticket["action_id"], arguments, summary="更新合成测试订单")
business_result = result.value
confirmation = result.confirmation  # confirmed 或 unknown
```

准备与恢复都要求当前本地策略明确allow，默认拒绝/显式deny不被人工批准覆盖。身份、策略快照、工具/权限、显式工具版本、参数HMAC/审阅摘要、summary和TTL不匹配无法领取。实现/语义变化必须由宿主提高tool_revision；不是自动源码校验或进程隔离。

只支持普通同步函数与具名参数；拒绝协程、生成器、位置专用和 *args/**kwargs。按签名补齐默认值，再用独立JSON快照调用工具，原容器之后的修改不影响已领取实参。参数接受010的严格JSON类型，完整规范UTF-8 JSON最多4096字节；不支持float/自定义对象。日期、金额等由宿主明确使用字符串/整数表达。页面用无损整数解析，保留64位整数和值类型。

默认TTL300秒，30–600秒，恢复必须使用同一TTL。action_id默认新UUID；同内容显式prepare重试不续期，新旧协议不能复用ID。宿主服务重启后重新构建相同Policy/工具版本和密钥、传入同参数与ID，可以尝试恢复尚未领取的批准；已领取动作不能恢复。

## 单次领取与结果未知

| 情况 | 工具 | 服务状态/行为 |
| --- | --- | --- |
| 待审核、拒绝、过期、本地deny、绑定变化 | 零次 | 拒绝领取或在本地阻止 |
| 并发恢复同一动作 | 最多一个调用者能开始 | 行锁保证只有一个available→claimed |
| 领取响应丢失/不符/超时 | 当前宿主零次 | 可能已经claimed；不重试、不释放 |
| 领取后进程退出 | 是否开始/完成未知 | 永久claimed，页面标“已领取·结果未知” |
| 工具成功，确认成功 | 一次 | completed，返回原对象与confirmed |
| 工具成功，确认失败 | 一次 | 状态可能claimed或completed，返回原对象与unknown |
| 工具抛异常 | 一次，可能已有部分副作用 | 原异常传播，尝试一次failed确认，不能重试业务 |

领取在数据库事务中检查批准/时效/绑定并消费。客户端扣除整个请求耗时，保守检查剩余有效期；进入工具前再次检查策略和本机单调时钟。领取后不会延长审批有效期；允许过期后确认已领取动作的结果。

没有租约、自动释放、重开或“重新执行”按钮。unknown不是可重试错误，也不是业务未执行的证明。已知结果的相同complete请求可幂等确认，保留首次时间；相反结果冲突，但宿主SDK只尝试一次确认。不能通过再次resume来补确认。外部系统与数据库间没有原子事务，本实现不承诺跨系统恰好一次或进程暂停后的实时执行保证。

## API、页面与升级

| API | 角色 | 用途 |
| --- | --- | --- |
| POST /api/v1/reviewed-actions | producer | 创建完整参数审批 |
| GET 同路径 | reviewer | 独立列表，limit1–100/offset0–10000 |
| POST /{action_id}/decision | reviewer | decision与已展示review_digest |
| POST /{action_id}/claim | executor | 全部绑定与新claim_id；任何重复领取409 |
| POST /{action_id}/complete | executor | claim_id与outcome completed/failed |

请求严格未知字段/类型，最大16KiB，响应no-store；错误不回显载荷。服务只存储/协调，以上路径都不接收callable或任意代码。完整字段见 [011 OpenAPI](../specs/011-reviewed-execution/contracts/openapi.json)。

Dashboard 的“执行审批”与“审批准备”使用独立组件会话；切换类型、断开或整页重载清除reviewer token。查询刷新保留当前内存凭证，但清除展开项和参数确认。核对完整参数与工具版本后才可批准/拒绝，提交摘要对应当前记录。页面只记录决定，宿主另行恢复；显示审核与执行身份、领取/确认时间，不含执行凭证或执行按钮。写结果未知须先手动刷新。

本页可搜索/筛选并按原始顺序、待审核优先或到期升序查看；不跨页收集。改变视图清除参数确认，需要重新展开核对。日期完整显示且查询时间标明快照，未自动同步到期状态；有效性由服务端判断。Action ID支持显式复制，参数HMAC/策略摘要在绑定信息中展开。操作/验收见[工作台指南](dashboard-design.md)及[038](../specs/038-review-reading/tasks.md)。

迁移4新增reviewed_actions关联表，旧Span/准备记录保留；当前readiness要求{1,2,3,4}。旧列表/决定与新记录隔离，旧010响应不扩展。升级需配套Collector/Runtime/Dashboard，不支持自动降级。见 [合成示例](../examples/reviewed-execution/README.md) 与 [验收](../specs/011-reviewed-execution/tasks.md)。

011初版限定同步工具；后续[异步工具](async-reviewed-execution.md)、[审批图](langgraph-reviewed.md)、[异步持久图](async-graph.md)和[配置接入](configured-review.md)已有各自验收。Policy DSL中的require_approval分支、自动重试与生产身份体系仍未交付。这里通过显式ReviewedTool为本地allow添加人工审批条件，旧Runtime.tool仍只执行原有allow/deny。

# 审批准备与人工决定

SPEC-010 提供持久化审批请求、人工批准/拒绝和查询。**批准记录不执行工具，也不改变现有 Runtime allow/deny**。旧准备接口不提供require_approval、单次领取或执行；新的显式同步恢复见 [执行审批](reviewed-execution.md)，异步/图恢复仍待实现；不要把数据库里的 approved 当作调用业务函数的凭证。

## 启用本地服务

默认关闭审批。Collector 必须同时配置独立的 producer / reviewer token，两者互异，且不能等于 AEGIS_API_TOKEN。只配置一种或使用相同凭证会拒绝启动。AEGIS_APPROVAL_REVIEWER 为服务端审核身份，默认 local-reviewer；API 不接受调用者覆盖身份。此身份是本地固定角色，不是多用户认证或租户系统。

PowerShell 中生成临时开发凭证，保留在当前进程；不要将输出或本机 secret 提交到仓库：

```powershell
$env:AEGIS_APPROVAL_REQUEST_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$env:AEGIS_APPROVAL_REVIEW_TOKEN = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
$env:AEGIS_APPROVAL_BINDING_KEY = [Convert]::ToHexString([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
docker compose up -d --build --wait
```

绑定密钥由 Agent 宿主管理，不传给 Collector / Dashboard。变更该密钥会改变参数绑定；重试同一动作必须使用原密钥和原请求。HTTP 客户端仅支持本机回环 HTTP，服务端端口应继续绑定本机；此增量没有远程传输或生产部署验收。

## 宿主准备请求

安装本地 SDK、Policy、Runtime 包后，业务宿主显式提供受信任身份、策略快照与动作说明：

```python
import os
import uuid
from aegis_policy import Policy
from aegis_runtime.approvals import ApprovalClient

client = ApprovalClient(
    "http://127.0.0.1:8000",
    token=os.environ["AEGIS_APPROVAL_REQUEST_TOKEN"],
    binding_key=bytes.fromhex(os.environ["AEGIS_APPROVAL_BINDING_KEY"]),
)
ticket = client.prepare(
    action_id=uuid.uuid4().hex,
    subject="demo-agent", tool="update_demo_record", permission="demo.write",
    policy=Policy("demo-v1", ()),
    arguments={"record": "synthetic-001", "value": 1},
    summary="合成演示：申请修改测试记录（只记录审批，不执行）",
)
```

该函数不接收业务 callable，不会执行工具。arguments 只在本地规范化并计算 HMAC-SHA256；网络只含摘要、身份/工具/权限、策略 revision/digest、说明和可选 Trace / Span。不要自行把原参数或其他 secret 放进 summary。HMAC 不提供可读的参数预览，summary 也不是未来真实动作授权所需的完整审阅上下文。

arguments 接受精确 JSON 类型：null、bool、有符号64位整数、字符串、list、字符串键 dict。禁止 float、自定义类型、tuple、循环，深度≤16，单容器≤128项、字符串≤2048字符、规范 UTF-8 JSON≤16KiB。规范排序字典键，保留列表顺序和值类型。策略快照包括版本和规则顺序，保守绑定所有变化。

TTL 默认300秒，严格整数30–600秒。服务端设置创建/到期时间；相同 action_id 和完全相同绑定幂等返回原记录，不延长时间；任何绑定变化返回409。新动作生成新 ID；网络结果未知时调用者可显式重试原动作。客户端超时≤5秒、禁用代理/重定向、无自动重试、验证≤64KiB响应及回传绑定，失败为固定 ApprovalUnavailable。

## 审核和状态

打开 Dashboard 的“审批准备”，提供 reviewer token，查看动作说明、主体、工具/权限、摘要、有效期及关联 Trace。点击“记录批准”或“记录拒绝”只保存决定。Trace 凭证与 reviewer 凭证独立；切换离开审批页、断开或刷新页面后需重新提供 reviewer token。凭证不写入浏览器持久存储或 URL。

请求为 pending，未过期时可记录 approved/rejected。数据库行锁保证并发相反决定仅一个胜出；相同决定的有效期内重试保留原时间/审核人，反向或到期决定返回409。pending/approved 到期查询为 expired；rejected 保留拒绝。没有重开、续期、删除或执行接口。

页面不自动轮询或重试。决定结果未知会清空列表，必须先手动刷新确认再继续，避免陈旧状态驱动下一次写入。是否过期由数据库时钟最终判定，不能依赖浏览器时钟。

| API | 凭证 | 请求 |
| --- | --- | --- |
| POST /api/v1/approvals | producer | 严格审批绑定对象，最大16KiB |
| GET /api/v1/approvals | reviewer | limit 1–100、offset 0–10000 |
| POST /api/v1/approvals/{action_id}/decision | reviewer | 仅 decision=approved 或 rejected |

未知字段、重复 JSON 键、错误类型和不成对 Trace / Span 都拒绝。接口返回固定错误；服务未启用为503，凭证错误401，绑定/决定冲突409。完整 schema 见 [OpenAPI](../specs/010-approval-records/contracts/openapi.json)，边界与验收见 [SPEC-010](../specs/010-approval-records/spec.md)。

## 数据与后续

迁移3增加 approvals，保留原生、LLM、图流和治理 Span；最新服务 readiness 要求迁移集合 {1,2,3,4}（迁移4为独立执行协议）。迁移有事务/advisory lock，重复或并发升级安全，未来未知版本拒绝；不提供自动降级。审批数据保存于同一 PostgreSQL 卷，容器重建不清除记录。

SPEC-011另行定义了完整参数、同步单次领取和未知结果处理；旧010记录不可升级，需主动选择新协议。本轮不是不可篡改审计、跨系统恰好一次执行或生产交易授权。无模型调用的完整例子见 [prepare.py](../examples/approval-records/README.md)。

# SPEC-011：可审阅参数与单次受约束恢复

日期：2026-10-20。本增量提供显式同步 ReviewedTool 的准备/恢复，以及服务端单次领取与结果确认。Aegis 无需 LLM；不自动恢复图、不执行任意远程代码，不增加业务重试。旧 Runtime.tool / allow-deny 和 SPEC-010 哈希准备接口保持原行为。

## 信任、参数与版本

新 ReviewedTool(function, *, client, policy, subject, permission, tool, tool_revision, disclose_arguments=True) 是显式可信宿主入口。必须显式选择 disclose_arguments=True，其他值拒绝构造。只接受普通同步函数，拒绝协程/生成器。prepare(arguments:dict, summary, action_id可选, ttl_seconds=300) 与 resume(action_id, arguments, summary, ttl_seconds=300) 显式调用，不轮询/重试；summary/TTL 同样属于恢复绑定。

仅支持具名参数：对签名 bind(**arguments)、apply_defaults，再规范化为独立 JSON 快照；拒绝 *args/**kwargs 及位置专用参数、不合法/非JSON默认值。参数复用010的精确JSON限制，并收紧规范UTF-8 JSON总量至4096字节以供完整审阅。实际调用使用同一独立快照的全部 kwargs，宿主修改原容器不能改变已领取参数。prepare和resume均要求本地Policy明确allow；拒绝、策略故障或身份/权限缺失不发领取请求、不执行函数。批准是额外条件，不能覆盖本地deny。

新执行协议显式保存完整 review_arguments（参数快照，含默认值）和 review_digest=SHA256(规范JSON)，同时保留 HMAC；它们不进入Span/JSONL。此路径明确披露参数给本机Collector/数据库和审核人，宿主不得传入secret；旧010路径仍只发送HMAC。tool_revision为宿主显式版本，工具实现/语义变化必须升版本；策略快照、身份、工具/权限、工具版本、全部参数、摘要和TTL均绑定。宿主/原函数/数据库管理员仍可信；不防同进程恶意绕过。

## 服务端与协议隔离

新 /api/v1/reviewed-actions：POST producer创建，GET reviewer分页；POST /{action_id}/decision reviewer，仅 decision和review_digest；POST /{action_id}/claim executor；POST /{action_id}/complete executor。Collector只记录/领取/确认，不持有或调用业务函数；执行发生于Agent进程。

新增独立 AEGIS_APPROVAL_EXECUTION_TOKEN，显式配置才启用新协议，必须与producer/reviewer/Trace凭证互异且原审批两种凭证已配置；AEGIS_APPROVAL_EXECUTOR默认local-executor，服务端绑定身份。未配置执行凭证时新路径503；旧010仍可独立启用。不增加默认执行凭证。请求仍严格未知字段/16KiB上限、固定错误、无cookie/CORS授权。

迁移4增加 reviewed_actions 关联 approvals，每条有 tool_revision、review_arguments/digest、execution_state、claim_id、executor、claimed_at、finished_at。旧010记录绝不可领取或原地升级。旧列表只显示旧记录，旧创建/决定不得读写新协议记录；新列表只显示新记录，协议互撞返回409/404。不扩展旧010响应字段；011另存OpenAPI。

## 状态与时序

审批状态沿用pending/approved/rejected/expired，执行状态独立available/claimed/completed/failed。claimed表示已不可再次领取、工具可能尚未开始或结果未知；没有自动释放、租约、重开或再执行。完成确认失败仍保持claimed，不推断失败/成功。

create在单一事务内创建审批+执行记录，相同动作完全同绑定幂等且不续期。reviewer提交review_digest必须等于已展示的完整参数摘要；不同摘要拒绝。claim请求包含subject/tool/permission/policy revision/digest/arguments_hmac/tool_revision/review_digest/summary/ttl和客户端新随机claim_id（32非零hex）；同事务锁审批/执行行、检查绑定、approved、未到期及available，写claimed/服务端身份/时间。每个action恰有一个领取成功，任何重复（包括相同claim_id）409；丢失响应不能重试领取来运行工具。

客户端必须验证领取响应完整绑定、claim_id和claimed状态，并在本地单调时钟的保守剩余有效期内开始函数（服务返回剩余毫秒，客户端扣去整个请求往返耗时）；剩余不足则不执行、票据保持claimed未知。策略在准备、领取前和函数前再次求值且快照必须一致。进程暂停/远端时钟变化不构成跨系统实时/恰好一次保证；函数开始后的超时不撤销副作用。

函数只调用一次；成功返回 ExecutionResult(value, confirmation:confirmed|unknown)，其中value保持原对象。业务异常原样传播，尝试一次failed确认；异常正文/返回值不上传。complete只接受claim_id和outcome completed/failed，匹配已领取记录，首次写固定完成时间；同结果重试幂等保留时间，相反结果409。允许过期后确认已领取的结果，不允许过期后首次领取。业务失败可能已有部分副作用，failed也绝不能重新执行。

客户端沿用回环HTTP、无代理/重定向、超时≤5秒、有界响应和固定错误，网络绝不自动重试。领取未知/不符/超时不执行；结果确认未知不重复函数。显式同步首版不支持async或LangGraph interrupt恢复，后续单独spec。

## 页面与验收

新增“执行审批”独立页面/内存reviewer会话，显示完整格式化参数、tool_revision、摘要、审批和执行状态、时间/审核与执行身份、关联Trace。批准文案说明宿主之后可显式恢复一次，页面不调用工具；claimed清晰显示“已领取·结果未知”，不提供重试/释放按钮。无执行凭证进入浏览器；旧“审批准备”文案/能力保持。

| AC | 验证 |
| --- | --- |
| 1101 | 显式披露、签名/默认值/JSON边界、参数快照、身份/策略/工具版本变化不得恢复 |
| 1102 | 新旧协议隔离，三角色/Trace权限，默认关闭/配置错误、严格字段/摘要和体限制 |
| 1103 | 真实PG schema3→4保留旧数据；并发领取仅一个；过期/重复/错绑定/错claim失败，确认幂等和未知不重开 |
| 1104 | 实际HTTP+ReviewedTool同步成功一次、异常一次、拒绝零次；领取响应丢失/篡改/超时/确认失败不重复；旧控制回归 |
| 1105 | 浏览器完整参数/批准/拒绝/claimed未知/结果、独立凭证/旧页面、无执行API按钮 |
| 1106 | wheel/迁移、构建、OpenAPI、文档/证据，无真实模型或真实业务系统请求 |

# SPEC-012：异步工具的审批恢复与取消

日期：2026-10-20。新增显式AsyncReviewedClient/AsyncReviewedTool，复用011 reviewed-actions协议与迁移{1,2,3,4}，不改服务端状态、OpenAPI或Dashboard。旧同步ReviewedTool与010准备接口保持。异步入口仍无需LLM，不实现LangGraph checkpoint/interrupt恢复或Policy DSL require_approval。

## 接入与资源

新可选模块aegis_runtime.async_reviewed_execution。仅普通async def具名JSON工具，拒绝同步函数、生成器、位置专用与*args/**kwargs；参数/默认值/完整披露、HMAC/审阅摘要、身份/权限/策略/版本/summary/TTL绑定均复用011。宿主必须使用对应异步实现的显式tool_revision（实现/同步异步语义变化须升版），协议不自动推断函数实现。

AsyncReviewedClient需要可选extra reviewed-async=httpx==0.28.1（已有59-pin开发基线，不新增第三方版本）。核心导入及同步API不导入/要求HTTPX；构造异步客户端时缺依赖报固定安装提示。支持asyncio/Python3.11+，实例仅用于一个事件循环，使用async with或显式await aclose释放自身连接；不接管业务函数创建的任务。

使用原生HTTPX AsyncClient，不把同步urllib移入线程；显式回环HTTP、独立凭证、trust_env=False、不跟随重定向/不重试，最多4条连接。每次网络操作有整个请求（含连接池等待/响应流）的总期限≤5秒，同时设置网络阶段超时；响应≤64KiB，编码/重复键/绑定/状态校验失败固定ApprovalUnavailable。连接/响应通过异步上下文关闭；不创建后台补偿、守护线程或自动重领任务。aclose禁止新请求，重复关闭幂等；关闭错误不覆盖已有业务异常，关闭期间的新取消继续传播；关闭取消/超时不承诺已经释放所有连接，可在同一循环再次aclose补做资源清理，但禁止再发请求。

## 异步与取消边界

prepare/resume均为惰性协程，未await不发请求、不执行工具。方法开始、领取后、进入工具前设置可取消检查点；本地策略与保守单调时效在函数前再次检查。原生await保留当前Agent上下文，并发任务不共享Span或参数快照。

| 取消位置 | 工具 | 确认与服务状态 |
| --- | --- | --- |
| 开始/发送前 | 零次 | 不发请求，不消费动作 |
| prepare请求中 | 零次 | 服务可能已有pending；不自动重建/重试 |
| 领取请求中或领取后、函数前 | 零次 | 可能或确定claimed，保守保持未知，不发complete/释放 |
| 函数执行中 | 已开始一次，可能有部分副作用 | 不发failed确认，保持claimed未知；传播原CancelledError |
| 成功/业务异常后的结果确认中 | 已调用一次 | 服务可能完成确认，也可能claimed未知；传播取消，不再执行 |

CancelledError不转换为ApprovalUnavailable，不吞掉或将取消伪装成业务失败。普通业务异常保持原对象，尝试一次failed确认；若确认期间发生新的任务取消，以该取消为准，原异常仍作为异常上下文。普通确认故障保留原业务异常；成功结果确认故障返回ExecutionResult原value和unknown。取消不是回滚或工具未执行证明。

不shield业务、领取或结果确认，不在调用者取消后继续补偿业务。取消网络不能撤销服务端已提交的事务；同action并发领取仍由既有数据库行锁控制，最多一个调用者开始。已领取/失败/完成均不重开。取消前确实尚未发出的动作仍available，但宿主不能根据取消异常推断服务状态或自动resume；需要另行查询。

aclose在宿主完成/取消并等待自身操作后调用，客户端不关闭共享事件循环、不取消其他业务任务。重复取消遵循asyncio语义，不承诺工具内部自行吞掉取消/创建后台任务时的外部副作用控制。进程退出与未知结果继续沿用011的保守失败边界。

## 验收

| AC | 验证 |
| --- | --- |
| 1201 | async专用/惰性、显式披露与签名/快照/策略/时效；旧同步拒绝async不变 |
| 1202 | 原生HTTPX有界流、总期限、禁代理/重定向/重试、固定错误与回传绑定；连接关闭/缺依赖/核心可选导入 |
| 1203 | 发送前、prepare/claim中、claim后、函数中和complete中取消，原取消/业务异常身份，零/单次执行、未知不重试 |
| 1204 | 并发和Agent/Tool上下文隔离，参数/异常正文不进入遥测，无遗留业务/网络补偿任务 |
| 1205 | 实际HTTP+真实PG：async成功/错误/取消/并发领取、持久claimed未知与重复恢复拒绝；原能力兼容 |
| 1206 | 可选extra/wheel/隔离安装、OpenAPI和SQL不变、文档/官方来源与证据同步，无真实模型请求 |

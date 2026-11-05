# SPEC-015：单个异步审批图与本机checkpoint

日期：2026-10-22。新增AsyncReviewedGraphTool，以普通async def工具、aget_state/ainvoke支持单个根interrupt。复用013逻辑action/精确snapshot/HMAC收据、012取消、014文件格式1；协议/四迁移/Dashboard不变，62第三方pin不变，无模型调用。不支持多机、同thread并发编辑、子图/多interrupt或自动重建completed收据。

## 接入

可选aegis_runtime.async_langgraph_reviewed.AsyncReviewedGraphTool，与同步图配置相同，客户端必须是AsyncReviewedClient，仅接收普通async def具名JSON参数。构造不做网络；node是async函数，只校验请求、interrupt和核对收据，不执行审批网络或业务。prepare/resume为惰性协程，开始检查点后绑定单事件循环；原参数/版本/身份/策略/TTL/summary检查不变。

公共纯snapshot校验由013抽出复用，异步入口只await graph.aget_state，不调用同步get_state或把业务放进线程。领取后的最终snapshot读取发生在业务函数前，读取/检查点结束后再次核对单调deadline；原函数在调用者任务内await，保留Agent上下文。确认成功且后验snapshot一致才await graph.ainvoke(Command(...),durability="sync")。结果GraphExecutionResult语义同013；普通图继续异常为unknown，新取消继续传播。

## 本机存储与所有权

新增configure_async_reviewed_checkpointer(connection,timeout=3)，宿主先用014工厂在启动阶段初始化或校验已有文件，再以aiosqlite mode=rw连接并async with管理其生命周期。配置函数仅接收已连接且无事务的官方aiosqlite.Connection，要求真实本机单main库/WAL，核对格式1 marker/框架版本/官方表列，设FULL和有界busy timeout，返回严格serializer、已setup的官方AsyncSqliteSaver。不新建文件、不自动setup/迁移，不关闭借入连接。

配置整个await有0<timeout<=5秒期限；CancelledError原样传播，其他存储错误固定CheckpointUnavailable。aiosqlite自身有宿主拥有的工作线程，取消await不能撤销已排队SQL。配置失败/取消后宿主关闭连接并等待队列排空，不继续复用；正常业务取消后宿主先等待任务结束，再关闭saver连接/HTTP客户端。重复取消导致关闭中断时，宿主仍负责在循环关闭前完成清理，不承诺强制终止原生SQL或工具自己创建的任务。

一个新extra reviewed-langgraph-async固定现有HTTPX/LangGraph/checkpoint/SQLite/aiosqlite/sqlite-vec版本，方便一次安装；核心和新模块导入不要求可选依赖。同步和异步宿主可顺序读取相同格式，但本次异步工具必须使用对应tool_revision；切换实现不能借原批准执行，也不能换call/key/id重试未知结果。

## 取消

| 阶段 | 业务函数 | 服务/图状态与后续 |
| --- | --- | --- |
| 未await/发送前/初始snapshot读取 | 0 | 不领取；可能仅读取本机状态 |
| prepare请求中 | 0 | 可能已pending，不自动重建 |
| claim请求中/已领取后snapshot中 | 0 | 可能claimed，永久消费，不complete/释放 |
| 函数中 | 已开始1次，可能部分副作用 | 传播原取消，不failed确认/继续图 |
| 成功/异常结果确认中 | 已开始1次 | 可能已completed/failed或未知，传播取消 |
| 确认后snapshot/图继续中 | 已完成1次 | 图可能暂停或写入完成，不重跑工具/自动继续 |

无shield业务/网络/图、无库创建的后台补偿任务。原业务异常对象保持，确认错误不掩盖；取消优先。返回成功但确认故障仍保留原value/unknown，不调用图；后验变更blocked。遥测不新增state/config/ticket/正文，图/审核存储仍是宿主主动披露的完整JSON参数。

## 验收

| AC | 验证 |
| --- | --- |
| 1501 | async专用/惰性、原绑定/严格JSON/单root范围、同步入口不变，真实异步图只用aget_state/ainvoke |
| 1502 | 取消在claim/snapshot/函数/确认/图继续阶段，原对象、0/1次执行、未知不重试，慢snapshot不能延长deadline |
| 1503 | SQLite配置/格式互读、借入连接不关闭、失败/取消后宿主关闭线程，配置总期限/严格serde/核心隔离 |
| 1504 | 真实HTTP/PG与官方异步SQLite，新宿主/进程读取已保存checkpoint，成功/取消/部分失败后不可重复，Agent上下文/隐私 |
| 1505 | wheel/extra、62-pin/两平台来源、协议/四迁移及受影响回归，示例/文档/机器证据，无LLM |

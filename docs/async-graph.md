# 异步审批图与本机 SQLite

[SPEC-015](../specs/015-async-graph/spec.md) 接收普通 `async def` 具名 JSON 工具，采用原生 `aget_state` / `ainvoke`。单个根 interrupt、稳定逻辑 call、精确 checkpoint 绑定和完整参数披露与 [同步图](langgraph-reviewed.md) 相同。Aegis 服务、示例和验证无需 LLM。

先安装本地 SDK / Policy，然后安装 `python -m pip install -e "./runtime[reviewed-langgraph-async]"`。可选依赖仍使用开发锁中的既有版本；核心 import 不加载 HTTPX、LangGraph 或 aiosqlite。

## 宿主接入

```python
import asyncio
from pathlib import Path
import aiosqlite
from aegis_runtime.durable_graph import open_reviewed_checkpointer
from aegis_runtime.async_durable_graph import configure_async_reviewed_checkpointer

path = Path("checkpoint.sqlite3").absolute()
# 启动阶段：首次显式 create=True；已有文件使用默认 create=False。
with open_reviewed_checkpointer(path, create=True):
    pass

async def host():
    async with aiosqlite.connect(path.as_uri() + "?mode=rw", uri=True) as connection:
        saver = await configure_async_reviewed_checkpointer(connection)
        # 用 saver 编译图；在此作用域 await 完所有图/工具任务。
        # async with AsyncReviewedClient(...) as client:
        #     gate = AsyncReviewedGraphTool(async_tool, client=client, ...)
        #     await graph.ainvoke(initial, config, durability="sync")
        #     ticket = await gate.prepare(graph, config, summary="完整参数审阅")
        # 审核人在独立会话批准后，由可信宿主显式调用：
        #     result = await gate.resume(graph, config, ticket)

asyncio.run(host())
```

完整可运行代码见 [示例](../examples/async-durable-graph/agent.py)。graph/node/tool 的身份、版本和策略均由可信宿主提供。异步实现使用独立 tool_revision；升级实现后不能借旧批准执行。每个 thread 必须由宿主串行管理，不支持子图、多中断或同时编辑 checkpoint。

## 连接生命周期

同步工厂初始化或校验格式1文件。异步配置只借用已连接、无事务的官方 aiosqlite.Connection，不创建/关闭连接，不自动迁移。要求本机 main 库、WAL、自有 marker、精确框架版本和官方表列；设置 FULL 与有界 busy timeout，返回严格 serializer 的官方 AsyncSqliteSaver。

宿主拥有 aiosqlite 工作线程。配置失败、超时或取消后关闭连接，不继续使用；取消 await 不能撤销排队 SQL。先等待操作任务退出，再 await 连接与 HTTP 客户端关闭。关闭再次被取消时，宿主仍需在事件循环退出前完成清理；库不强停 SQL，也不管理工具自行创建的任务。配置超时覆盖 SQL 等待，不承诺中止原生工作线程。

## 结果和取消

领取后先 await 最新 snapshot，再检查领取的单调 deadline，才 await 原工具。确认成功且后验 snapshot 未变化，才发送定向完成收据并以 sync durability 继续图。

| 结果 | 含义 |
| --- | --- |
| confirmed / resumed | 工具结果已确认，图继续返回；value 保持原对象 |
| unknown / not_resumed | 确认响应未知，保留 value，图不继续 |
| confirmed / blocked | 确认后 checkpoint 改动，图不继续 |
| confirmed / unknown | 图继续普通异常；不能据此重跑工具 |
| CancelledError | 原取消传播；按取消阶段，领取、业务、确认或图写入可能已发生 |

领取永久消费。业务取消不发送 failed，异常确认错误不覆盖原业务异常。确认/图继续期间取消也传播，不能换 call/action/key 重试未知副作用，不能自动重建完成收据。审批库和图文件不构成共同事务。核对审批状态和图状态后由宿主处理；本版本没有自动补偿。

Trace 不新增 state/config/ticket/参数正文，保留 Agent 父上下文；审核存储和本机 checkpoint 则包含宿主主动披露的完整 JSON 参数，应按业务数据管理。验证范围见 [015 任务](../specs/015-async-graph/tasks.md)。

# ADR-0009：原生异步图与借入 SQLite 连接

日期：2026-10-22。状态：采用。对应 [SPEC-015](../../specs/015-async-graph/spec.md)。

同步审批图和本机格式1已存在。异步宿主需要保留取消与 Agent 上下文，且原生 aiosqlite 在线程中排队执行 SQL；取消 await 并不表示 SQL 撤销。

新增 AsyncReviewedGraphTool，复用纯 snapshot/请求/HMAC 收据校验，仅通过 aget_state/ainvoke 操作图。工具仍在调用者任务中 await，异步 checkpoint 前置校验后重新检查领取时限。取消不转换为普通 blocked/unknown，不创建补偿任务，不释放已消费领取。

宿主在事件循环启动前用同步工厂初始化或校验文件，以 async with 管理官方 aiosqlite 连接。Aegis 仅校验并配置借入连接和 AsyncSqliteSaver。选择明确的连接所有权，避免在库内承担创建/关闭被重复取消后的工作线程回收。配置失败后宿主关闭连接并等待队列排空。

沿用原文件 marker、严格 serializer、四迁移和审批协议，无新第三方版本。代价是宿主需要同步启动步骤及明确关闭资源；本机单宿主/单 root interrupt 边界保持。多机协调、跨库事务、收据恢复、通用 checkpointer 抽象另行设计。

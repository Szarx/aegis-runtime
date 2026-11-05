# ADR-0008：官方SQLite与保守进程恢复

日期：2026-10-22。状态：采纳，参见 [SPEC-014](../../specs/014-durable-graph/spec.md)。

使用官方SqliteSaver验证本机跨进程恢复，不自研checkpointer或更改审批协议。显式文件、新建/重开分开、marker版本检查、严格serializer和sync durability，使丢失文件/不兼容格式不能悄悄变成新执行。三个新依赖只在可选extra，旧59版本保持。

业务单次保证仍来自稳定逻辑call的永久消费claim。恢复图不能重新运行claimed/failed/completed工具；完成确认与图写入间崩溃保守保持暂停，不重建收据。代价是部分动作需人工调查；本轮优先证明独立进程的边界，而不是引入跨库事务、租约或自动补偿。

文件/宿主可信且单个宿主串行驱动thread；marker和版本校验用于防误用，不构成防篡改审计。后续再分别设计生产checkpointer、调度协调、异步图与completed收据恢复。原InMemorySaver验收继续作为013历史证据。

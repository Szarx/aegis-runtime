# SPEC-007 方案

- 专用图流代理持有捕获的 SDK/父上下文，首次 advance 创建 Span；短时 attach/detach，消费者不继承悬挂 Agent。RLock 保护 finish-once，不以保持 context manager 跨 yield 实现。
- 不读取/缓存图流 payload，不做预取，原迭代器驱动真实框架。提供 context manager 便利接口；未初始化时原样返回，无全局补丁。
- aegis.graph.v1 单独版本化；JSONL v3 保留自有两个字段，原 v1/v2 格式不变。Collector 增加独立 Agent 映射分支，复用现有表与约束。
- SQL 动态汇总 graph_outcome；查询 schema 可空扩展，当前 OpenAPI 保存到 007，历史 004 不覆盖。前端使用已有 Badge 语义，并在节点详情显示图接口/结束原因。
- 真实 LangGraph + 合成 SDK transport 验证，不追加真实模型请求；范围由实际支持矩阵约束，不同时引入事件流或 checkpoint 恢复。

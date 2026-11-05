# SPEC-006 实现方案

- 基于公开 CompiledStateGraph.invoke / ainvoke 调用边界创建 v1 Agent Span，复用 operation_span 的 fail-open、取消与上下文逻辑。不在 callback start/end 之间 attach 长生命周期 context，避免回调运行线程或任务变化导致上下文泄漏。
- 保留图业务与现有 callbacks；模型 Wrapper 只负责模型，显式工具装饰器只负责工具，不由框架回调重复采集。节点只记录已经声明的模型/工具，不发明新的 operation 类型。
- observe_graph 对原始编译图及其 RunnableBinding with_config 结果包装。使用公开 with_config，不解析私有图调度器。with_retry / batch / stream 等委托结果不保证继续追踪，在文档明确。
- 示例使用真实 StateGraph / ToolNode、LangChain AIMessage/ToolMessage 和 OpenAI SDK 合成 DeepSeek transport；LangGraph 条件边控制模型→工具→模型。相同工厂可不启用任何 Aegis 包装，对照结果与计数。
- 所有 39 个已有依赖保持原固定版本，新增 LangGraph 及必需依赖。官方 PyPI metadata / wheels 核对 SHA256，分别记录 Windows / Linux 下载凭据；安装后 pip check 与 wheel 打包验证。
- 仅补充跨组件真实 PostgreSQL/HTTP 和浏览器验证，不重复构建未改动前端源码；Collector 镜像因锁文件需验证完整离线依赖构建。不得追加真实模型请求。

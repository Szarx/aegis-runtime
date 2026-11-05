# LangGraph 状态流研究与验收边界

查阅：2026-10-18，Asia/Shanghai。官方来源：[LangGraph Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)。以下为本项目整理，不保存整篇第三方文档。

官方文档将 stream / astream 的模式、输出格式与事件投影分别说明。本项目先支持状态流的公开迭代入口；不根据状态 chunk 猜测模型终态或 checkpoint 完成，不把事件投影 API 的存在等同于已验证。

## 本次决策

- 参数原样转发，不检查/复制 chunk。真实验证 updates / values、组合模式、v1/v2 和 custom；messages 仍需独立的原生 ChatModel 接入才能作自动 Token 追踪声明。
- 图执行惰性启动，所以创建迭代器时只捕获 SDK 和父上下文，首次取值才创建 Span。Span 在推进/关闭时短时激活，避免消费者处理输出时错误继承图父节点。
- EOF、提前关闭、错误和取消独立记录。提前关闭不表示完整业务完成，也不回滚已发生工具副作用。没有看到 EOF 时保守标 closed。
- 使用自有 aegis.graph.v1 元数据，复用既有 OTel 和数据库。图 state/config/chunk/messages 不进入遥测；该 mapping 不是新的标准 GenAI 字段兼容性声明。

基线沿用 SPEC-006：LangGraph 1.2.15、core 1.6.12、prebuilt 1.1.1，Python 锁文件共 59 项，本轮无新增依赖。原两平台官方 wheel 来源和 SHA256 继续有效，不生成虚构下载记录。来源索引仍为 31 个唯一 ID，复用 langgraph-streaming 并更新查阅状态。

## 已完成证据

85 个 Python 与 23 个前端测试方法；六组真实图、合成模型 baseline / traced CLI 对照；传播异常与取消两个场景；8 Trace / 24 Span 经真实 HTTP / PostgreSQL / Dashboard 核对。Windows 类型/Vite、Docker Collector/Dashboard 与 SDK wheel 隔离安装通过。本轮零新增真实模型请求。

事件投影、checkpoint/interrupt 恢复、原生 ChatModel、框架内真实 Provider 和新用户接入耗时均未验收。契约见 [SPEC-007](../../specs/007-langgraph-stream/spec.md)，实际结果见 [tasks](../../specs/007-langgraph-stream/tasks.md) 与 [机器可读摘要](../../specs/007-langgraph-stream/validation.json)。

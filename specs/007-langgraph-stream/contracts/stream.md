# 图状态流契约

版本：SPEC-007，2026-10-18。固定 LangGraph 1.2.15、langchain-core 1.6.12、prebuilt 1.1.1；不声明其他版本兼容。

## 入口与资源责任

```python
from aegis.langgraph import observe_graph

graph = observe_graph(existing_compiled_graph, name="order-agent")
with graph.stream(input_state, config=existing_config, stream_mode="updates", version="v2") as chunks:
    for chunk in chunks:
        consume(chunk)
        if should_stop():
            break
```

异步对应 `async with graph.astream(...)` / `async for`。SDK 初始化和导出沿用现有 API；模型使用 Wrapper、工具使用 Decorator。没有初始化时直接返回原流，不增加上下文管理接口。创建时已初始化、消费前 SDK 关闭时不创建新 Span。

返回对象提供标准迭代、close / aclose 和上下文管理，不保留原生成器类型，不支持 send / throw / asend / athrow。传入参数和 chunk 原样交付，不预取或读取输出；创建时捕获父上下文，首次推进才开始图 Span，仅推进/关闭期间 attach。消费者工具保留消费者父上下文；框架节点内部显式 LLM/Tool 继承图 Agent。

提前停止必须明确关闭，单纯 break 后不保证 GC 清理。关闭不回滚工具，不承诺强制停止框架后台工作。最后一项已交付但未实际观察 EOF 时，关闭仍保守记录 closed。每个图流只结束/导出一次，重复关闭仍按底层资源行为处理。

## 生命周期与映射

| 观察到的终止 | aegis.graph.outcome | OTel status | error.type |
| --- | --- | --- | --- |
| 迭代 EOF | completed | UNSET | 无 |
| EOF 前 close / aclose 或正常退出上下文 | closed | UNSET | 无 |
| 原流推进/关闭抛错 | error | ERROR | 原异常类型 |
| 推进/上下文取消 | cancelled | ERROR | CancelledError 类型 |
| 未消费就关闭 | 无 Span | — | — |

普通消费者上下文体异常不归因图，清理正常时为 closed。直接关闭遇到原流清理错误时传播原错误；上下文体已有异常时优先保留体异常，清理错误只记录遥测；体取消优先标 cancelled。观测错误 fail-open，不添加业务重试。

图 Span 为 INTERNAL / invoke_agent，名称 `invoke_agent <name>`，mapping 为自有 `aegis.graph.v1`。属性仅允许 mapping、operation、agent name、graph.mode=stream|astream、graph.outcome 和 error.type；exception event 仅保留类型。没有 state、config、chunk、messages、提示词、工具参数、响应正文或凭证。本地 JSONL schema 为 `aegis.span.v3`；原 invoke / ainvoke 保持 v1、模型保持 v2。

Collector 必须随新 mapping 升级。数据库继续迁移集合 {1,2}，无需新表列；当前 [OpenAPI](openapi.json) 的 TraceSummary 增加 nullable graph_outcome，按已存 graph mapping 的 error > cancelled > closed > completed 归约；没有图流记录时 null。status 仍汇总整个 Trace 的 ERROR；图 completed 与错误工具可以同时存在。前端兼容缺失/为 null 的旧 summary，UNSET 筛选文案为“无异常”，closed 为“提前关闭”。旧 OpenAPI 历史快照不覆盖。

## 实际验证范围

真实 StateGraph / ToolNode 的 stream / astream、updates / values、组合模式、v1/v2 chunk 格式和 custom 输出已运行。config / context / callbacks 与 with_config 保持；chunk 与业务异常身份、前后业务输出、执行次数、并发和消费者上下文已验证。

messages 仅原样转发；不声明原生 ChatModel 自动 Token 追踪。stream_events / astream_events 事件投影、batch、checkpoint / interrupt / resume、分布式恢复和框架内真实 Provider 未验收。EOF 只表示本次迭代结束，不能推断 checkpoint 业务已完成。完整条件见 [spec](../spec.md)，结果见 [任务](../tasks.md)。

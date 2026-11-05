# SPEC-007：LangGraph stream / astream 生命周期

日期：2026-10-18。先维护契约，再开发；基线沿用 LangGraph 1.2.15 与 SPEC-006 的 59 个固定依赖。本轮不追加真实模型请求。

## 公共行为

1. observe_graph 返回代理新增 stream / astream；原图仅调用一次，位置/关键字参数、config/context/callbacks、stream_mode、version 原样转发。不额外调用 invoke / get_state，不预取、不复制 chunk，不改变工具次数或新增业务重试。仍不保持原生成器类型身份；支持公开迭代协议和显式 close / aclose，并提供 with / async with 便利关闭。send / throw / asend / athrow 不在接口范围。
2. 调用 stream 方法时捕获父上下文；首次 next / anext 才建立 Agent Span 和开始执行。没有消费便关闭时没有 Span。SDK 未启用时直接返回原迭代器；创建时启用、首次消费前关闭 SDK 时也不启动新 Span。
3. 只在取下一项、关闭原流期间激活图 Agent，交出 chunk 后恢复消费者上下文。框架节点/显式 LLM/Tool 继承图 Agent；消费者在两次 yield 之间调用的工具继承消费者父上下文，不能误挂图节点。不同异步流互不串联。
4. 实际 EOF 记录 completed；显式提前 close / aclose 或上下文正常退出记录 closed；异常 error、取消 cancelled，保持原异常身份。只观察到最后一项但未继续取 EOF，关闭时保守记 closed。结束一次，重复关闭不重复导出。单纯 break 不承诺 GC 清理，调用者必须关闭或使用上下文管理。
5. 普通消费者上下文体异常不归因图执行，记录 closed；CancelledError 记录 cancelled / ERROR。原流关闭错误记录 error 并由直接 close 调用传播；上下文体已有异常时保留原异常，清理错误仅记录在遥测中。关闭不等于回滚已经执行的工具，也不承诺强制终止原框架无法停止的后台工作。

## 数据契约

流式 Agent 使用自有 mapping `aegis.graph.v1`、operation invoke_agent、kind INTERNAL、name `invoke_agent <agent>`。原 invoke / ainvoke 继续 v1，模型继续 v2。新增字符串属性 aegis.graph.mode=stream|astream、aegis.graph.outcome=completed|closed|error|cancelled；仅允许 Agent 名称、mapping、operation、error.type 和这些图元数据，图 state/config/chunk/messages/内容/凭证不采集。本地 JSONL 为 aegis.span.v3。

closed / completed 保持 UNSET，error / cancelled 为 ERROR 并带真实异常类型。Collector 校验 mapping/kind/operation/outcome 配对，旧 v1/v2 不变；旧服务会拒绝新 mapping，完整展示需要本增量 Collector。

SQL 无新增表列或迁移，继续 1+2。Trace 汇总新增可空 graph_outcome，由当前已有 graph mapping 的 Span 派生，优先 error→cancelled→closed→completed，无图流 Span 为 null。原 status 仍表示是否有 ERROR 子节点，与生命周期分开。列表/详情用 graph_outcome 显示“提前关闭/已取消”，不将 closed 标为完成；UNSET 筛选显示“无异常”，可包含正常提前关闭。无新增费用或 Token 汇总。

## 支持与验收

验证真实 StateGraph 的同步/异步 updates / values、组合模式与 v1/v2 chunk 格式，以及真实 custom 输出。messages 参数只转发，不宣称原生 ChatModel 自动 Token 追踪。事件投影 stream_events / astream_events、batch、checkpoint / interrupt / resume、分布式与恢复仍不在范围；EOF 仅证明本次迭代结束，不证明未验收的 checkpoint 业务完成。

| AC | 验证 |
| --- | --- |
| 701 | 真实框架 stream / astream 输出、参数/回调、对象身份、懒启动/无预取和 before/after 行为一致 |
| 702 | EOF/提前关闭/关闭前未消费/异常/取消/清理异常，Span 结束一次且保留原异常 |
| 703 | 框架线程/异步任务和多个流上下文正确；消费者工具不挂图 Span，原 invoke / ainvoke 回归 |
| 704 | 图 v3 JSONL、OTLP 白名单和类型/状态配对、隐私、旧 v1/v2、观测故障 fail-open |
| 705 | 真实 PostgreSQL / HTTP 查询与 Dashboard 列表/详情正确区分 closed / completed / cancelled / error |
| 706 | CLI 成功/提前关闭/框架处理错误对照、相关回归、构建、wheel、OpenAPI 和文档更新 |

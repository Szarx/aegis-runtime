# LangGraph审批中断示例

真实StateGraph/InMemorySaver，普通同步工具只向忽略目录artifacts/langgraph-reviewed/tool-calls.jsonl追加合成记录。无模型或外部业务调用。按 [图恢复接入](../../docs/langgraph-reviewed.md) 安装extra，启动已有Collector/PostgreSQL/Dashboard，宿主配置独立producer/executor凭证及稳定的AEGIS_APPROVAL_BINDING_KEY（至少32字节hex）。

```text
python examples/langgraph-reviewed/agent.py --rebuild-host
```

程序先暂停并输出action_id，不调用工具。在Dashboard“执行审批”查看graph_binding中的graph/thread/checkpoint/interrupt与完整arguments，核对后批准，然后回到终端按Enter。Enter只触发恢复尝试，不能代替服务端批准。成功退出码0，函数写一次，图返回完成标记。审核凭证不交给Agent。

加`--fail`验证先写一次后业务异常（退出码2），图保持暂停，不重试。拒绝审批或尚未批准时按Enter，退出码1且工具零执行。EOF退出码4，无执行；当前InMemorySaver随进程退出丢失，数据库审批仍可能保留，到期前不要用新id/key试图替代该动作。

`--rebuild-host`重新构造驱动/编译图并复用同一个进程内saver，验证宿主对象可重建；不是跨进程checkpoint持久化验收。JSONL遥测不含参数正文，图checkpoint和审核参数包含主动披露的完整实参，需宿主保护。默认例含9223372036854775807，页面应保留原整数。

退出码3表示已执行但图未确认继续，输出continuation为not_resumed/blocked/unknown；不能重新执行工具。先查询审批和checkpoint，按接入文档人工处置。本例不自动轮询、不自动审批、不实现图异步/子图/多interrupt或外部副作用恰好一次。

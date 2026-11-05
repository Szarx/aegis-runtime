# 异步执行审批示例

只向忽略目录 artifacts/async-reviewed-execution/tool-calls.jsonl 追加合成记录，无LLM或外部业务调用。Python3.11+；先按 [异步接入](../../docs/async-reviewed-execution.md) 安装Runtime的reviewed-async extra，启动已有Collector/PostgreSQL/Dashboard，并在宿主配置独立producer/executor凭证和至少32字节的十六进制AEGIS_APPROVAL_BINDING_KEY。审核凭证只在Dashboard使用。

```text
python examples/async-reviewed-execution/agent.py prepare
```

在Dashboard“执行审批”核对完整参数（含默认值和64位整数）、demo-async-v1版本，明确批准；记下action_id后运行：

```text
python examples/async-reviewed-execution/agent.py resume --action-id YOUR_ACTION_ID
```

prepare/resume两边的`--scenario`、`--value`及所有配置必须相同。`--endpoint`可指定实际回环HTTP origin，不含路径。

| scenario | 工具副作用 | 返回码 / 服务状态 |
| --- | --- | --- |
| success（默认） | 追加一次 | 0 / completed；确认失败则unknown |
| failure | 追加一次后抛业务异常 | 2 / failed（确认成功时） |
| cancel | 宿主确认工具已经追加后取消并等待该任务 | 3 / claimed，结果未知 |

重复resume全部拒绝，退出码1且不新增记录。取消示例使用宿主拥有并等待结束的任务，不使用超时猜测工具是否开始；工具侧可能已有副作用，因此claimed不释放。确认期间取消时服务也可能已经completed，不能根据异常推断服务状态。该示例未实现自动查询、轮询、重试或图checkpoint恢复。

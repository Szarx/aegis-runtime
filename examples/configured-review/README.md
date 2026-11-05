# 配置工具的人工审核与单次恢复

本例使用v2 Application配置，write只能经reviewed_tool绑定。固定合成参数经显式disclose_arguments=True披露给审批服务；业务只追加一行本地计数，不访问LLM或业务系统。

先阅读[完整指南](../../docs/configured-review.md)，在本机配置独立producer/executor凭证与binding key，reviewer由独立审核者持有。prepare/resume分别运行：

```text
python -m aegis_runtime inspect examples/configured-review/application.json --subject demo-agent
python examples/configured-review/agent.py prepare --endpoint http://127.0.0.1:8000
python examples/configured-review/agent.py resume --endpoint http://127.0.0.1:8000 --action-id YOUR_ACTION_ID
```

中间通过现有Dashboard“执行审批”核对完整参数并批准/拒绝；本例不自动审批。两条均可加--async；异步需reviewed-async extra。默认JSONL路径在artifacts/configured-review，网络遥测可按统一接入指南替换配置telemetry。

成功批准恢复进入业务1次，拒绝/未批准/过期/参数篡改为0，重复恢复不增加计数。--scenario failure进入后失败，--async --scenario cancel进入后取消；两者可能已有副作用。unknown退出4，不能据此自动重试，状态仍需查询。准备和恢复使用相同scenario/value/summary/ttl与工具实现版本，变更后旧批准不可复用。

应用只拥有SDK，借入客户端由宿主管理，关闭前等待操作结束。恢复只针对工具动作，宿主自行决定Agent后续步骤；不自动继续任意图或授予配置认证。完整测试与安装证据见[026任务](../../specs/026-configured-review/tasks.md)。

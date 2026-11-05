# Policy审批闭环示例

同一配置中reader允许直接调用，reviewer要求审批，blocked拒绝。仅操作--calls指定的合成JSONL文件，无LLM请求或外部业务系统；示例进程显式关闭LangSmith自动追踪。需要先启动启用Trace、producer、reviewer、executor四个独立角色的本地Collector/PostgreSQL；使用自己的本机环境变量AEGIS_API_TOKEN、AEGIS_APPROVAL_REQUEST_TOKEN、AEGIS_APPROVAL_EXECUTION_TOKEN、AEGIS_APPROVAL_BINDING_KEY。不要把真实密钥写入示例文件。

安装依赖见[配置指南](../../docs/policy-approval.md)；异步图可选runtime[reviewed-langgraph-async]，发送OTLP另装sdk[otlp]。默认application.json输出本地JSONL；若要平台看到治理事件，把telemetry改为otlp、endpoint为本机/v1/traces、token_env为AEGIS_API_TOKEN。审批endpoint仍用Collector根地址，默认http://127.0.0.1:8000。

从仓库根目录执行，artifacts目录需存在，新ticket不可覆盖：

```text
python examples/policy-approval/agent.py request --subject reviewer --ticket artifacts/policy-ticket.json --calls artifacts/policy-calls.jsonl
```

输出pending_review与action_id，业务文件尚不存在。进入“执行审批”，用独立reviewer凭证连接，按Action ID搜索、展开并核对全部参数/工具版本，勾选确认后记录批准。页面决定不执行工具。随后在另一个进程运行：

```text
python examples/policy-approval/agent.py resume --subject reviewer --ticket artifacts/policy-ticket.json --calls artifacts/policy-calls.jsonl
```

只新增一行，返回completed/confirmed；再次resume返回approval_unavailable且不新增业务行。request/resume的参数/摘要/工具版本/策略/TTL必须一致，--value用于演示参数变化会被拒绝。reader的request直接执行；blocked的request退出1且零执行。不同请求用不同ticket/calls路径，避免把新调用当作旧动作恢复。

两个命令都可追加--mode langgraph和--async，使用真实StateGraph与原生异步工具。图由外部驱动明确运行request或resume节点，持久的是完整审批票据；它不通过重新运行请求图来恢复工具，也不宣称本示例提供LangGraph checkpointer恢复。原持久图接入另见[既有配置图指南](../../docs/configured-graph.md)。

--scenario failure在写入后抛错，--async --scenario cancel在写入后取消，用于验证部分副作用后不能重做。示例无自动重试/回滚；确认unknown退出4，取消3，审批不可用2，拒绝1，其余配置/业务/导出失败5。request输出失败文件可能为空，不能当作可恢复票据；先检查当前平台与调用日志。需要在准备响应丢失后找回同一请求时，可预先保存非零hex32的--action-id，使用新的ticket文件显式重准备；它不重执行业务。

该例会把完整合成参数写入本机ticket和服务端审批记录，这是明确开启的披露。Trace/事件不保存参数值。平台关联流程、信任边界与完整验收见[045任务](../../specs/045-policy-approval/tasks.md)。

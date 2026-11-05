# 异步持久图示例

从仓库根目录运行，先按 [接入说明](../../docs/async-graph.md) 安装 reviewed-langgraph-async extra 并启动 Collector / PostgreSQL。示例没有 LLM，工具只追加合成记录。reviewer 与 producer/executor 使用独立凭证。

宿主环境需要 AEGIS_APPROVAL_REQUEST_TOKEN、AEGIS_APPROVAL_EXECUTION_TOKEN、AEGIS_APPROVAL_BINDING_KEY（至少32字节的十六进制密钥）；通过本机环境设置，不放入代码或聊天。Collector 必须启用相应独立角色，配置见 [执行审批](../../docs/reviewed-execution.md)。

```text
python examples/async-durable-graph/agent.py start --state artifacts/my-async-graph
python examples/async-durable-graph/agent.py status --state artifacts/my-async-graph
```

start 使用全新目录并保存 checkpoint / ticket，工具执行零次。在 Dashboard 的 `#/reviewed-actions` 使用 reviewer 凭证核对完整 graph_binding / arguments 与 digest 后批准，再由宿主运行：

```text
python examples/async-durable-graph/agent.py resume --state artifacts/my-async-graph
python examples/async-durable-graph/agent.py status --state artifacts/my-async-graph
```

每条命令是独立进程；status 无需审批凭证、不访问审批服务。默认 endpoint 为本机8000，可传 --endpoint。resume 用新原生异步 SQLite 连接和 HTTPX 客户端，执行一次并继续原图。退出码0成功、1操作未完成、2合成业务部分失败、3结果/图继续未知；这些退出码不能作为业务重试依据。

新目录 start 可加 --fail，工具追加记录后抛错；图保持暂停、动作 failed，不能再次执行。工具日志是小型同步文件副作用示例，不代表通用异步文件适配器。连接由宿主 async with 关闭，初始化/格式校验在 asyncio.run 前完成。不要手工重建 ticket、清空文件或更换 call 来重试未知结果。

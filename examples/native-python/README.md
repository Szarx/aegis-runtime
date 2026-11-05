# Native Python Agent Example

状态：已实现；对应 [SPEC-001](../../specs/001-python-sdk/spec.md)，支持本地 JSONL 与 SPEC-002 Collector，不依赖模型凭证或真实业务系统。

合成订单查询 Agent 调用 `lookup_order`，SDK 用入口和 Tool 装饰器建立父子 Span。成功查询返回合成状态，失败查询按原逻辑抛出 LookupError；示例捕获预期错误后结束。

仓库根目录按 [SDK 安装说明](../../sdk/python/README.md) 安装后：

```text
python examples/native-python/agent.py
python examples/native-python/agent.py --output artifacts/custom/traces.jsonl
```

每次运行追加 4 个 Span、形成 2 次 Agent Run，预期树如下：

```text
invoke_agent customer-agent (UNSET)
└── execute_tool lookup_order (UNSET)

invoke_agent customer-agent (ERROR)
└── execute_tool lookup_order (ERROR, builtins.LookupError)
```

默认输出 `artifacts/native-python/traces.jsonl`，每行一个本地调试记录。记录不包含订单编号、返回内容、异常消息或堆栈；输出的 `orders.read` 仅为权限元数据。

终端显示业务结果、预期失败提示和导出诊断，退出码为 0 表示 flush 与 shutdown 成功。可重复运行，文件采用追加方式。网络模式接入 Collector 与 PostgreSQL，Dashboard 已可查看原生执行，尚无安全策略。

## 网络模式

先按 [本地部署](../../deploy/docker/README.md) 启动服务，再执行：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/native-python/agent.py --endpoint http://127.0.0.1:8000/v1/traces
```

`--output` 与 `--endpoint` 互斥。不指定两者时保持默认本地输出。网络模式新增 2 个 Trace / 4 个 Span，查询 `/api/v1/traces` 和详情接口，或打开 Dashboard（默认 8080）输入相同 token 查看执行，重启 Collector 后仍可查询。示例只输出目的地址与诊断，不输出认证头。

测试会在临时目录运行示例并验证 4 个 Span、2 个 Trace、状态与父子关系；见 [验收记录](../../specs/001-python-sdk/tasks.md)。

# 最小工具权限控制示例

本例只用固定返回值与内存执行计数，不调用模型、数据库或真实业务系统。仓库根目录按 [SDK](../../sdk/python/README.md) 准备开发依赖，再安装两个本地组件：

```text
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime
python examples/runtime-policy/agent.py
python examples/runtime-policy/agent.py --async
```

默认 artifacts/runtime-policy/traces.jsonl，可用 --output 改路径；每次追加 4 Trace / 8 Span。一次允许执行 1 次、显式拒绝 0 次、无匹配默认拒绝 0 次、允许后工具抛合成异常执行 1 次。异常对象保持，拒绝先于工具执行。CLI 输出计数和诊断，不打印工具参数或结果。

策略来自本目录 policy.json：order-agent 可读，blocked-agent 同时匹配 allow 和 deny，实际 deny 优先；orders.write 没有匹配而默认拒绝。subject 在 Runtime 构造时由宿主绑定，不使用 Agent 展示名或函数参数。将已有 aegis.tool 替换为 runtime.tool，保留 Agent observe 和已有模型 Wrapper；工具传给 StructuredTool 前包装，真实 LangGraph ToolNode 的允许/拒绝路径已测试。

按 [部署](../../deploy/docker/README.md) 启动 Collector / Dashboard 后，PowerShell：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/runtime-policy/agent.py --endpoint http://127.0.0.1:8000/v1/traces
python examples/runtime-policy/agent.py --async --endpoint http://127.0.0.1:8000/v1/traces
```

每个受控工具尝试有独立 action_id；新 mapping aegis.governance.v1，JSONL v4。Dashboard 中选择工具可看允许/阻止、原因、身份、规则与策略版本；拒绝显示“已阻止”，允许后业务错误仍显示异常。Trace ERROR 可含被拒绝尝试，不代表拒绝工具曾执行。旧 permission 标签仍只代表元数据。

Collector 必须与新 SDK 一起升级，旧服务不接受新 mapping；无需 SQL 迁移，继续 {1,2}。身份/决策来自应用上报，页面不执行授权，不是可信认证或不可篡改审计。未覆盖直接调用原函数、进程沙箱、外部用户认证、人工审批或恢复。契约与实际结果见 [009](../../specs/009-runtime-policy/tasks.md)。

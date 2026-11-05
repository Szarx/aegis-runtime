# OpenAI 示例

SPEC-004 已完成离线验收。默认运行官方 OpenAI 3.33.0 客户端，HTTPX2 MockTransport 返回合成 JSON / SSE，不需要 Key、网络 Provider 或付费模型。每次明确输出 offline，产生 Agent / LLM / Tool 三个 Span。Tool 返回合成订单状态；没有模型自动选工具的声明。

## 安装与本地记录

仓库根目录创建并激活 Python 3.11+ 环境后：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python
python examples/openai/agent.py
python examples/openai/agent.py --api chat --stream --async
```

默认追加到 artifacts/openai/traces.jsonl。`--api responses|chat`、`--stream`、`--async` 组成 8 种支持组合；缺省 Responses、同步、非流式。合成响应 input=7 / output=3，仅用于链路验收。`--output <path>` 可改本地文件。

## Collector 与 Dashboard

先按 [部署说明](../../deploy/docker/README.md) 启动 Compose，PowerShell：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/openai/agent.py --stream --endpoint http://127.0.0.1:8000/v1/traces
```

打开 Dashboard http://127.0.0.1:8080，输入同一 token，查看 openai-order-agent；选择 offline-model，核对 Token、模型、API 与结束原因。endpoint 必须包含 /v1/traces，与 output 互斥。

## 接入已有应用

将 OpenAI / AsyncOpenAI 的构造入口替换为 AegisOpenAI / AegisAsyncOpenAI（来自 aegis.openai），或 `client = wrap_openai(client)`。现有 create 参数、响应和事件对象保持；使用 @observe 标记应用入口、@tool 标记工具。客户端与 Stream 是代理对象，不保持原类型身份。

支持 `.responses.create` / `.chat.completions.create` 同步/异步、非流式/stream=True。流式提前停止必须 close 或 with / async with；单纯 break 不保证清理。Chat 流用量由调用者传入 stream_options.include_usage；示例显式设置，包装器不修改参数。Responses.stream 辅助器、raw、parse、Realtime、WebSocket、Azure、Agents SDK 与框架自动接入未验证；范围外入口委托且不追踪。

## 真实模型另行验收

本轮按用户选择不运行 live。后续仅在本机配置 OPENAI_API_KEY 和 OPENAI_MODEL，再显式使用 `--mode live`；没有默认真实模型。Key 不应发到聊天、写入源码或遥测；示例不打印模型正文。live 会实际调用模型，其成功不在本轮证据中。

完整支持矩阵、流与隐私约束见 [spec](../../specs/004-openai/spec.md)，结果见 [验收记录](../../specs/004-openai/tasks.md)。

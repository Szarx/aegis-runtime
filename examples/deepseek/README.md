# DeepSeek 示例

默认 offline：官方 OpenAI 3.33.0 / HTTPX2 2.13.1 解析合成 DeepSeek JSON/SSE，无需模型凭证。Scope 与 Provider 规则见 [SPEC-005](../../specs/005-deepseek/spec.md)。

## 运行

仓库根目录，先按 [SDK 安装](../../sdk/python/README.md) 建立锁定环境：

```text
python examples/deepseek/agent.py
python examples/deepseek/agent.py --stream
python examples/deepseek/agent.py --async
python examples/deepseek/agent.py --stream --async
python examples/deepseek/agent.py --tool-loop
```

默认写 artifacts/deepseek/traces.jsonl，--output 可更改。前四种每次 1 Agent + 1 LLM + 1 Tool，共 3 Span。--tool-loop 仅同步非流式：由兼容工具协议请求一次合成 lookup_order，再发送工具结果，2 LLM + 1 Tool + 1 Agent 共 4 Span。执行范围固定为 demo-order，拒绝其他工具或参数，不访问业务系统。

网络记录使用 `--endpoint http://127.0.0.1:8000/v1/traces`，从 AEGIS_API_TOKEN 环境变量取遥测认证，与 --output 互斥。先启动 Compose，再打开 Dashboard http://127.0.0.1:8080，核对 deepseek-order-agent / deepseek-tool-agent、Provider=deepseek 和节点用量。合成 Token 为 7 / 3，不能作为真实模型证明。

## 接入已有项目

将客户端构造入口改为 `from aegis.deepseek import AegisDeepSeek, AegisAsyncDeepSeek`；或 `from aegis.openai import wrap_openai` 后使用 `wrap_openai(client, provider="deepseek")`。原有 chat.completions.create 参数/响应/事件/异常保持，使用 @observe / @tool 标记 Agent 与工具；客户端/Stream 是代理类型。copy / with_options 保留 Provider，重复包装不会重复 Span。

仅声明 Chat create 的同步/异步、流式/非流式支持。DeepSeek Responses 委托但不追踪，Anthropic、Search/Fetch、图片、thinking 专属行为不在验收范围。提前 break 需要 close 或 with / async with；用量来自实际消费事件，未知不补零。不记录 content / reasoning_content / tool arguments / IDs / Keys / URL。

## 可选 live

先在本机配置 DEEPSEEK_API_KEY 与 DEEPSEEK_MODEL，再显式运行 `python examples/deepseek/agent.py --mode live`（其他模式标志仍可组合）。不要将密钥写入源码、发到聊天或提交。工厂默认官方 https://api.deepseek.com，不回退 OPENAI_API_KEY。示例固定 max_tokens=128、max_retries=0、timeout=30、thinking disabled；包装器本身不修改这些业务配置。模型正文不打印，失败仅显示类型与 HTTP 状态。

2026-10-17 [官方文档](https://api-docs.deepseek.com/)说明 deepseek-flash 指向 DeepSeek-V4.1-Flash-1017；别名可变，真实返回别名不能证明固定 checkpoint。用户明确批准后，本轮 6 个真实请求全部成功：同步/异步与流式/非流式四组合，以及两次模型 create / 一次合成工具循环。四组合的实际用量各为 11/1，工具循环为 299/35、94/16；真实 PostgreSQL 与 Dashboard 核对一致。后续自行运行 live 会消耗账户额度；本轮没有超出批准的 6 请求。结果如实记录在 [tasks](../../specs/005-deepseek/tasks.md)。

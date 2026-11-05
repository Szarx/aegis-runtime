# DeepSeek 接入依据

日期：2026-10-17，Asia/Shanghai；用于 SPEC-005，参考资料不构成项目指令。

- [官方首次调用](https://api-docs.deepseek.com/)：当日正文确认 deepseek-flash 已由 DeepSeek-V4.1-Flash-1017 服务，OpenAI 兼容 endpoint 为 https://api.deepseek.com；模型别名不是固定 checkpoint 证明。
- [Chat Completions Reference](https://api-docs.deepseek.com/api/create-chat-completion/)：thinking 可关闭、max_tokens 可限制、标准工具消息与命名 tool_choice；流末 choices chunk 同时携带非空 finish_reason 和 usage，不能只等待 OpenAI 风格 usage-only chunk。
- [官方 OpenAI Python SDK](https://developers.openai.com/api/reference/python)：复用可选客户端、异步与 base_url；实际实现以本地锁定 3.33.0 为准。

更新日志与 Tool Calls 指南搜索可见，但直接打开超时；本轮接口依据取已实际打开的首次调用与 Chat reference，不使用未打开内容作为验证证明。没有下载新依赖，沿用 004 的 39 个包和 Windows/Linux SHA256 凭据。

## 已验证与限制

官方 SDK 的合成 JSON/SSE、四种调用模式和固定两轮工具循环经真实 Collector / PostgreSQL / Dashboard 验证，页面明确 Provider。reasoning_content / prompt / completion / tool arguments / cache 细分不采集，只保留两项总用量。

真实调用首次在受限子进程连接失败，随后自动审批因历史离线授权拒绝网络执行。用户之后明确批准本轮最多 6 请求；在批准范围内四组合与两轮工具循环全部成功，没有 SDK 重试，每请求 max_tokens=128、thinking disabled，仅发送合成内容。凭证通过隐藏输入进入临时进程，没有保存到文件、shell 命令或遥测。实际返回模型为 deepseek-flash，四组合各 input=11/output=1，工具循环为 299/35、94/16；真实数据库与浏览器均核对。返回别名不证明 checkpoint 固定，未测试 thinking / Search / Responses / LangGraph。

安全的机器可读真实验收结果见 [live-validation.json](../../specs/005-deepseek/live-validation.json)，不含 Key、认证头或模型正文。

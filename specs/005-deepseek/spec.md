# SPEC-005：DeepSeek Provider 与真实调用验收

日期：2026-10-17。先维护本契约，再开发；状态见 [任务](tasks.md)。用户已授权使用 DeepSeek 凭证继续开发与验证，取代“所有真实调用均延后”的本轮安排；OpenAI Provider 本身仍未实测。

## 范围与接口

官方文档当日确认 deepseek-flash 指向 DeepSeek-V4.1-Flash-1017，OpenAI 兼容 base_url=https://api.deepseek.com。本增量优先支持 chat.completions.create，同步/异步、非流式/stream=True；Responses、Anthropic 格式、Search/Fetch、图片与 thinking 专属行为留待后续，不声称平台不提供这些 API。

公共入口 `from aegis.deepseek import AegisDeepSeek, AegisAsyncDeepSeek`，默认官方 base_url，从显式 api_key 或本机 DEEPSEEK_API_KEY 读取凭证，不回退 OPENAI_API_KEY。复用 OpenAI 3.33.0 / HTTPX2 2.13.1，额外安装组 deepseek。也允许 `wrap_openai(existing_client, provider="deepseek")`；provider 为显式观测类别，不推断 URL 或作为可信身份。仅接受 openai / deepseek，copy / with_options 保留，重复包装幂等，冲突 provider 拒绝以防重复或错误归类。

## 行为与数据

1. 保持 SPEC-004 的参数、返回/异常对象、原 SDK 重试、异步上下文、流不预取、关闭/取消与结束一次。客户端/Stream 使用代理对象。DeepSeek provider 的 Responses 委托原客户端且不追踪；OpenAI 两类 API 保持原行为。
2. 仍使用 aegis.genai.v2 / CLIENT / chat，gen_ai.provider.name 新增 deepseek；Collector 拒绝未知 Provider 及 DeepSeek 的范围外 API。没有新增 SQL 列/迁移或 Token/费用汇总。Dashboard 节点明确展示 Provider，旧数据正常显示。
3. DeepSeek 流的最后一个内容 chunk 可同时包含 finish_reason 和 usage，choices 并非空数组。只从实际消费的字段提取 prompt_tokens / completion_tokens，不依赖 OpenAI 的 usage-only chunk。忽略 reasoning_content、cache 细分、工具参数和所有正文，保留缺失/零/整数规则。
4. 默认示例离线；live 必须显式启用并给定 DEEPSEEK_MODEL。示例限制 max_tokens=128、max_retries=0、请求超时 30 秒、thinking disabled；这是示例配置，不由包装器暗中修改。模型别名会随官方发布变化，不能把返回别名冒充固定 checkpoint 证明。
5. 不把用户凭证保存到文件、shell 命令、资源笔记、遥测或异常输出；凭证仅传给官方 api.deepseek.com。日志仅输出白名单元数据与错误类型/HTTP 状态，错误正文不打印。真实请求只包含合成验收内容。

## 验收

| AC | 要求 |
| --- | --- |
| 501 | DeepSeek 同步/异步工厂、独立环境变量、显式 Provider、copy / wrap 幂等与配置保持；没有新强制核心依赖 |
| 502 | 官方 SDK 解析 DeepSeek 风格 JSON/SSE，四种调用模式、终态同 chunk 用量、未知/零、关闭/取消、返回与异常语义 |
| 503 | Collector Provider 白名单与 API 配对、原生/OpenAI 回归、真实 PostgreSQL 保留 deepseek 与精确整数用量 |
| 504 | 少量真实 deepseek-flash 请求，分别记录成功或实际阻碍；Key/正文不进入记录。鉴权失败不重复收费重试，也不伪称已完成真实验收 |
| 505 | 默认离线示例、模型/Provider/用量的 Dashboard 展示、文档/来源更新、构建和相关回归通过 |

真实请求无法完成不阻断离线开发；任务记录如实保留未通过项目。真实 LangGraph 接入与体验计时仍需要独立 spec。

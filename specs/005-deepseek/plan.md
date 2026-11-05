# SPEC-005 实现方案

1. 让共享 ClientProxy / ResourceProxy / CallTrace 显式携带 Provider；默认 openai 保持兼容，DeepSeek 只拦截 chat create。copy、with_options 继续携带，重复 wrap 不重复记录。
2. aegis.deepseek 是可选轻量构造入口，使用 OpenAI 客户端和独立 DEEPSEEK_API_KEY；不新增第三方依赖，不自动修改模型或业务参数。
3. 在 Collector v2 校验中扩展 Provider 与 API 组合，继续使用现有 JSONB 和迁移 2。Dashboard 的模型节点增加 Provider 文本。
4. 独立 DeepSeek transport 夹具模拟“最终 choices chunk 同时含 usage / reasoning_content / cache 字段”；测试共用公共 SDK，避免只测试硬编码假客户端。
5. 示例默认离线，可显式 live；本轮先完成离线回归，再使用临时进程内凭证调用官方端点，验证实际返回的模型/usage 与保存的 Span 一致。失败时仅记录安全错误类别和状态，不打印 SDK 错误正文。
6. 维护 005 任务记录、资源笔记与现行产品说明；004 的离线证据作为历史保留，不改写成 OpenAI 真实调用成功。

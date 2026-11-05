# SPEC-004 实现方案

1. 使用代理组合官方 OpenAI / AsyncOpenAI，不复制完整构造签名，不侵入私有 HTTP 请求实现。只拦截两种 create；with_options/copy 继续包装，显式记录代理类型边界。
2. 独立 CallTrace 负责 parent context、有限 metadata 和 finish-once。stream 代理在每次 next/anext 临时激活，消费者迭代体不持有模型 context。结束不预读，也不依赖 finalizer。
3. 使用官方 SDK 3.33.0 实际 HTTPX2 JSON / SSE 解析测试；source/type 核对 transport 和流关闭方式后实现。核心装饰器继续 mapping v1，不破坏冻结的原生契约。
4. 模型 mapping v2 / 本地 JSONL v2；Collector 独立校验白名单与类型，原生 v1 格式不变。SQL 002 仅扩展已知 CHECK；迁移事务中按 schema advisory lock 串行，版本表记录 1/2，未来版本中止。
5. API Span attrs 支持 str|int（Pydantic strict union 防止 bool 变 Token），前端保留 usage 为 bigint。不引入 Token 汇总/费用字段或后端缓存。UI 新增第三种操作展示，修正“均未采集”的固定说明。
6. 保持独立于已有示例的合成 JSON/SSE fixtures；演示提供 offline 默认模式和显式 live。独立 Compose / PostgreSQL schema 验证升级、已有 Span 与新 LLM 数据，同源 UI 核对。
7. 所有安装和外部资料保持官方来源、精确版本和完整性记录；不读取用户密钥值。现有 SDK / Collector / 前端回归后再标记任务完成。

官方文档已实际读取：Python library、Streaming responses、Chat streaming events。字段常量另核对本地官方 opentelemetry-semantic-conventions 0.66b1，不声明完整 GenAI 规范兼容。真实 API 验收明确延后。

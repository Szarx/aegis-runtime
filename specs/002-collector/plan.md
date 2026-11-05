# SPEC-002 实现方案

1. SDK 使用可选官方 OTLP HTTP Exporter，保留本地模式和有界后台队列。冻结 endpoint / headers / 网络超时配置，不修改业务重试行为。
2. Collector 用官方 opentelemetry-proto 定义解码，单独的 ingestion 模块校验和过滤，不导入 SDK 私有代码。
3. FastAPI 提供接收、查询和健康 API；网络请求与数据库工作分离，同步数据库操作在线程池运行。
4. Psycopg 3 的 SQL 参数与 Identifier 负责值和 schema 安全引用。每次事务使用有限连接/语句超时，迁移只保留一个可打包 SQL 来源。
5. Trace 汇总动态计算，优先保证去重、迟到数据和查询筛选正确；当前不提前引入缓存汇总表或消息队列。
6. 官方 OTel Exporter → 本机 HTTP 服务 → 真实 PostgreSQL 为主要验证链路；内存替身只用于协议/故障的组件测试。
7. 本地 Compose 仅启动 PostgreSQL 和 Collector，不增加空 Dashboard 服务。生成 OpenAPI 文档与运行说明供后续 UI 对接。

文件布局：`collector/src/aegis_collector/{api,ingestion,storage}`、Collector 本地包与 CLI、SDK 可选 exporter 配置、`tests/integration/`、`deploy/docker/`、根 Compose。

先写 spec 和契约，再开发与验证；任何行为调整先修改相应契约并说明原因。新依赖版本、数据库镜像摘要与验证证据在 tasks 中记录。

# Collector 与可复现依赖

查阅与验证：2026-10-14。SPEC-002 沿用 SPEC-001 的映射与 OTel 1.45.1，将原生 Agent / Tool 完成 Span 经官方 HTTP Exporter 发送到 FastAPI，保存到 PostgreSQL 16.15。

[OTLP](https://opentelemetry.io/docs/specs/otlp/) 的 HTTP binary Protobuf、partial success 和可重试响应形成传输依据；编码使用官方生成的消息，未自造 JSON 协议。[Python Exporter](https://opentelemetry-python.readthedocs.io/en/latest/exporter/otlp/otlp.html) 的具体超时/重试按安装版本源代码和可控网络服务验证。仅声明本项目支持子集。

[Psycopg](https://www.psycopg.org/psycopg3/docs/basic/usage.html) 的事务上下文与参数绑定用于存储，[PostgreSQL INSERT](https://www.postgresql.org/docs/18/sql-insert.html) 的 ON CONFLICT 用于 first-write-wins。参考文档版本为 18，实际数据库测试为 16.15，不能据此声称验证了 18。SQL 由包内迁移维护，不复制两份脚本。

[FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) 的 TestClient 用于协议边界测试；真实网络互通另用 Uvicorn 和官方 Exporter，真实存储另用独立 schema。异常与验证错误返回固定消息。

官方索引访问不稳定时，使用 PyPI 版本 JSON 的文件 URL 和 SHA256 校验，再离线安装。资源只保存来源与原创笔记，下载缓存放忽略目录。

- [Windows wheel 来源](../downloads/python-windows.json)：32 个 wheel；setuptools 使用已安装且锁定的开发环境版本。
- [Linux wheel 来源](../downloads/python-linux.json)：33 个 wheel，包含完整构建依赖；二进制位于忽略的 deploy/docker/wheelhouse。
- [官方 Python 镜像来源](../downloads/python-image.json)：Registry manifest/config/layer 摘要与实际 Python 版本。导入 Docker archive 后本地 manifest 可重新生成，上游摘要保持独立记录。
- [机器来源索引](../sources.json)：对应官方文档与精确版本。
- [SPEC-002 验收](../../specs/002-collector/tasks.md)：33 个方法与 Compose 实测结果。

默认 tag 可变化；锁定 wheel 版本不意味着 Docker tag 永久固定。后续发布应锁定完整基础镜像链并复验，当前不发布公共包或镜像。

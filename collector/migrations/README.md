# 数据库迁移位置

SQL 随 Collector Python 包分发，唯一维护位置为 storage/migrations：[001_initial.sql](../src/aegis_collector/storage/migrations/001_initial.sql) 建原生表，[002_llm_spans.sql](../src/aegis_collector/storage/migrations/002_llm_spans.sql) 扩展 CLIENT chat 约束，保留 v1 数据。

仓库根目录配置 `AEGIS_DATABASE_URL` 后执行 `python -m aegis_collector migrate`；启动时也可用 `serve --migrate`。迁移在事务与 advisory lock 内执行，可重复/并发运行、不删除已有数据；未来未知版本拒绝并回滚。readiness 要求迁移集合 {1,2}。基础规则见 [存储契约](../../specs/002-collector/contracts/storage.md)，升级与验收见 [SPEC-004](../../specs/004-openai/tasks.md)。

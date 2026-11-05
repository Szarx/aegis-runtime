# PostgreSQL 存储契约 v1

默认应用 schema 为 `aegis`。测试 schema 为测试创建的唯一名称，测试只删除自己创建的 schema。

`schema_version` 保存迁移版本，当前为 1；`spans` 的结构如下：

| 列 | 类型 |
| --- | --- |
| trace_id / span_id | CHAR(32) / CHAR(16)，复合主键 |
| parent_span_id | 可空 CHAR(16)，无父子外键 |
| name / operation / kind / status | 受限文本，kind=INTERNAL，status=UNSET/ERROR |
| service_name / agent_name | VARCHAR(128)，agent_name 可空 |
| start_time_ns / end_time_ns | BIGINT，正值且结束不早于开始 |
| resource / scope / attributes / events | JSONB，已过滤的 metadata |
| resource_schema_url / scope_schema_url | VARCHAR(256)，可空字符串 |
| received_at | TIMESTAMPTZ，服务端写入时间 |

插入采用 `ON CONFLICT (trace_id, span_id) DO NOTHING`。Span 的内容在第一次成功写入后保持不变，所有接受的记录在一个事务提交之后才确认接收。

索引包括时间、Agent、Service，主键支持 Trace 详情。Trace 列表按实际 Span 动态分组，过滤先确定匹配 Trace，再汇总其完整 Span，避免筛选后丢掉工具节点。

最早开始、最晚结束、Span 数量、Agent 名称集合和错误状态均为派生统计。分页查询在同一只读 REPEATABLE READ 事务中获取总数和条目；分页本身不提供跨请求快照。

数据库连接上限等待 3 秒，SQL statement_timeout 为 5 秒；不引入 Redis、SQLite 或另一个存储后端。迁移 SQL 只有一个可打包的规范来源，重复运行不删除数据。

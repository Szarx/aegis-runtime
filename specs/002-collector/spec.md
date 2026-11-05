# SPEC-002：OTLP Collector 与 PostgreSQL 查询

- 日期：2026-10-13。
- 范围：Phase 1A 的 SDK → Collector → PostgreSQL 链路。
- 状态：契约确定；实现和验证见 [tasks.md](tasks.md)。

## 用户场景

已有原生 Python Agent 使用 SPEC-001 的装饰器，增加 Collector endpoint 后，将执行记录保存到数据库；重启 Collector 后仍可查询，网络失败不重跑业务工具。Dashboard、LLM 与框架适配继续留给后续 spec。

## 传输与支持范围

采用标准 **OTLP/HTTP binary Protobuf**，`POST /v1/traces`，Content-Type 为 `application/x-protobuf`，基线为 OpenTelemetry Python 1.45.1 和查阅的 OTLP 1.11.0。具体请求/响应见 [传输契约](contracts/otlp.md)。

此次只保存 `scope.name=aegis`、`aegis.mapping.version=aegis.genai.v1`、INTERNAL 的 `invoke_agent` / `execute_tool` 完成 Span。其他领域 Span 单独拒绝并计入 partial success，不声明通用 OTel Collector 兼容。暂不支持 gRPC、OTLP JSON、压缩请求、其他信号或原始内容采集。

SDK 新增 `init(service_name, endpoint=..., export_timeout_millis=3000, headers=...)`。endpoint 是完整 `/v1/traces` URL，只接受 http / https、无用户名密码、查询参数或 fragment。endpoint、output_path、自定义 exporter 三选一；本地模式保持原有行为。OTLP 依赖为可选安装项。

网络使用官方 HTTP Exporter 的序列化与有限重试；只重传遥测。SDK 保持有界后台队列，flush / shutdown 的等待期限独立于网络请求。网络恢复与超时测试使用合成 Span 和可控 HTTP 服务。

export_timeout_millis 为 1–30000 的整数；headers 为不含换行的字符串映射，只有指定 endpoint 时才可提供。

## 接收与隐私

请求上限 1 MiB，单批最多 512 个 Span；超过限制整批拒绝。空请求成功；不可解码请求返回 400。逐 Span 验证标识、时间、范围、字符串长度与必要操作字段，详细规则见传输契约。

服务端仅保留允许的资源、属性、异常类型与 schema URL；不保留参数、输出、异常消息、堆栈、认证头或其他未知字段。metadata 名称应为静态配置；服务端不承诺检测名称中所有可能的敏感内容。

有效 Span 在一次数据库事务中写入；数据库不可用返回可重试 503，不先返回成功。无效 Span 与有效 Span 混合时，保存有效部分并用标准 partial success 报告拒绝数量和固定的诊断消息。

## 存储与一致性

使用 PostgreSQL，数据库契约见 [storage.md](contracts/storage.md)。唯一键为 `(trace_id, span_id)`，已完成 Span 不更新，重复上报按 first-write-wins 幂等处理。父 Span 缺失或迟到不拒绝子 Span，也不使用父子外键。

Trace 汇总按已存 Span 动态派生，保留所有关联 Span；迟到父节点会自动反映在详情和统计中。成功状态 UNSET，任一 Span 为 ERROR 则 Trace 状态 ERROR。未采集 Token / 成本，不显示为零。

迁移显式执行或用启动参数开启。迁移具有版本记录，可重复执行，不删除已有业务数据；未知迁移版本停止初始化。测试使用专属临时 PostgreSQL 与独立 schema，不复用其他项目数据。

## 查询与运行

查询 API 见 [query-api.md](contracts/query-api.md)：Trace 列表支持分页、Agent / Service / 状态与时间筛选；详情返回排序后的 Span 与缺失父标识。数据库连接和 SQL 语句有有限超时。

默认本地开发监听 `127.0.0.1`。支持可选 Bearer token；配置后接收和查询都需认证。没有多租户、角色或生产网关。健康检查区分 liveness / readiness，错误响应不回显数据库地址、认证头或载荷。

此增量提供 PostgreSQL + Collector 的本地 Compose；发布端口只绑定回环地址，数据库卷持久化。Docker Compose 启动是本地开发，尚未包含 Dashboard。

## 验收条件

| 编号 | 要求 | 验证 |
| --- | --- | --- |
| AC-201 | 标准 Protobuf 请求与响应可互通 | 真实官方 OTel HTTP Exporter 向服务发送 SPEC-001 示例 |
| AC-202 | 混合无效 Span 正确部分接收，坏数据/超限不写入 | 解析 partial success / Status，检查数据库计数 |
| AC-203 | 重传不会覆盖记录或重复计数 | 同一请求重发、同标识改变内容、并发重传 |
| AC-204 | 跨 Store / 服务重建保持持久化，迁移幂等 | 真实 PostgreSQL，重建实例与重复迁移 |
| AC-205 | 乱序 Span 与外部父节点可查询，迟到更新汇总 | 子先父后，检查缺失父、Span 计数与状态 |
| AC-206 | 列表/详情筛选、稳定排序与分页正确 | 多 Trace、边界分页、未知 Trace 和非法参数 |
| AC-207 | 网络错误只影响遥测，超时与重试有界 | 可控 503 / 400 / 失联服务；业务只执行一次 |
| AC-208 | 服务端去除敏感内容且错误不泄漏载荷 | 构造原文属性、异常消息、认证头与非法数据 |
| AC-209 | 认证与健康检查符合约定 | 正确/缺失 token、数据库失联和健康接口 |
| AC-210 | 本地部署和原生示例可复现 | Compose / 临时数据库、迁移、接收、查询与 SDK 回归 |

## 依赖与限制

FastAPI、Uvicorn、Psycopg 3、官方 OTLP HTTP Exporter 与 Protobuf 依赖锁定于验证清单。Python 3.11+ 是目标，本次实际环境另行记录。使用本机缓存的官方 PostgreSQL 16 镜像验证，实际版本与镜像摘要写入验收记录；其他版本不自动声明已验证。

环境调整记录：官方 18.6 镜像下载超时，采用已缓存的 PostgreSQL 16，保持 PostgreSQL 持久化与原有数据契约，不引入替代数据库。

此阶段不提供完整平台 UI、Token / 成本统计、生产认证授权、保留/删除任务、审计不可篡改、框架兼容或审批控制。下一份 spec 设计 Dashboard 的列表与 Trace Tree / Timeline。

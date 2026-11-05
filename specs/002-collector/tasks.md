# SPEC-002 任务与验证

状态：已验证（2026-10-14）。

- [x] T201：维护范围、OTLP、存储、查询契约与实现方案。
- [x] T202：SDK endpoint / 官方 OTLP Exporter、配置与回归。
- [x] T203：Protobuf 接收、过滤、partial success、认证与输入上限。
- [x] T204：PostgreSQL 迁移、幂等写入与动态查询。
- [x] T205：本地 CLI / Compose 与网络示例入口。
- [x] T206：真实数据库与 HTTP Exporter 互通、故障和 SDK 回归验收。
- [x] T207：生成 OpenAPI、更新依赖、资源、产品文档与验收证据。

## 验证记录

运行环境：Windows Python 3.12.14；Collector 镜像内 Python 3.12.15、UID 10001；真实 PostgreSQL 16.15（x86_64 Linux musl）。OpenTelemetry SDK / HTTP Exporter 1.45.1，FastAPI 0.143.0、Uvicorn 0.54.0、Psycopg 3.3.6、Protobuf 7.36.2。完整依赖见根目录 requirements-dev.lock，pip check 无冲突。

PostgreSQL 官方镜像固定为 `postgres@sha256:3c5c8892d184f738f4fe282d14ddaa613a38f00f4189d2d94725ebe6f2909ddb`。Python 基础镜像来自官方 Registry，manifest/config/layers 和 diff IDs 校验后导入本机；上游 digest 与本地 Docker archive 生成的 manifest 不混用，见 [来源记录](../../resources/downloads/python-image.json)。

### 自动化验收

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector -v
```

SDK 19 个方法通过（1.883 秒），包含 SPEC-001 原 15 个及 4 个网络故障/配置测试。示例 CLI 改动后定向重跑 ac09，1 个方法通过（0.295 秒）。Collector 协议 7 个通过（0.231 秒）。API 声明调整后，真实 Compose PostgreSQL 下的集成 7 个完整通过（3.058 秒），未跳过。共 33 个不同测试方法；这些记录来自分次执行，不伪称一次总测试运行。

最初事务回滚夹具错误地在 ALTER CHECK 中使用参数占位符；改为 Psycopg SQL Literal 后，定向及完整集成套件均通过，业务实现未通过改契约规避失败。Starlette 对当前 httpx TestClient 的弃用提示不影响通过结果；后续升级需重新验证。

| AC | 已通过证据 |
| --- | --- |
| 201 | 官方 OTel Exporter → 真实 Uvicorn → PostgreSQL；空请求及标准 Protobuf 响应 |
| 202 | 无效/不支持 Span partial success、编码错误、Body/批次上限、metadata 边界 |
| 203 | 请求重发、相同 ID 改内容不覆盖、8 次并发提交仅写入一次 |
| 204 | 重复迁移、Store/API 重建、未来版本拒绝、整批事务回滚；Compose 重启保留数据 |
| 205 | 子先父后、外部父缺失、迟到后统计与父子关系更新 |
| 206 | 整 Trace 筛选、稳定排序、分页越界与时间边界、非法/未知 ID、SQL 注入字符串 |
| 207 | 503 恢复重传、400 不重试、慢服务有限超时；业务执行计数保持一次 |
| 208 | 丢弃原文与未知字段、只保留异常类型；错误消息不含数据库或请求内容 |
| 209 | 缺失/正确 Bearer、数据库失败 503、liveness/readiness 分离 |
| 210 | 安装后的 Collector 包含迁移；Compose 构建、健康检查、原生网络 CLI、查询与重启 |

### Compose 演示

隔离项目 `aegis-spec002-check`，HTTP/PG 发布到随机回环端口（本次 32769 / 32768），不使用其他项目容器或数据库。命令以 [部署说明](../../deploy/docker/README.md) 为准，验收时覆盖端口为 0。

- 镜像构建成功，服务等待数据库健康并完成启动迁移，两项健康检查通过。
- 原生示例：成功与预期 LookupError 各一次，2 Trace / 4 Span；accepted/exported=4，其余失败、丢弃、pending 计数为 0。
- 成功 Trace：`e74b03fc98d3827ea3ad8162bd277de3`；失败 Trace：`a81c8715f84e4bc48b2fd668a3f906e0`。每个 Trace 两个 Span、无缺失父节点。
- 重启 Collector 后，相同 Trace 仍可查询，计数和父子结构保持一致。合成响应保存在忽略的 artifacts/collector-demo/，不是源代码依赖。
- 验证完成后停止本次隔离 Compose 服务，保留其数据卷；不自动删除其他项目资源。
- 最终镜像重新构建并健康启动；其 `/openapi.json` 与仓库冻结副本一致，认证、持久化及父子结构再次核对通过。

文档检查：40 份 Markdown、123 个本地链接有效，17 个唯一官方来源；依赖锁与已安装环境一致，临时环境、下载缓存及合成运行产物已被 Git 忽略。

### 资料与限制

直接 PyPI 索引和 Docker 拉取多次超时；通过官方版本 JSON / Registry 取得对应文件、校验哈希并离线安装/构建，未切换未经核对的镜像源。32 个 Windows 和 33 个 Linux wheel 的 URL/版本/哈希分别保存于 [下载索引](../../resources/notes/collector.md)，二进制缓存不入 Git。

[OpenAPI 副本](contracts/openapi.json) 已从应用生成；查询参数错误为 400，接口文档不声明默认 422。当前仅支持原生 Aegis Agent / Tool 完成 Span，未实现通用 Collector、Dashboard、LLM、Token/成本、框架、治理拦截或生产多租户。其他 Python/数据库版本未验证。下一增量先设计 Dashboard spec。

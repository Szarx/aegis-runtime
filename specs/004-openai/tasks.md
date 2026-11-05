# SPEC-004 任务与验证

状态：离线验收完成，2026-10-17；用户明确选择“先完成离线验证，真实调用另行验收”。

- [x] T401：先维护范围、支持矩阵、流生命周期与数据契约。
- [x] T402：安装 OpenAI 3.33.0 / HTTPX2 2.13.1，核对官方客户端与 SSE 实现；锁定 39 个 Python 包。
- [x] T403：实现同步/异步客户端与流代理、元数据、上下文隔离和 finish-once。
- [x] T404：Collector v1/v2 共存、迁移 2、查询整数 Token、旧数据保留与 readiness。
- [x] T405：Dashboard LLM / Token / outcome 与默认离线、可选 live 示例。
- [x] T406：SDK / 协议 / PostgreSQL / 前端回归、8 组合真实 HTTP 离线链路与浏览器验收。
- [x] T407：更新官方资源、Windows / Linux SHA256 下载凭据、锁文件、产品文档与当前 OpenAPI。
- [ ] 真实 Provider 调用：用户指定另行验收；本轮没有配置模型、未发起 live 请求。
- [ ] 真实 LangGraph 接入与首次接入耗时：下一增量独立 spec。

## 环境与执行

Windows Python 3.12.14；OpenTelemetry 1.45.1 / semconv 0.66b1；OpenAI 3.33.0；HTTPX2 / HTTPCore2 2.13.1；FastAPI 0.143.0；PostgreSQL 16.15。Windows Node 22.23.2 / npm 10.9.8；Docker Node 22.23.3 / npm 10.9.9。Vue / Vite 等前端依赖沿用 SPEC-003 锁文件。

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm -v
cd dashboard
npm test
npm run build
```

| 验收 | 证据与结果 |
| --- | --- |
| AC401–405 | SDK 32 个方法通过（原 19 + 新 13）；真实官方 SDK 合成 JSON/SSE，响应/事件和异常对象、原参数、SDK 重试、配置、同步/异步流、EOF/close/context/error/cancel、并发上下文、消费者 Tool 归属、缺失/零/非法/重复 usage、隐私与观测故障覆盖 |
| AC406 | Collector 10 个协议方法通过（原 7 + 新 3）；真实 PostgreSQL 10 个方法通过（原 7 + 新 3）；schema1→2 保留原生数据、重复/并发迁移、未来版本回滚、类型/事务/幂等与查询 |
| AC407 | 独立 Compose 项目 aegis-spec004-check，三个服务健康；Responses / Chat × sync / async × stream / non-stream 共 8 次 CLI 调用，8 Trace / 24 Span；所有诊断 exported=3、failed/dropped/instrumentation_failures=0 |
| AC407 UI | 真实 Dashboard 同源代理查询 8 条 Trace；浏览器选择 LLM 节点，确认 Agent 父、Tool 兄弟节点、request/response model=offline-model、input=7/output=3、chat.completions/stream/completed、费用未估算；1280×900 桌面布局与窄屏可用，截图 artifacts/openai/dashboard-llm.jpg |
| AC408 | 前端 20 个方法、vue-tsc 与 Windows/Docker Vite 生产构建通过；SDK wheel 实际构建、隔离目录安装后可导入 aegis.openai 与 integrations.openai；pip check 无冲突；Markdown 链接、资源与依赖锁一致性已检查 |

Python 共 52 个方法，前端 20 个，合计 72；CLI、浏览器、构建和打包检查单独记录，不重复计为测试方法。数据库测试设置了 AEGIS_TEST_DATABASE_URL，实际执行且没有跳过。测试仅清理自己创建的 schema。

本轮示例请求曾省略 endpoint 的 /v1/traces，被 SDK 配置校验拒绝；修正命令后 8 种组合全通过。前端首次类型检查发现解码器 kind 未收窄，修正后严格构建通过。浏览器 fullPage 截图接口不可用，已用可见区域截图保存证据。

## 结果与限制

离线验收覆盖真实官方客户端的 HTTP/SSE 解析与平台链路，不代表真实模型、收费、服务端重试/限流或框架兼容性。仅声明本次固定版本与明确支持的 create API；客户端/Stream 是代理，不保持原类型身份。Chat 流需调用者启用 include_usage；用量缺失不补零，未增加 Trace 汇总或费用估算。提前停止流需显式关闭，不承诺 GC 清理。

004 当前 [OpenAPI](contracts/openapi.json) 扩展 operation / kind / 整数属性；002 历史快照不覆盖。官方资料及下载 SHA256 见 [资源笔记](../../resources/notes/openai.md)。验证产物和依赖缓存被 gitignore 排除；独立测试 Compose 最后停止，未删除持久卷。

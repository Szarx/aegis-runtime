# SPEC-009 任务

状态：最小 allow / deny 控制与限定范围验收完成，2026-10-18。没有新增真实模型请求。

- [x] T901：冻结策略、身份绑定、优先级、失败行为与遥测/授权区别。
- [x] T902：Policy / Runtime 包与受保护 sync/async 工具入口。
- [x] T903：SDK governance、Collector 校验与 Dashboard 展示。
- [x] T904：拒绝零次副作用、故障、并发、隐私及兼容回归。
- [x] T905：示例、真实 HTTP/PostgreSQL/浏览器验收。
- [x] T906：wheel、构建、资源、基础文档及证据。

## 运行基线

Windows / Python 3.12.14，沿用 59 个第三方 Python pin 和 npm 锁定版本；没有新增第三方依赖。新增本地分发 aegis-runtime-policy / aegis-runtime-control，均 0.1.0.dev0，未公开发布。Policy 纯标准库，Runtime 依赖本地 Policy 和 SDK；核心 SDK 不依赖它们或可选框架。

## 自动化结果

| 范围 | 方法数 | 新增 | 结果 |
| --- | ---: | ---: | --- |
| Policy | 5 | 5 | 严格输入、不可变快照、三元组、deny 优先与默认拒绝 |
| Runtime | 7 | 7 | 零副作用/一次执行、缺配置/求值故障、返回/异常/取消、并发、追踪故障与真实 ToolNode |
| SDK | 59 | 2 | 全量通过，包含 v4、隐私、无 SDK 上下文和原三种映射 |
| Collector 协议 | 18 | 3 | 全量通过，四种 mapping 共存与治理字段/状态配对 |
| 真实 PostgreSQL | 14 | 1 | 全量通过，无跳过，去重/状态/父子与旧查询形状保持 |
| Onboarding | 8 | 0 | 现有接入验证器回归通过 |
| Dashboard | 26 | 3 | 全量通过，阻止与工具错误分别解释、旧权限不冒称执行控制 |
| 合计 | 137 | 21 | 111 Python + 26 前端，子场景/CLI/人工/构建不重复计数 |

SDK 约 3.759 秒、协议 0.390 秒、Runtime 1.139 秒、Policy 0.002 秒、数据库 9.649 秒、Onboarding 0.374 秒、前端 1.47 秒。TypeScript 严格检查、Windows Vite 和 Docker Collector/Dashboard 生产构建通过；618 模块，gzip CSS 5.08 KB、列表 36.68 KB、详情 160.03 KB。

```text
python -m unittest discover -s policy-engine/tests -v
python -m unittest discover -s runtime/tests -v
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream tests.integration.test_governance -v
python -m unittest tests.contract.test_onboarding -v
```

数据库命令使用专用 Docker PostgreSQL 的 AEGIS_TEST_DATABASE_URL，创建并删除独立随机 schema。Runtime 的 ToolNode 方法使用实际编译 StateGraph 驱动框架上下文，handle_tool_errors=True 后拒绝成为框架错误消息但受保护工具仍零执行；没有用模拟框架回调替代。

AC901 对应五项 Policy 方法；AC902–903 对应 Runtime 七项方法及 SDK governance，验证工具参数中的 subject 无法覆盖宿主身份、SDK 未初始化/关闭、追踪 start 故障不绕过/重跑；原业务异常与取消对象保持。AC904 对应协议三方法、SDK v4 白名单及数据库新方法。AC905–906 对应以下实际平台、前端、wheel 和文档。

Runtime 同一故障方法后来补充实际 Exporter 抛错场景并重跑七方法通过（约 1.865 秒），允许仍一次、拒绝仍零次，failed_spans 诊断可见；不把子场景/重跑另计为方法。框架测试明确关闭测试进程 LangSmith 跟踪，Runtime 本身不修改宿主遥测环境。

## 示例与实际平台

```text
python examples/runtime-policy/agent.py
python examples/runtime-policy/agent.py --async
```

每组四次工具尝试：allow 执行 1 次 / 显式 deny 0 次 / no_match 默认拒绝 0 次 / allow 后业务异常 1 次。使用内存计数与合成返回值，没有真实业务数据库或模型。策略让 blocked-agent 同时匹配 allow/deny，证明 deny 优先。参数与异常正文未写入遥测。

在独立 aegis-spec009-check Compose 项目中，实际运行两组 --endpoint：共 8 Trace / 16 Span、8 个独立 action ID，4 个 allow / 4 个 deny；outcome 为 completed=2 / denied=4 / error=2。两个 SDK 均 accepted=exported=8，failed/dropped/pending/export_failures/instrumentation_failures 为零，flush/shutdown 成功。查询和直接 PostgreSQL 均确认数量、父子、ERROR=6 / UNSET=2，迁移仍 {1,2}，三个服务健康。graph_outcome 为 null 与普通非图流式场景一致。

实际浏览器看到工具“已阻止”、explicit_deny 原因、blocked-agent、orders.read、demo-v1 / deny-blocked 与 action ID，并提示工具未执行；另打开允许后业务异常记录，确认“已允许”与 ValueError / error 分开显示。截图为 artifacts/runtime-policy/dashboard-denied.jpg；合成 CLI / 查询 / wheel 元数据同目录，均被 Git 忽略。无凭证的仓库摘要见 [validation.json](validation.json)。

## 打包与交付

SDK / Policy / Runtime 三个 wheel 均成功构建、隔离安装，导入来源确认为目标目录。无 SDK 初始化时默认拒绝仍执行零次；import 不加载 OpenAI、LangGraph、FastAPI 或 Psycopg。wheel 文件 SHA256 在 validation.json；pip check 无冲突。

当前 OpenAPI 结构未变，仍与 [007 快照](../007-langgraph-stream/contracts/openapi.json) 一致；不新增 SQL 迁移。新 mapping 需要配套 Collector，旧服务会拒绝。原 aegis.tool permission 标签与调用语义保持，仅 runtime.tool 保护的入口执行控制。

Policy/Runtime 文档、README、架构、路线图、数据与集成设计已同步。采用 [ADR-0003](../../docs/adr/0003-runtime-authorization.md)，官方原则依据见 [研究笔记](../../resources/notes/runtime-policy.md)；来源索引新增 OWASP，现 32 个唯一官方 ID，不改写历史下载凭据。

验收后浏览器标签已关闭，aegis-spec009-check 已 down，确认剩余同项目容器为 0、数据库卷保留；没有操作其他 Docker 项目。没有新增真实 Provider 请求。身份仍由可信宿主提供，不提供外部用户认证、租户隔离或进程沙箱；异步遥测不是持久审计。人工审批、恢复与远程策略仍未实现。

最终交付检查通过 76 份 Markdown / 302 个本地链接、32 个唯一官方来源、59 项已安装 Python pin 和历史两平台下载凭据、npm pin、未变 OpenAPI、189 个源文件/文档/配置的凭证模式扫描，以及截图、wheel 和临时安装目录的忽略规则。

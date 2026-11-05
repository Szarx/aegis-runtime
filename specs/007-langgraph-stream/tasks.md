# SPEC-007 任务

状态：限定范围开发与离线平台验收完成，2026-10-18。未追加真实模型请求。

- [x] T701：读取官方 streaming 文档，冻结懒启动、上下文、关闭和数据契约。
- [x] T702：同步/异步图流代理、finish-once 与消费者上下文隔离。
- [x] T703：Collector graph mapping、查询 graph_outcome、Dashboard 状态。
- [x] T704：真实框架生命周期、模式、隐私与相关回归测试。
- [x] T705：离线 CLI / HTTP / PostgreSQL / 浏览器验收。
- [x] T706：wheel、构建、OpenAPI、产品文档与证据更新。

## 环境与自动化

Windows Python 3.12.14；LangGraph 1.2.15 / langchain-core 1.6.12 / prebuilt 1.1.1；OpenAI 3.33.0 / OTel 1.45.1；Node 22.23.2。沿用 SPEC-006 的 59 项 Python 锁定依赖与两平台来源凭据，本轮没有新增依赖。

| 范围 | 方法数 | 结果 |
| --- | ---: | --- |
| SDK | 57 | 全量通过；新增 10 方法，真实图、生命周期、身份与上下文等 |
| Collector 协议 | 15 | 全量通过；新增 3 方法，mapping 配对、隐私、旧数据共存 |
| 真实 PostgreSQL | 13 | 全量通过，无跳过；新增 1 方法，状态/生命周期归约与旧数据 null |
| Dashboard | 23 | 全量通过；新增 3 方法，summary 解码、枚举和图 Badge |
| 合计 | 108 | 85 Python + 23 前端；子场景、CLI、构建与人工操作不重复计数 |

SDK 全量约 2.965 秒，协议约 0.274 秒，数据库约 53.166 秒。之后扩充 SDK 同一 10 个新增方法内的 callbacks、消费者与异步清理子场景并定向重跑通过，不把重复运行计为新方法。生产实现没有因此改变。

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream -v
```

数据库命令需 AEGIS_TEST_DATABASE_URL 指向专用 PostgreSQL；本次真实执行创建并删除独立随机 schema。前端 npm test / npm run build 对应 vitest、vue-tsc 与 Vite；本机直接调用同一 Node 入口绕过 cmd 子进程限制，严格类型和生产构建通过，Docker 中标准 npm 构建也通过。

AC701–703 对应 SDK 的 test_graph_stream.py：真实 updates / values / 组合、v1/v2、custom、with_config/callbacks、懒启动、无消费关闭、EOF/关闭/错误/取消/清理故障、并发与消费者隔离。AC704 对应本地 JSONL v3、协议三个 mapping 与状态配对、隐私及观测故障。AC705–706 对应真实数据库、前端、以下 CLI 与页面、wheel/构建/OpenAPI。

## CLI 与实际平台

```text
python examples/langgraph/stream.py
python examples/langgraph/stream.py --early-close
python examples/langgraph/stream.py --fail-tool
python examples/langgraph/stream.py --async
python examples/langgraph/stream.py --async --early-close
python examples/langgraph/stream.py --async --fail-tool
```

实际验收将每条命令附加本机测试 Collector 的 --endpoint。六组均运行 baseline / traced，两者 chunk 序列、模型/工具次数一致。完整消费/框架处理错误每遍 2 模型 / 1 工具、4 Span；首次 chunk 后关闭每遍 1 模型 / 0 工具、2 Span。全部 flush / shutdown 成功，失败、丢弃、pending、导出失败、观测失败为零。两种模型 Token 为 7/3 合成值，不能当作真实用量。

额外实际运行真实图传播工具 ValueError（3 Span）与等待节点取消（1 Span）。合计 8 Trace / 24 Span；graph_outcome 为 completed=4 / closed=2 / error=1 / cancelled=1，status 为 ERROR=4 / UNSET=4。实际 HTTP 核对所有子节点 parent ID、两种状态筛选、关闭图无 Tool、白名单无图内容。工具错误已由框架处理时图 completed、Trace ERROR，分别保留。

浏览器核对列表 8 条记录 / 24 节点、完成/关闭/异常/取消文案、UNSET 筛选“无异常”。关闭详情为 astream / closed，只有图和一个模型，提示“已提前停止消费，未确认完整执行。”截图在 artifacts/langgraph-stream/dashboard-list.jpg 与 dashboard-closed.jpg；原始 CLI 和 HTTP 摘要在同目录，均为忽略的本机合成验收产物。可随仓库维护的无凭证摘要见 [validation.json](validation.json)。

Windows vue-tsc/Vite 和 Docker Collector/Dashboard 镜像通过；压缩后 CSS 5.08 KB、列表 36.47 KB、详情 159.52 KB。SDK wheel 在隔离目标安装并导入新的可选 LangGraph 包通过。当前 [OpenAPI](contracts/openapi.json) 与 create_app(None).openapi() 对比，历史 004 快照保留。数据库继续迁移 {1,2}，无新增迁移。

## 边界与清理

完整公开契约见 [stream.md](contracts/stream.md)。messages 只转发，不宣称原生 ChatModel 自动 Token；事件投影、batch、checkpoint/interrupt/resume、分布式恢复、框架内真实 Provider 与新用户接入耗时没有验收。EOF 仅证明当前迭代结束；提前关闭不回滚，也不保证停止框架无法终止的后台工作。

本轮没有使用真实凭证或新增 Provider 请求；160 个源文件/文档/配置的凭证模式扫描通过。交付检查通过 66 份 Markdown / 248 个本地链接、31 个唯一官方来源 ID、59 项已安装 Python pin 与两平台下载凭据、npm pin、OpenAPI 和隐私约束；pip check 无冲突。

浏览器验收标签已关闭。专用 Compose 项目 aegis-spec007-check 的最后清理尝试发现 Docker Linux Engine 管道已不可用，down 未执行成功；未删除容器或卷，不能声称已完成 Compose 资源清理。Docker 恢复后可在仓库根目录执行 `docker compose -p aegis-spec007-check down`，保留持久卷；不要加 -v。此前真实数据库、HTTP、构建和浏览器验收已成功完成，不受清理状态影响。官方参考见 [研究笔记](../../resources/notes/graph-stream.md)。

2026-10-18 后续：用户启动 Docker 后，在 [SPEC-008 平台续验](../008-onboarding/tasks.md) 开始前已实际完成该项目 down，并用 volume inspect 确认数据库卷保留。原失败记录保留，validation.json 另有 cleanup_follow_up 记录解决状态。

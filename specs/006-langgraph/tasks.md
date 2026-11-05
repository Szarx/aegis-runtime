# SPEC-006 任务与验证

状态：首批显式接入和真实框架离线验收完成，2026-10-17。未追加真实模型请求。

- [x] T601：先读取官方 quickstart / streaming，维护范围、公开接口与验收契约。
- [x] T602：固定并安装 LangGraph 1.2.15 / core 1.6.12 / prebuilt 1.1.1；59 包 Windows/Linux 官方 wheel SHA256 来源。
- [x] T603：显式图代理与真实 StateGraph / ToolNode 示例，保留业务图和原回调。
- [x] T604：同步/异步、并发/嵌套上下文、回调/config/context、错误/取消、身份、隐私与观测故障通过。
- [x] T605：真实 HTTP / PostgreSQL / Dashboard 闭环，接入改动与本机缓存耗时记录。
- [x] T606：相关回归、wheel、锁文件、资源与产品文档同步。
- [ ] 图流式 / event-stream、checkpoint/interrupt 恢复、批处理、自动全节点和原生 ChatModel Adapter：后续增量。
- [ ] 框架内真实 Provider 与新用户 5 分钟接入体验：独立验收。

## 实测环境

Windows Python 3.12.14；LangGraph 1.2.15；langchain-core 1.6.12；langgraph-prebuilt 1.1.1；checkpoint 4.3.0；langgraph-sdk 0.4.8；langsmith 0.14.11。OpenAI 3.33.0 / HTTPX2 2.13.1、OTel 1.45.1、PostgreSQL 16.15、现有 Vue/Vite 前端不变。原 39 pins 版本均保留，新增 20，共 59；pip check 无冲突。

## 结果

| AC | 证据 |
| --- | --- |
| 601 | 实际安装并运行 StateGraph / ToolNode，使用条件边执行模型→工具→模型；Provider transport 合成，未调用外部模型或 LangSmith |
| 602–604 | SDK 47 方法通过（原 38 + 新 9）；新增 Runtime context 检查后定向 9 方法再次通过。参数与返回/异常身份、callbacks、config、with_config、幂等、并发隔离、嵌套父、处理/传播工具错误、真实取消、关闭观测与追踪故障覆盖 |
| 605 database | 真实 PostgreSQL 12 方法通过（原 11 + 新 1），实际设置 AEGIS_TEST_DATABASE_URL，没有跳过。官方 SDK / 真实图→OTLP→数据库→查询验证 4 Span、父子关系、类型与隐私 |
| 605 CLI | sync/async × success/handled-tool-error 四组 baseline / traced 对照均 equivalent=true、model_calls=2/tool_calls=1；经真实 HTTP 产生 4 Trace / 16 Span，各 exported=4、failed/dropped/instrumentation_failures=0 |
| 605 UI | 浏览器核对 langgraph-order-agent、两 LLM 与一 Tool，Provider deepseek、7/3 合成 Token；错误工具 builtins.ValueError 可定位，Agent 仍正常而 Trace 汇总 ERROR。截图 artifacts/langgraph/dashboard-tool-error.jpg；错误 Trace 37dadf7445a4cb0f8156f9e668fbbc4e |
| 606 | Collector 12 协议方法回归通过，现行 OpenAPI 与 004 快照一致；Docker 59 包离线安装和三服务健康通过；SDK wheel 构建并隔离安装可导入 aegis.langgraph；核心 import 不加载 LangGraph；依赖/资源/文档链接校验通过 |

本轮 47 SDK + 12 协议 + 12 数据库 = 71 个 Python 方法。前端源码未变化，沿用 SPEC-005 的 20 方法与生产构建，本轮不重复执行或冒称新测；Compose 使用缓存前端镜像并做实际浏览器验收。独立方法累计 91，CLI、打包和人工操作不重复计数。

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm -v
python examples/langgraph/agent.py --endpoint http://127.0.0.1:8000/v1/traces
python examples/langgraph/agent.py --async --fail-tool --endpoint http://127.0.0.1:8000/v1/traces
```

## 接入与计时

最小示例 3 个 import + 3 个接入语句，共 6 行新增；初始化/导出/清理另计，见 [差异契约](contracts/integration.md)。这是本示例的最小改动，不是任意成熟项目的通用保证。

| 模式 | baseline+traced 对照执行 ms | 同一对照到首次 flush ms |
| --- | ---: | ---: |
| sync success | 251.231 | 276.528 |
| sync handled error | 196.073 | 216.699 |
| async success | 221.494 | 245.356 |
| async handled error | 223.860 | 245.599 |

计时在依赖已装、平台已启动的本机缓存环境，包含两次图构造/执行、不含安装和人工修改；不能作为 5 分钟首次接入验收。原始测量在 artifacts/langgraph/measurements.json，查询证据在 artifacts/langgraph/http-query.json。

采用公开调用边界而非自动 callback 适配：当前只追踪显式 Agent / Wrapper / Tool，不发现所有图内部步骤。返回代理不保持原图类型。stream / batch 等委托不自动创建 Agent Span，返回图也不保证继续包装。完整能力与限制见 [spec](spec.md)。本轮不触碰真实 Key，005 的 6 请求授权已经用完；实际框架与合成模型不等于框架内真实 Provider 验收。

临时测试项目 aegis-spec006-check 最后停止并保留持久卷；只清理测试创建的 schema。来源及依赖凭据见 [资源](../../resources/notes/langgraph.md)。

# SPEC-005 任务与验证

状态：本增量离线与限定范围真实验收完成，2026-10-17。

- [x] T501：先核对 DeepSeek 当日官方模型与接口，维护 spec / plan。
- [x] T502：Provider 参数、可选 DeepSeek 工厂与官方 SDK 离线测试。
- [x] T503：Collector 校验、真实数据库、Dashboard Provider 显示。
- [x] T504a：默认离线与显式 live 示例、合成工具循环准备完成。
- [x] T504b：用户明确批准后，6 个真实 deepseek-flash 请求全部成功；真实数据库、查询和浏览器核对。
- [x] T505：回归、构建、打包、文档与来源索引。

## 验收证据

环境沿用 SPEC-004：Windows Python 3.12.14、OpenAI 3.33.0、HTTPX2 2.13.1、OTel 1.45.1、PostgreSQL 16.15、Vue 3.5.44 / Vite 8.3.4。无依赖版本变化；新增 deepseek optional extra 复用 OpenAI。

| AC | 结果 |
| --- | --- |
| 501–502 | SDK 38 个测试方法通过（原 32 + 新 6）：独立凭证环境、Provider / copy / wrap、官方 JSON/SSE 四模式、最终 choices chunk usage、隐私、错误对象、取消/关闭与工具执行一次 |
| 503 | Collector 协议 12 方法通过（原 10 + 新 2）；真实 PostgreSQL 11 方法通过（原 10 + 新 1）；OpenAI / 原生数据与迁移回归，DeepSeek Provider 与整数用量持久化 |
| 504 | 用户明确批准最多 6 请求后，四种基础模式 + 两轮工具循环全部成功，max_tokens=128 / thinking disabled / max_retries=0；合计额外 5 Trace / 16 Span，导出失败/丢弃/观测故障均为 0，真实数据库与浏览器核对通过 |
| 505 CLI | Compose 项目 aegis-spec005-check 三服务健康；4 种 Chat 离线模式各 3 Span，工具循环 4 Span，共 5 Trace / 16 Span；exported 均与 accepted 相同，失败/丢弃/观测故障均为 0 |
| 505 UI | 真实 Dashboard 浏览器查看 deepseek-tool-agent：1 Agent、2 LLM、1 Tool；模型节点 Provider=deepseek、模型 offline-deepseek、input=7 / output=3、completed，费用未估算；截图 artifacts/deepseek/dashboard-provider.jpg |
| 505 build | 前端 20 方法通过、vue-tsc 和 Vite 生产构建通过；Docker 前后端构建与健康检查通过；SDK wheel 实际构建并隔离安装后可导入 aegis.deepseek；pip check 与文档/资源校验通过 |

本轮共 61 Python + 20 前端 = 81 个测试方法。CLI、浏览器、构建不重复计数。数据库测试实际设置 AEGIS_TEST_DATABASE_URL，没有跳过；仅清理测试自有 schema。现行 OpenAPI 与 004 快照一致，没有 API 结构或 SQL 迁移变动。

## 命令与环境处理

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm -v
```

Windows 的 npm 默认 cmd 子进程出现 EACCES，直接执行相同 node 入口通过：

```text
node node_modules/vitest/vitest.mjs run --pool=threads
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node node_modules/vite/bin/vite.js build
```

受限环境运行异步 CLI 挂起后已停止该会话，在允许本地 socket 的测试执行环境重跑成功。最初复用 004 wheel 隔离目录遇 Windows 文件访问限制，改用新的 005 安装目录后通过，未删除旧验收产物。

## 本轮真实验收与授权边界

首次受限执行 APIConnectionError，随后网络执行因历史离线范围被自动审批拒绝。用户随后明确回复“批准本轮最多 6 个真实请求”，再次审查后执行成功；没有绕过拒绝。共执行 4 种调用组合 + 两轮合成工具循环，每请求 max_tokens=128、max_retries=0、timeout=30、thinking disabled。仅发送合成问候和固定 demo-order；Key 通过隐藏输入进入临时进程，不写入源码、命令、文件或遥测。本轮 6 请求额度已用完，没有额外测试调用。

DeepSeek 当前限定范围的真实验收已完成；OpenAI Provider、thinking 专属行为、DeepSeek Responses / Search / Anthropic 和 LangGraph 仍分别待验收。官方来源见 [研究笔记](../../resources/notes/deepseek.md)。临时 Compose 停止且保留持久卷。

真实四组合用量各 input=11/output=1；工具循环两个 LLM 分别 299/35、94/16，总计输入 437 / 输出 55 Token。这是六次请求实际返回的用量相加，非平台汇总能力，也不代表账单或价格估算。工具恰好执行一次，服务 deepseek-live-verification 的 5 Trace / 16 Span 与模型元数据、父子关系一致。真实工具 Trace：629cc933607bd1744f9e9c72ac3e96b8；截图 artifacts/deepseek/dashboard-live.jpg，查询 artifacts/deepseek/live-http-query.json。安全可提交结果见 [live-validation.json](live-validation.json)。

独立自动化回归仍为 81 方法，六次真实请求作为人工授权验收另计，不冒充自动化方法数量。现有代码在真实调用中未发现需改动问题，没有为了更新文档重复消耗 Provider 请求。

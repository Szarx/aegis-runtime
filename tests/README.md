# Repository Validation

安装与依赖见 [SDK](../sdk/python/README.md) / [Collector](../collector/README.md)，使用 unittest：

```text
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s collector/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream -v
```

最后一条需设置 AEGIS_TEST_DATABASE_URL 指向专用真实 PostgreSQL。未设置会跳过；测试创建并删除独立随机 schema，不使用应用 schema。Windows 上可将 TEMP / TMP 指向仓库忽略的 tmp。

SPEC-004 已通过 SDK 32、Collector 协议 10、真实 PostgreSQL 10，共 52 个 Python 方法；包括官方 SDK JSON/SSE 解析、流关闭/取消/错误、上下文、隐私、用量和 schema1→2 数据保留。测试计数按方法，不把子场景或人工操作重复计数。

前端在 dashboard 中执行 npm ci、npm test、npm run build：20 个测试、严格类型和生产构建通过。另有 8 种默认离线 CLI 组合经真实 HTTP / PostgreSQL / Dashboard、浏览器模型节点验证，以及 SDK wheel 打包与隔离安装检查。

合成 transport 能验证官方 SDK 的协议行为，不能替代真实 Provider 或 LangGraph；SPEC-004 时点两项尚未验收，后续证据见下文。明细见 [SPEC-004](../specs/004-openai/tasks.md)，历史 33 方法及原生 Dashboard 证据保留在 002/003。`fixtures/` 仅含合成数据；contract 含 SPEC-008 快速开始验收器测试，e2e 目录留待后续自动化扩展。

## SPEC-005 当前回归

同一组命令现通过 SDK 38、Collector 协议 12、真实 PostgreSQL 11，共 61 个 Python 方法；前端 20，总计 81 个。新增 6 个 SDK、2 个协议、1 个数据库方法。JSON/SSE transport 来自官方 SDK 解析，覆盖 DeepSeek 最终 choices 同 chunk usage、Provider 分类/复制、独立凭证、错误身份、取消/关闭与合成工具循环。

另验证四组合 CLI 和工具循环经真实 HTTP 链路产生 5 Trace / 16 Span，浏览器展示 Provider、用量、父子关系，SDK wheel 独立安装可导入 DeepSeek。另有 6 个 DeepSeek 真实请求已成功，形成额外 5 Trace / 16 Span，详见 [005](../specs/005-deepseek/tasks.md)。Windows npm 默认 cmd 子进程 EACCES 时，已直接使用 node 运行 vitest / vue-tsc / vite 同一入口完成验证，Docker 生产构建也通过。

## SPEC-006 当前回归

SDK 47（新增 9）、Collector 协议 12、真实 PostgreSQL 12（新增 1），本轮共 71 个 Python 方法通过。新增方法真实运行 StateGraph / ToolNode，覆盖同步/异步、并发/嵌套上下文、config / context / callbacks、身份、传播/处理异常、取消、隐私与观测故障。前端未变，沿用 SPEC-005 的 20 方法证据，不声称本轮重新执行前端测试。

另有四个 baseline / traced CLI 对照、真实 HTTP / 数据库 / 浏览器、59 个 Python pin / 两平台 SHA256 下载凭据、wheel 隔离安装与核心可选 import 检查。未新增 Provider 请求；详见 [006](../specs/006-langgraph/tasks.md)。

## SPEC-007 当前回归

同一组命令当前通过 SDK 57（新增 10）、协议 15（新增 3）、真实 PostgreSQL 13（新增 1），85 个 Python 方法；前端本轮重新运行 23（新增 3），共 108 方法。SDK 新增方法覆盖真实图模式/格式/custom、回调、懒启动、关闭/取消/清理异常、消费者与并发上下文、身份、隐私和观测失败。数据库测试不跳过，使用专用 Docker PostgreSQL 的随机 schema。

六组 CLI 接入前后对照和两个边界场景产生 8 Trace / 24 Span，另有 HTTP 状态筛选、浏览器列表/关闭详情、Windows 类型/Vite、Docker 构建与 wheel 隔离安装。CLI/构建/人工验证不重复计入方法总数。零新增真实模型请求；证据和复现步骤见 [007](../specs/007-langgraph-stream/tasks.md)。

## SPEC-008 当前增量

新增 `python -m unittest tests.contract.test_onboarding -v` 的 8 个方法，最终在 Python -O 下也通过，包括实际进程超时、失败后停止、损坏 Trace、计数/用量/父子校验与凭证输出隔离。native / langgraph 两套全新 venv 从本地官方缓存完成安装与真实离线示例，空缓存按预期失败；没有重跑未改动的 SDK/Collector/UI 全套。前序 108 方法沿用 007 证据，累计 116 个独立方法不等于本轮全量执行。详情见 [008](../specs/008-onboarding/tasks.md)。

SPEC-008 Docker 恢复后另完成独立项目/新库的真实平台续验：3 Trace / 8 Span、三服务健康、迁移 {1,2}、查询状态/父子、浏览器原生/模型节点及分阶段计时；未新增自动化方法，也未重复计入既有测试数量。两个测试项目容器清理完成、卷保留，见 [平台记录](../specs/008-onboarding/platform-validation.json)。

## SPEC-009 当前回归

当前方法：Policy 5、Runtime 7、SDK 59、Collector 协议 18、真实 PostgreSQL 14、Onboarding 8，共 111 Python；前端 26，总计 137。此轮均实际执行，数据库无跳过，新增 21 方法。命令在原回归基础上增加：

```text
python -m unittest discover -s policy-engine/tests -v
python -m unittest discover -s runtime/tests -v
python -m unittest tests.integration.test_collector tests.integration.test_llm tests.integration.test_graph_stream tests.integration.test_governance -v
```

Runtime 中实际 StateGraph / ToolNode 验证为可选框架方法，本轮装有锁定依赖、真实执行通过。CLI/浏览器/打包不计入方法数；默认拒绝计数、策略失效、并发、身份/返回/异常、隐私与四种 mapping 共存见 [009](../specs/009-runtime-policy/tasks.md)。

## SPEC-010 审批准备

2026-10-18 实际通过 Policy5、Runtime14、SDK59、Collector协议/API22、真实PG19、Onboarding8，共127 Python；前端31，总计158，新增21。新增Runtime7、API4、PG5、前端5，按独立方法计数。数据库无跳过；Windows异步/回环通信需允许本机进程访问。迁移测试当前集合为{1,2,3}，旧快照留作历史。

PG入口在前述命令加入 tests.integration.test_approvals；覆盖绑定幂等/冲突、并发决定、过期、schema2升级与服务重建。Runtime客户端实际回环HTTP验证重定向/超时失败，批准记录不能覆盖默认拒绝。四个本地wheel、Windows/Docker构建与浏览器合成批准/拒绝另行验证，不加入方法数。

2026-10-20 完成服务停止/重启后原数据和到期投影复核、测试项目清理且保留数据库卷；没有将历史全部自动化声称为当日重跑。完整证据见 [010](../specs/010-approval-records/tasks.md)。

## SPEC-011 同步执行审批

2026-10-20 实际通过Policy5、Runtime23、SDK59、Collector协议/API26、真实PG26、Onboarding8，共147 Python；前端35，总计182方法，新增24。新增入口tests.integration.test_reviewed，数据库无跳过；最后输入边界修正另针对性重跑Runtime9方法，不重复计数。

覆盖完整参数/默认值/版本与策略绑定、3角色隔离、新旧协议不可升级、schema3→4、并发唯一领取、完成幂等、过期、领取/确认未知和业务异常身份。实际HTTP/浏览器合成成功1次、部分失败1次、拒绝与丢失领取响应0次；重建/重启后重试仍无新增副作用。四个wheel、Windows/Docker构建和类型检查另记，不计入方法数。完整证据见 [011](../specs/011-reviewed-execution/tasks.md)。

## SPEC-012 异步执行审批

2026-10-20本增量实际执行Runtime33项、真实HTTP/PG相关9项，共42项通过，无PG跳过；新增Runtime10、PG2共12方法。旧011的182方法中30方法本轮重跑，其余152方法沿用已完成证据，因此方法目录累计194，不声称本轮全部194重跑。前端与服务端协议未改，沿用011的35项前端/生产构建证据。合成CLI、wheel、安装、协议/迁移核对另计。见 [012](../specs/012-async-reviewed-execution/tasks.md)。

## SPEC-013 LangGraph审批恢复

2026-10-20本轮Runtime46、HTTP/PG相关9，共55独立方法通过；新增Runtime13、PG2共15。旧194中40重跑、154沿用，目录累计209；不重复计入首批12或修正OTLP二进制响应测试后重新运行的2项。前端/服务端协议未变，前端35项与生产构建沿用011。首个PG运行的1个错误是测试把OTLP二进制响应当JSON解析，修正测试后2个新方法通过；生产代码未因此改变。示例/wheel/安装另记，见 [013](../specs/013-langgraph-reviewed/tasks.md)。

## SPEC-014 持久图与独立进程

2026-10-22本轮Runtime54、相关真实HTTP/PG13（含4个新增进程方法），共67独立方法通过；新增Runtime8/PG4共12，旧209中55重跑/154沿用，目录累计221。子场景、子进程及复跑不重复计数；前端35项和构建沿用011。Windows测试核对ticket必须显式UTF-8，sqlite3连接上下文只结束事务而不关闭，两个测试辅助连接改为closing；生产路径关闭/读取逻辑未因此改动。详见 [014](../specs/014-durable-graph/tasks.md)。

## SPEC-015 异步图

本轮Runtime65与真实HTTP/PG17，共82方法通过；新增Runtime11/PG2共13，旧221中69重跑/152沿用，目录累计234。新异步示例10次独立子进程；014旧47次子进程亦回归，子场景/进程/复跑不重复算方法。前端35项及构建沿用011。本轮无UI/SQL变更、无模型调用。证据见 [015](../specs/015-async-graph/tasks.md)。

## SPEC-016 已有Agent配方

SDK59、接入契约12（旧8+新4）、Runtime基础7，本轮78个方法通过，无跳过。旧234中74重跑、160沿用，目录238；子场景/8组CLI不重复算方法。无核心包/SQL/UI变更，包安装/PG/页面证据沿用015及其历史来源。见 [016](../specs/016-existing-agent/tasks.md)。

## SPEC-017 接入预检

18项接入契约通过（旧12+新增6），旧238中12重跑/226沿用，目录244。实际doctor CLI当前/无site-packages/既有独立核心环境、三profile及可选配置检查核对，其他环境没有015缓存venv时不要求该本机附加场景。核心包/SQL/UI未改，历史证据按016/015来源继承。见 [017](../specs/017-preflight/tasks.md)。

## SPEC-018 统一验证入口

`python scripts/check.py`逐组件子进程运行，避免重复模块名；`--postgres`需要专用AEGIS_TEST_DATABASE_URL并加入全部集成测试，skip不算通过。GitHubCI使用同一入口，首次远端运行待验证。前端独立npm test/build。候选工作树检查用scripts/repository_check.py，有限模式不等于完整秘密审计。见 [018](../specs/018-private-repository/tasks.md)。

## SPEC-019 Trace用量

本轮43个前端方法全部通过，新增8；类型/构建通过，真实浏览器基于生产构建+合成API核对大整数/未知/0/无模型四种情况。累计254方法，211个Python沿用018而非本轮重跑；API/SQL/SDK未改。见 [019](../specs/019-trace-usage/tasks.md)。

## SPEC-020 安全事件

全部221个Python方法与51个前端方法重跑，共272，无跳过。新增Collector6、真实PG4、前端8；新API认证/校验/固定故障、旧011契约精确保留、过滤/分页/时间边界/null/去重/隐私、无损解码/取消/过期响应/SSR状态均验收。真实SDK→HTTP→PG的25次治理尝试和生产浏览器分页/筛选/空结果/Trace关联独立核对，不将这些子场景重复计入方法数。见[020任务](../specs/020-security-events/tasks.md)。


## SPEC-021 导出与离线核验

新增12个契约方法、1个真实HTTP/PG方法。全部234个Python与51个前端重跑，285方法通过、无跳过；多页101条/筛选100条与停服后verify由真实CLI验收。纯标准库核验独立执行，不新增页面/镜像/模型验收。见[021证据](../specs/021-security-export/tasks.md)。

## SPEC-022 策略工作台

新增Policy7、Runtime1、契约2共10方法。244 Python与51前端全部重跑，295方法通过，无跳过；实际CLI、同步/异步14次Runtime尝试、两个示例进程及独立Policy wheel的-I/-S验收通过。原策略/审批行为保持，不新增服务/UI/真实模型验收。见[022证据](../specs/022-policy-workbench/tasks.md)。

## SPEC-023 策略变更评估

新增Policy8、Runtime1、契约1共10方法。254 Python与51前端全部重跑，305方法通过、无跳过；实际CLI的0/1/2退出码、32次Runtime前后尝试/10次业务调用和逐Span对照、独立Policy wheel的-I/-S与旧命令兼容均验收。见[023证据](../specs/023-policy-comparison/tasks.md)。

## SPEC-024 事件策略回放

新增契约8、真实PG1共9方法。263 Python和51前端全部重跑，314通过、无跳过；校验快照兼容、纯回放分类及保护、实际CLI、真实SDK/HTTP/PG导出25事件/停服回放两候选、独立Policy target的-I/-S均验收。原事件结果与候选决策分开，不新增工具执行或UI验收。见[024证据](../specs/024-event-policy-replay/tasks.md)。

## SPEC-025 统一配置接入

新增Runtime19、契约3、真实PG1共23方法。286 Python与51前端全部重跑，337通过、无跳过。配置/资源所有权/并发/异常/取消，八组合真实原生/框架进程、8事件平台导出/停服回放和全新核心venv安装一起验收；本机缓存安装不当作在线或人类耗时。见[025证据](../specs/025-application-onboarding/tasks.md)。

## SPEC-026 配置中的人工审核

新增Runtime12、契约1、真实PG3共16方法。302 Python与51前端重跑，共353通过，无跳过；真实sync/async独立进程审核恢复、确认提交后HTTP503/unknown、取消/失败/篡改、治理导出回放及全新核心/可选异步安装验收。更新回执故障场景后的3项PG复跑不重复计数。见[026证据](../specs/026-configured-review/tasks.md)。

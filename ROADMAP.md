# Aegis Roadmap

路线遵循：Foundation → Observability → Runtime Security → Risk → Ecosystem。阶段通过验收条件推进，当前不承诺具体日期。框架适配在核心契约稳定后逐步加入。

## 当前交付安排

045 已完成策略驱动的人工审批闭环。本轮按 [SPEC-046](specs/046-private-github/tasks.md) 验证并交付首次私有 GitHub 快照。

## Phase 0 · Foundation（已完成）

目标：将现有讨论整理为可继续开发的仓库。

- [x] 建立 README、架构、路线图与贡献指南。
- [x] 建立 SDK、Runtime、Collector、Policy、Dashboard、Examples 的目录与职责说明。
- [x] 记录候选接入 API、数据模型和端到端验收流程。
- [x] 明确已有能力、设计草案、后续能力和待确认事项。

验收：各文档与目录相互对应，读者能够确定首个实现任务、模块边界和验收方式。目录存在不表示功能完成。

## Phase 1 · Agent Observability MVP（闭环已实现，人工验收继续）

目标：原生 Python / OpenAI Agent → SDK → Collector → PostgreSQL → Dashboard 跑通，并在成熟框架中验证接入体验。

### 1A：最小垂直闭环

- [x] SPEC-001：冻结原生 SDK API、本地 Span 契约与 OTel / GenAI 映射基线。
- [x] 确认 Python 开发基线、锁定 SDK 依赖并提供本地安装配置。
- [x] SPEC-002：冻结 OTLP 接收、查询与数据库契约。
- [x] SPEC-003：锁定 Node / Vue / Vite / TypeScript / ECharts / 无损解析依赖。
- [ ] 公开分发名称与许可证。
- [x] 实现原生 Python Agent 入口与 Tool Span，支持同步和基本异步调用。
- [x] 实现有界本地批量导出、flush / shutdown 超时与失败诊断；原始内容不采集。
- [x] 实现网络 Exporter、传输超时与重传语义，按新 spec 验证。
- [x] 实现 Collector 校验、去重、持久化、Trace 列表与详情查询。
- [x] 提供 PostgreSQL 迁移和本地 Compose 配置；部署证据见 SPEC-002。
- [x] SPEC-003：Dashboard 列表、Trace Tree / Timeline、节点详情与同源 Compose 配置。
- [x] 提供无需外部模型凭证的可复现原生 Python 示例，验证成功与失败追踪。

SDK 19、Collector 协议 7、真实 PostgreSQL 集成 7，共 33 个方法通过，见 [SPEC-002 任务记录](specs/002-collector/tasks.md)。已验证 SDK → HTTP → PostgreSQL → 查询；SPEC-003 新增 17 个前端测试，并对真实 Collector / PostgreSQL 做浏览器验收，见 [任务记录](specs/003-dashboard/tasks.md)。原生 Agent 可视化链路已可运行；OpenAI Wrapper 已完成 SPEC-004 离线验收；OpenAI Provider 和框架内真实模型尚未完成，LangGraph 首批离线接入见 SPEC-006；DeepSeek 已在 SPEC-005 完成限定范围的真实调用验收。

验收：示例成功与失败执行均可按同一上下文在 Dashboard 中定位；Collector 不可达时不改变业务执行结果；重传不重复计数。详见 [MVP 验收方案](docs/design/mvp.md)。

### 1B：首批 LLM 与框架接入验证

- [x] OpenAI SDK Wrapper（SPEC-004 离线验收）：记录模型调用、时延、错误和实际可用的 Token 用量。
- [x] 离线验证同步、异步、流式支持矩阵；响应/事件及异常对象保持，客户端与 Stream 使用代理。
- [x] 将 OpenAI 默认离线示例接入 Collector / PostgreSQL / Dashboard，8 种组合通过。
- [ ] 真实 OpenAI Provider 调用：用户指定另行验收，开发者使用本机凭证和显式模型。
- [x] SPEC-006：真实 LangGraph StateGraph / ToolNode 的 invoke / ainvoke 离线接入，验证父子关系、错误传播、并发与行为一致。
- [x] SPEC-007：图 stream / astream 状态流、懒启动、提前关闭、异常/取消与平台展示。
- [ ] 框架内真实 Provider、事件投影：单独验收；单根checkpoint/interrupt恢复已由013–015限定范围交付。
- [ ] 测量首次接入耗时与修改行数，修正公共 API 与文档。
- [x] SPEC-008：独立环境快速开始、最小 profile 依赖、缓存安装到有效 Trace 及平台页面确认计时；人工与在线下载仍待验收。
- [x] SPEC-019：Trace已接收模型用量汇总，独立输入/输出完整度，未知不显示为零。
- [ ] 可选成本估算，另行定义价格来源与版本。

验收：至少一个已有 LangGraph Agent 在少量修改后形成 Agent / LLM / Tool Trace，结果和工具副作用与接入前一致；OpenAI 支持矩阵覆盖的调用方式通过验证。

基础接入目标是约 5 分钟，包含本地平台启动的完整体验目标约 10 分钟；必须实测，当前不是性能或易用性保证。

这一安排保留此前“Python、OpenAI、LangGraph 优先”的方向：Python 和 OpenAI 完成 MVP 核心，LangGraph 紧接着验证首个框架，不等待其他生态适配全部完成。

## Phase 2 · Runtime Security & Human Approval（最小控制当前）

目标：在受保护工具产生副作用前完成权限判断，治理决策可追溯。

- [x] SPEC-009：Action ID、显式受保护工具入口与调用前拦截，同步/异步执行计数验证。
- [x] SPEC-009：版本化本地精确匹配策略、deny 优先、默认拒绝与 allow / deny。
- [x] SPEC-010：审批动作绑定、持久化请求与独立人工决定；不执行工具。
- [x] SPEC-011：完整参数审阅、同步ReviewedTool单次领取/恢复、结果确认与未知不重试。
- [x] SPEC-012：异步工具单次恢复、取消传播、未知结果与可选HTTPX客户端。
- [x] SPEC-013：同步单个LangGraph根interrupt，精确checkpoint绑定和宿主驱动单次工具执行。
- [x] SPEC-014：官方SQLite本机持久checkpoint、独立进程恢复与五个退出边界。
- [x] SPEC-015：原生异步单根图、SQLite连接所有权与取消边界。
- [x] SPEC-045：Policy v2 require_approval、配置v4同步/异步策略工具、人工决定后显式单次恢复与治理事件关联。
- [ ] 多interrupt及生产多机checkpointer恢复。
- [x] SPEC-009：宿主构造绑定身份、严格不可变策略、规则优先级、缺配置/求值错误失败关闭。
- [ ] 外部用户认证/租户身份、远程策略更新与生产配置管理。
- [x] SPEC-010/011：审批请求持久化、Dashboard 审核、拒绝/超时与绑定校验。
- [x] SPEC-011–015：显式单次领取、未知不重试和本机单根图进程恢复；生产多机与跨系统恢复仍待设计。
- [x] SPEC-020：已接收治理事件关联Trace / Span / Action并展示Security Events；不等同于持久或不可篡改审计。

验收：被拒绝或未获有效审批的工具调用不执行；修改参数后不能沿用旧审批；审批流程失败不放行；通过测试工具证明副作用发生次数符合约定。

首版使用规则实现策略求值；OPA 等外部策略后端作为扩展评估。Risk Engine 不作为基础权限控制的前置条件。

## Phase 3 · Risk Engine

目标：在已有执行上下文与策略控制基础上补充可解释的风险信号。

- [ ] 风险事件模型、评分来源、原因与版本。
- [ ] 工具敏感级别、上下文与行为特征。
- [ ] 提示注入与异常行为检测的评估集及误报/漏报指标。
- [ ] Risk Center 与策略协同，明确检测失败时的处理。

验收：风险评分有可追溯依据，评估方法与局限公开；规则权限控制在风险模块不可用时仍按约定生效。AI 风险模型和自动攻击模拟按验证结果另行规划。

## Phase 4 · Ecosystem & Governance Expansion

- [ ] 进一步完善 LangGraph 与 OpenAI Agents SDK 的原生适配。
- [ ] 逐批扩展 LangChain、CrewAI、AutoGen。
- [ ] MCP Adapter / Security Gateway，单独定义网关部署与信任边界。
- [ ] Java SDK、Spring AI、Semantic Kernel 等语言与框架支持。
- [ ] 基于已记录数据的行为回放、审计保留与导出。
- [x] SPEC-021：已接收治理事件的有界JSONL/CSV排查包、汇总与离线完整性核验；审计保留/来源认证与回放另行设计。
- [ ] 根据负载与协调需求评估 Redis、ClickHouse、服务拆分。

验收：每个适配器有明确的版本与能力矩阵、示例和接入验证；核心 SDK 不强制安装所有框架依赖。回放历史不会重新产生真实工具副作用。

## 下一轮实现顺序

1. **已有Agent接入体验**：025–028整合配置、工具/审批、持久化图与状态流；继续按实际使用改进接入配方，并单独实测人工修改、在线安装与首次有效Trace耗时。
2. **框架适配扩展**：按需要定义原生ChatModel/事件投影或后续框架，保持显式接入、可选依赖及已有调用契约；不将图状态流当作模型Token流。
3. **审批治理深化**：单宿主同步/异步单根图和045策略审批已交付；多interrupt、生产多机协调和完成收据恢复仍需独立设计，不能从已有批准推断新授权。
4. **真实Provider验收**：用户配置本机凭证、模型及请求额度后另行安排；离线结果不替代真实调用。已批准的DeepSeek六请求额度不继续使用。
5. **私有开发仓库**：首次交付记录见 [SPEC-046](specs/046-private-github/tasks.md)。公开前需确定许可证与分发名称，并复核私有远端 CI。

每次提交完成一个可验证的结果，同时更新组件说明和相关设计文档。

## SPEC-005 · 用户指定 DeepSeek 增量

- [x] DeepSeek 可选构造入口、显式 Provider、Chat 同步/异步与流式离线支持。
- [x] 合成工具循环：两次模型 create、一次 orders.read 工具调用；无真实业务副作用。
- [x] Collector Provider 校验、真实 PostgreSQL 查询、Dashboard Provider 与 Token 展示。
- [x] SDK 38、协议 12、数据库 11、前端 20 个测试方法与生产构建通过。
- [x] 真实 deepseek-flash：用户明确批准最多 6 请求后，四模式与两轮工具循环全部成功；真实 Token、Provider、父子关系与数据库/浏览器一致。

用户希望使用 DeepSeek 验证新版本，已完成此 Provider 的限定范围接入与真实验证。LangGraph 已按 SPEC-006 完成首批离线接入；OpenAI Provider 真实调用也仍未验收。结果见 [005 任务](specs/005-deepseek/tasks.md)。

## SPEC-006 · 首个真实框架接入

LangGraph 1.2.15 / langchain-core 1.6.12 / prebuilt 1.1.1 已实际运行，模型使用官方 SDK 合成 transport。三个显式接入点不改图业务；同步/异步、成功/框架处理工具失败四组合输出与计数一致，每次 2 模型 + 1 工具，4 Span。SDK 47、协议 12、真实数据库 12 方法通过，浏览器核对 Agent / LLM / Tool 与错误。

本机缓存环境对照全过程到首次 flush 为 216.699–276.528 ms，只反映此合成示例，未完成新用户安装/接入 5 分钟体验测量，也没有新增真实模型调用。详细证据见 [006](specs/006-langgraph/tasks.md)。

## SPEC-007 · 图流式生命周期

真实 LangGraph stream / astream 的 updates / values、组合模式与 v1/v2 格式、custom 输出已验证。完整消费、提前关闭、传播异常、框架处理异常与取消均保持业务行为；图和消费者上下文隔离。Collector graph mapping、可空 graph_outcome 与 Dashboard 生命周期展示已完成，数据库不新增迁移。

SDK 57、协议 15、真实 PostgreSQL 13、前端 23，共 108 个测试方法通过；六组 CLI 对照与两个边界场景共 8 Trace / 24 Span，实际页面确认提前关闭与取消。Windows / Docker 构建、wheel 和当前 OpenAPI 通过。没有新增真实 Provider 请求；事件投影、恢复和新用户接入计时仍未验收。见 [007](specs/007-langgraph-stream/tasks.md)。

## SPEC-008 · 独立环境快速开始

一条命令创建新 venv、按 native / langgraph profile 安装本地 SDK 与必要依赖、运行示例并严格校验 Trace。两套新环境使用已有官方缓存，首次有效 Trace 分别为 33.623 秒和 177.311 秒；native 7 包、langgraph 46 包（含 pip/构建工具），没有强制安装 Collector/OTLP。8 项失败/完整性/隐私测试与实际空缓存停止验证通过；未新增真实 Provider 请求。

快速开始和分阶段 receipt 已交付，见 [步骤](docs/quickstart.md) 与 [008 验收](specs/008-onboarding/tasks.md)。Docker 恢复后已补齐新库/OTLP/页面续验，三服务健康约 26.2 秒、首次查询约 44.3 秒、列表与详情确认上界约 107.9 秒。在线下载与人工阅读/修改仍未计时，5 分钟人工接入/冷启动 10 分钟完整体验继续保持未验收。

## SPEC-009 · 工具权限控制

Policy/Runtime 可安装包、严格不可变策略、宿主身份、deny 优先/默认拒绝、同步/异步调用前控制已实现。生成器、任意规则表达式、自动框架发现、审批与恢复未实现。受控工具 mapping、Collector 与 Dashboard 决策展示通过；旧 SDK permission 标签仍不执行授权。

111 Python + 26 前端，共 137 方法通过；包括真实 LangGraph ToolNode 与拒绝零次副作用、缺配置/求值异常/遥测故障、真实数据库和兼容回归。同步/异步示例经 HTTP / PostgreSQL / 页面形成 8 Trace / 16 Span，allow=4 / deny=4；无真实模型请求。记录见 [009](specs/009-runtime-policy/tasks.md)。

## SPEC-010 · 审批准备与决定

本地参数 HMAC / 策略快照绑定、PostgreSQL 迁移3、独立 producer/reviewer 角色、受时效与行锁保护的决定记录，以及 Dashboard 审批准备已实现。批准记录不推动工具执行，不改变现有 allow/deny。验证范围见 [010](specs/010-approval-records/tasks.md)；完整人工暂停/恢复、生产身份与持久审计继续待验收。

## SPEC-011 · 同步工具单次恢复

新协议完整参数审阅、工具版本、独立执行角色与PostgreSQL迁移4；ReviewedTool在本地allow之外要求未过期批准和唯一领取，调用同步函数一次，结果确认失败保持unknown且不重试。旧010不可执行。实际合成批准/拒绝/部分失败/领取响应丢失及兼容证据见 [011](specs/011-reviewed-execution/tasks.md)。异步、图恢复、策略require_approval分支和跨系统恰好一次仍未验收。

## SPEC-012 · 异步工具单次恢复

复用011协议与迁移，新增可选原生HTTPX客户端和AsyncReviewedTool。领取/函数/确认阶段取消均不重试业务，可能已提交的领取保持未知；资源由宿主await关闭。实际执行42项相关自动化方法（含12项新增）及合成CLI，当前方法目录194项，其余历史证据不冒称本轮重跑。见 [012](specs/012-async-reviewed-execution/tasks.md)。

## SPEC-013 · 单个LangGraph审批中断

纯中断节点与宿主驱动防止节点重跑重复工具；稳定逻辑call action、完整snapshot绑定和HMAC完成收据已接入。实际55方法通过（新增15），方法目录累计209，其余历史证据不冒称本轮重跑。真实HTTP/PG、并发、响应丢失与宿主对象重建见 [013](specs/013-langgraph-reviewed/tasks.md)。跨进程checkpointer仍未验收。

## SPEC-014 · 本机持久checkpoint

官方SQLite、文件marker/版本、严格serializer与sync durability；真实独立进程而非同一saver对象恢复，退出后claimed/failed/completed都不重领。67项相关方法（新增12）通过，目录累计221，其余历史证据不冒称重跑。新增3可选依赖，旧59版本不变、开发基线62。见 [014](specs/014-durable-graph/tasks.md)。

## SPEC-015 · 原生异步审批图

原生aget_state/ainvoke和宿主await工具，完成前后checkpoint校验及取消传播；借入官方aiosqlite连接，沿用格式1与严格serde。82项相关方法通过（新增13），目录累计234，其余152项沿用历史证据。真实HTTP/PG/SQLite和10次新独立进程命令见 [015](specs/015-async-graph/tasks.md)。

## SPEC-016 · 已有Agent接入配方

独立LangGraph应用无Aegis导入，显式适配客户端/工具/图。8组同步/异步baseline/observe/allow/deny，allow/观测保持结果，deny工具零执行；记录真实LLM调用边界耗时及宿主机械行差异。78项相关方法（新增4）通过，目录累计238，其余160项沿用；真实Provider/人工接入/在线安装/新平台验收不在本轮。见 [016](specs/016-existing-agent/tasks.md)。

## SPEC-017 · 接入前元数据检查

标准库doctor、选定发行包版本/基线、显式审批宿主配置形状、敏感信息不回显和独占报告已实现。18项接入契约（新增6）通过，目录累计244；其余226项沿用。当前环境、纯标准库模式和已有独立核心环境CLI已核对；不代表import/传递依赖/业务/平台可用。见 [017](specs/017-preflight/tasks.md)。

## SPEC-018 · 私有开发仓库

私有仓库上传准备：统一测试命令、候选工作树检查、固定Actions提交的CI、许可证与公开门槛说明。达到本机验证门槛即告知用户；实际远端创建/首次CI/公开发布单独处理。见 [018](specs/018-private-repository/tasks.md)。

## SPEC-019 · 已接收模型用量

前端详情BigInt汇总及覆盖展示，不改API/SDK/SQL；43项前端测试（新增8）通过，类型/构建通过。目录累计254，其余211个Python方法沿用018。合成API浏览器核对，不冒充新增真实PG/Provider验收。见 [019](specs/019-trace-usage/tasks.md)。

## SPEC-020 · 安全事件完整闭环

交付跨Trace治理事件查询、身份/工具/权限/时间等组合筛选、分页、页面状态与Trace关联，以及无需LLM的合成Agent。真实SDK/HTTP/PostgreSQL和生产页面共同验收，OpenAPI仅追加路径/模型并精确保留011旧契约。新增18个方法，全部221个Python（含40真实PG）与51个前端回归，累计272；类型/构建及Collector安装验收见[020任务](specs/020-security-events/tasks.md)。

事件中心仍不提供可信身份、多租户隔离、不可篡改审计、保留/导出或大规模查询性能保证。后续SPEC优先按完整可用功能组织，先维护文档、再实现与统一验收。


## SPEC-021 · 治理事件离线排查包

标准库CLI按条件查询/有界分页，生成JSONL、CSV和计数/哈希清单，并离线核验。原接口/迁移/核心包/UI未改；不提供数据库快照或来源认证。新增13方法，234 Python（含41真实PG）+51前端，共285全部重跑通过。真实服务101条多页、100条筛选和停服后核验通过，见[021验收](specs/021-security-export/tasks.md)与[操作指南](docs/security-export.md)。审计保留/签名/可信身份仍另行设计。

## SPEC-022 · 策略开发与验收工作台

新增标准库Policy工作台与check/explain CLI：严格文件检查、匹配/选中规则解释、声明式用例验收、有限覆盖及独占JSON报告；示例将同一批用例交给同步/异步Runtime，拒绝零执行。新增10个方法，244 Python（含41真实PG）和51前端，共295全部通过。独立wheel安装后-I/-S执行通过，旧求值器字节保持；报告不参与授权或审批绑定。见[022验收](specs/022-policy-workbench/tasks.md)和[操作指南](docs/policy-workbench.md)。

## SPEC-023 · 策略变更影响评估

比较基准/候选规则结构及同一用例的前后决策，显示放宽、收紧、原因/规则变化和有限覆盖。任何规范配置差异或基准预期不符均要求审查，不自动启用策略。新增10方法，254 Python（含41真实PG）与51前端，共305全部重跑通过；真实Runtime前后计数与独立wheel的-I/-S验收通过。见[023验收](specs/023-policy-comparison/tasks.md)和[操作指南](docs/policy-comparison.md)。

## SPEC-024 · 已接收事件的离线策略回放

连接021导出和Policy纯求值，核验同次读取的快照后生成候选差异报告，保留原outcome及Trace/Span/Action。真实SDK/HTTP/PG导出25事件、停服后两候选对照，以及Policy独立target的-I/-S通过。新增9方法，263 Python（含42真实PG）和51前端，共314全部重跑通过。只重算策略决策，完整审计/原工具重执行/自动部署未实现。见[024验收](specs/024-event-policy-replay/tasks.md)与[操作指南](docs/event-policy-replay.md)。

## SPEC-025 · 已有Agent统一配置接入

本轮扩大为完整接入场景：配置/Policy快照、显式受控工具、SDK生命周期和检查、原生/真实LangGraph八组合、真实平台查询/导出/停服回放、全新核心环境安装一起交付。新增23方法，286 Python（含43真实PG）与51前端，共337全部重跑通过。原Runtime/审批实现保持，核心安装不强制框架/模型/OTLP依赖；不提供自动发现、多身份认证、stream托管或审批授权。见[025验收](specs/025-application-onboarding/tasks.md)与[统一指南](docs/application-onboarding.md)。

## SPEC-026 · 配置工具的人工审核与单次恢复

v2声明direct/reviewed与工具版本，防止统一入口降级；显式完整参数披露、借用sync/async客户端、独立审核角色和新进程单次恢复连成完整流程。新增16方法，302 Python（含46真实PG）与51前端，共353通过；已验证pending/拒绝/篡改零执行、批准一次、部分失败/取消/未知及独立安装。原审批协议、v1配置、服务/SQL/UI保持，见[026验收](specs/026-configured-review/tasks.md)与[指南](docs/configured-review.md)。

## SPEC-027 · 配置驱动的持久化审批图完整接入

v3明确reviewed_graph与工具/图版本，受会话租约保护的node/prepare/resume把真实LangGraph、同步/异步SQLite、独立进程、独立审核、业务单次执行、图继续和治理查询连成完整场景。新增13方法，315 Python（含49真实PG）与51前端，共366全部重跑通过；全新核心及图extra安装、错误/取消/unknown不重做和专用环境清理通过。原v1/v2、审批/图协议与服务/迁移/UI保持，不提供跨系统恰好一次。见[027验收](specs/027-configured-graph/tasks.md)和[操作指南](docs/configured-graph.md)。

## SPEC-028 · 统一图调用、状态流与模型/工具闭环

Application.graph限定四调用与with_config，首次拉取至EOF/清理成功持有租约；取消/异常身份、yield间上下文和清理失败后的显式关闭保持。真实StateGraph/ToolNode+官方SDK合成模型，20平台组合、12流格式组合、故障入库和16治理事件离线导出通过。新增15方法，330 Python（含51真实PG）与51前端，共381全回归通过；独立核心/图模型extra安装6组合、文档和专用环境清理一起验收。配置/原SDK/审批协议、服务/迁移/UI保持，见[028验收](specs/028-managed-graph-stream/tasks.md)与[指南](docs/managed-graph-stream.md)。

## SPEC-029–031 · 前端工作台与阅读效率

029参考官方产品模式，统一中性工作台/本地SVG/五类业务页与窄屏导航；030完成本页审批队列、展开确认重置、渐进筛选和ID复制；031完成节点查找/类型视图、键盘焦点与标准/紧凑密度。59前端方法、类型/构建和隔离真实服务浏览器验收通过；330 Python继承028，方法目录389，不声称每轮重跑后端。完整参数/审批绑定与bigint保持，见[设计与验收](docs/dashboard-design.md)。

## SPEC-032–035 · 前端质量、恢复与可复现演示

统一质量入口连接完整测试/类型/构建/资源预算和CI；页面模块失败可显式恢复，同条件刷新有旧结果提示，未知数量不按零处理；受测文字/目标尺寸与焦点补齐。合成演示CLI通过原接入入口准备Trace、模型用量、治理事件与可选待审核动作。035全部重跑339 Python（52真实PG）和64前端，共403通过，真实生产preview及演示浏览器验收完成，见[035记录](specs/035-dashboard-demo/tasks.md)。无新增服务协议/迁移或模型依赖，尚未运行远端CI。

## SPEC-036 · 安全事件查询到本页下载

固定白名单JSONL保留原始纳秒与null，CSV处理字段边界和受测公式前缀；页范围/实际条数/UTC文件名明确，查询中/错误/空记录禁用。真实preview下载首页20条及末页12条，两格式逐行对照DOM通过。68前端/类型/构建/预算通过，339 Python继承035，目录407。不是021可核验bundle或全部审计，见[036验收](specs/036-security-page-export/tasks.md)。

## SPEC-037 · 首屏信息层级与查询披露

两列表复用原生查询面板，窄屏初始收起、保留草稿与已应用计数。Trace收紧顶部、删除重复占位，用量/覆盖常驻、长解释可展开。真实1280首屏执行链/首节点可见，390px完整查询/清空/键盘和窗口变化状态保持通过。72前端/类型/构建/预算通过，339 Python继承035，目录411，见[037验收](specs/037-dashboard-hierarchy/tasks.md)。

## SPEC-038 · 审批排序与绑定阅读

两种收件箱共享本页排序、完整到期日期和查询快照；排序变化清除展开与参数确认，原批准协议保持。Action可复制、长绑定信息渐进披露。新pending真实确认重置/排序/复制和390px完整参数核对通过，无决定或领取。75前端/类型/构建/预算通过，339 Python继承035，目录414，见[038验收](specs/038-review-reading/tasks.md)。

## SPEC-039 · Trace节点定位与规范链接

严格Span深链、脱离会话的链接复制与重新认证定位；同Trace选择复用已加载/正在请求详情，外部节点定位、缺失提示和无效参数有明确行为。真实键盘/筛选/重载/历史/390px及5秒延迟竞争验证通过，正常服务保持。82前端/类型/构建/预算通过，339 Python继承035，目录421，见[039验收](specs/039-trace-node-links/tasks.md)。链接是标识，不是授权。

## SPEC-040 · 调用耗时排查

已接收模型/工具Span的最长20项排行，BigInt精确排序、0ns/未知/异常数据与近似比例明确，定位衔接树焦点和节点深链。真实排行→0ns工具→原始时间/复制、无额外查询及390px键盘验收通过。87前端/类型/构建/预算通过，339 Python继承035，目录426；无模型调用、服务协议或依赖变化，见[040验收](specs/040-call-duration/tasks.md)与[指南](docs/trace-reading.md)。

## SPEC-041 · 私有开发快照统一验收

安装后单命令检查依赖、有限候选、全部Python/专用PG与前端，独立报告、失败闭锁及前后源码摘要核对。435项（348 Python含52真实PG、87前端）完整通过，类型/构建/资源预算与哈希通过；失败旧轮记录保留。仍无远端CI、模型请求或公开授权，见[041验收](specs/041-snapshot-check/tasks.md)。接下来优先完善已有Agent的Collector连通性与首次数据排查。

## SPEC-042 · 已有Agent的平台连通性诊断

只读标准库命令分阶段检查live/ready、查询凭证和显式Trace/治理首页，固定分类与白名单报告。444项（357 Python含53真实PG、87前端）全回归及类型/构建/预算通过；真实SDK写入与读取计数、错误凭证/缺失/停服、python -S和不跟随重定向已验收。见[042验收](specs/042-platform-diagnostics/tasks.md)。下一项优先回到前端：Trace/安全事件查询的可复制地址、重新认证与历史导航，使筛选排查能跨刷新/会话复现；仍先冻结SPEC再开发与浏览器验收。

## SPEC-043 · 列表查询地址与恢复

Trace/安全事件已应用筛选和分页可复制、刷新重新认证与历史恢复，UTC边界保留；无效地址阻止查询，旧节点与审批地址保持。92前端/类型/构建/预算通过，真实生产preview、3秒迟到响应竞争和390px检查通过；357 Python继承042，目录449。见[043验收](specs/043-query-links/tasks.md)。按用户要求完成后停止，下一SPEC尚未开始。

## SPEC-044 · 关联Trace节点与来源返回

事件入口定位对应Span，Trace详情/加载/错误状态显式返回来源筛选与页码；节点选择保留来源，独立节点复制省略来源。白名单来源、刷新/独立认证、旧链接、真实preview与390px已验证；98前端/类型/构建/预算通过，357 Python继承042，方法目录455。见[044验收](specs/044-trace-return/tasks.md)。遵照每次继续一个SPEC，本轮完成后停止，045未开始。

## SPEC-045 · 策略驱动的人工审批闭环

Policy v2第三决策、配置v4与同步/异步策略工具，allow直接执行、deny零执行、需审批返回票据；人工决定后宿主显式恢复，绑定重验并永久领取一次。治理v2、Collector、页面关联和导出/策略工具一起支持；原生/真实StateGraph、新进程与独立安装、故障/取消/并发及真实页面通过。376 Python含57真实PG、102前端共478项完整回归，类型/生产构建/预算与运行时源码摘要一致。首轮测试服务器清理失败已修复并保留失败记录。边界和证据见[045验收](specs/045-policy-approval/tasks.md)。完成后停止，046未开始。

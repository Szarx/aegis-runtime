# SPEC-027 任务

状态：已验证，2026-10-25。

- [x] 冻结配置、持久图和故障/资源边界。
- [x] AC2701：v3配置与强制图绑定、只读检查/状态。
- [x] AC2702：同步/异步图生命周期管理与真实图契约。
- [x] AC2703：持久化独立进程示例、真实审核/恢复/事件闭环与故障验证。
- [x] AC2704：全新安装、全回归、文档证据及环境清理。

## 完整场景与实测

配置、租约、真实图装配、同步/异步SQLite、独立进程start/status/resume、审核角色、服务查询/事件/Trace、导出核验及全新安装一起交付。无服务API、SQL迁移、UI或底层审批/图协议变更。

新增13方法（Runtime9、契约1、真实PG3），原353全部重跑；315 Python（SDK59、Policy20、Runtime107、Collector32、契约48、真实PG49）与51前端，共366全部通过，无失败/错误/跳过。重复进程、测试内场景及后续受影响方法重跑不重复计数。

| AC | 实测证据 |
| --- | --- |
| 2701 | v3严格五字段、graph元数据与显式报告；旧v1/v2全部回归，程序化/文件不接受图模式降级，原026实际安装包拒绝v3；direct/reviewed入口不能绑定图项，图入口拒绝非图/重复/错误客户端/隐式披露 |
| 2702 | 真实StateGraph暂停零业务/网络；prepare后未批准零执行，批准一次并继续；改参数/精确checkpoint/图版本零claim；整个claim/业务/图继续期间close拒绝，关闭后prepare/resume/node拒绝；async同任务执行、取消归还租约而claim永久消费，借用客户端由宿主关闭 |
| 2703 | 真实HTTP/PG+独立sync/async进程，SQLite关闭后重开；无凭证/不可用端点status仍可读；完整最大int64参数审阅，pending/拒绝/篡改零执行，成功1次、图completed、重复零增量；Trace角色不能读审批，2治理事件关联恢复Trace，遥测无参数；导出后停服离线核验2条 |
| 2703故障 | 同步部分失败failed、异步部分取消claimed，业务各进入一次、图仍pending、重复不增加；图版本变更不执行，恢复原版本后原批准可执行一次。sync/async complete已提交后HTTP503回执丢失，宿主unknown/退出4，服务completed、图pending，重复不重做 |
| 2704安装 | 全新venv离线安装SDK015/Policy023/Runtime027 wheel，核心8分发（含pip）无HTTPX/LangGraph/OpenAI；v1/v2/v3只读检查通过、图依赖延迟导入，缺少extra时拒绝绑定且不注册；显式安装reviewed-langgraph-async后，真实sync/async SQLite关闭重开恢复共2次，合成transport无外网，pip check通过 |

Runtime wheel SHA-256：22befa3d71daf58ba54cef29dafc193b8f99c5c4b24c4f4f3544253f3f533ffe。原026 wheel中除application外所有Python源码字节保持，新增managed_graph；原SDK/Policy和图/审批驱动未改。UI类型/构建/浏览器与服务镜像证据继承020，不声称本轮重建或新增页面验收。

最终CLI错误输出补充固定兜底后，受影响3个真实PG方法再次通过。专用aegis-spec027-check健康、测试schema清零后移除自身容器/网络、保留卷，未动用户原有服务。机器证据见[validation.json](validation.json)；本机明细在artifacts/check及artifacts/configured-graph，包括安装、最终CLI重跑、Docker清理与前端报告。依赖62 pins、44来源、双平台缓存哈希/历史59收据、当前020 OpenAPI/旧011兼容保持，文档链接/候选集/pip check通过。

边界：完整参数在审批、ticket、checkpoint中明确披露；信任宿主和本地目录。本机单根单interrupt，业务确认与checkpoint非共同事务；unknown/失败/取消永久消费claim，不自动重试、恢复收据或补偿。不提供多机恰好一次、自动审核或身份认证。无真实LLM、在线安装/人工操作计时、GitHub创建/推送或远端CI。

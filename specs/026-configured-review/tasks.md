# SPEC-026 任务

状态：已验证，2026-10-25。

- [x] 冻结配置版本、完整披露、借用客户端与单次执行边界。
- [x] v2配置、强制绑定模式和生命周期管理句柄。
- [x] sync/async分进程示例与真实审核/治理链路。
- [x] 故障/兼容/安装/全回归及文档机器证据。
- [x] 临时环境清理和候选文件核对。

## 完整交付与回归

v2配置强制执行模式、sync/async生命周期句柄、只读检查/状态、独立客户端资源边界、分进程prepare/人工角色模拟决定/resume、完整参数隐私、真实平台/导出/回放和独立安装一起交付。未修改原审批服务、四迁移或旧客户端执行协议。

新增16方法（Runtime12、契约1、真实PG3），原337全部重跑；302 Python（SDK59、Policy20、Runtime98、Collector32、契约47、真实PG46）与51前端，共353全部通过，无失败/错误/跳过。补充真实HTTP回执故障与CLI unknown退出4后，相关3个PG方法再次通过；重复运行和CLI进程不重复计数。机器结果见[validation.json](validation.json)。

| AC | 实测证据 |
| --- | --- |
| 2601 | v1报告/配置保持，v2严格模式/版本字段；普通入口不能绑定reviewed，审核入口不能绑定direct或重复/未知项；显式披露/客户端类型失败不注册；原025安装包实际拒绝v2，不静默降级 |
| 2602 | 未批准及Policy deny零执行；批准一次/重复不增加；SDK租约覆盖claim与业务，关闭后句柄失效；业务异常身份保留、unknown不重试，async在原任务await、取消归还租约但claim永久消费，客户端关闭由宿主负责 |
| 2603 | 真实HTTP/PG+独立sync/async进程：prepare0次、pending0次、改参数0次、批准恢复1次、重复仍1、拒绝不增加；trace角色不能读审批，审核参数最大int64保持；成功2事件按action关联恢复Trace，遥测无参数，导出后停服回放2不变 |
| 2603故障 | 业务失败进入一次后为failed，async取消进入一次后为claimed未知；过期/改tool_revision不执行，恢复原版本后可按原批准执行一次。服务端complete已提交但HTTP503回执丢失，CLI退出4/unknown，查库completed，重复零增量；sync/async API同样验证unknown不重执行 |
| 2604 | 全新venv离线缓存安装SDK/Policy/新Runtime wheel，8核心分发（含pip）无HTTPX/图/模型依赖；核心v1/v2检查、同步审核绑定/默认拒绝通过。显式加reviewed-async extra后，用合成HTTP transport验证异步批准一次及宿主关闭借用客户端，pip check通过 |

Runtime wheel SHA-256：819034051d55a6aa3198a2c8dc20b4467f965d148da5833949d5835c8cc875b7。除application新增版本/绑定分支外，025旧Runtime Python源码（含原审批客户端/执行）字节保持，新managed_reviewed模块追加。SDK015/Policy023 wheel继承，不声称本轮重建这些包或新服务镜像。

本机明细：artifacts/check/result.json与tests.log、artifacts/configured-review-frontend.json、artifacts/configured-review/installation.json、docker.json和新环境产物。62 pins、44来源、双平台缓存哈希/历史59条收据保持，OpenAPI仍为020/旧011兼容；文档、候选文件和pip check通过。

专用aegis-spec026-check健康、测试schema清零后关闭容器/网络，卷保留，用户原有服务未动。无真实LLM、自动审核、部署或GitHub创建/推送/远端CI；前端测试重跑，类型/构建/页面证据继承020，人工GUI操作耗时未验收。

边界：恢复的是工具动作，宿主负责Agent后续流程；不自动继续任意图。配置和身份依赖可信宿主，原始函数仍可被宿主调用；完整参数披露不是默认采集。领取消费/取消/未知不可重开，不提供跨系统恰好一次或审计完整性保证。

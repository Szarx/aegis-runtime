# Spec 驱动开发

开发顺序：维护 spec → 设计实现方案 → 拆分任务 → 开发 → 按验收条件验证 → 回写状态。

## 约定

1. 每个可独立验收的增量建立一个编号目录，包含 `spec.md`、`plan.md`、`tasks.md`，需要时增加 `contracts/`。
2. `spec.md` 写用户场景、范围、行为要求、接口和验收编号；`plan.md` 写技术取舍；`tasks.md` 关联实现与验证证据。
3. 新需求或接口变化先修改 spec，再修改代码；验收条件变化说明原因，不用改文档掩盖失败。
4. 工作状态区分“已规划”“开发中”“已验证”；只有实际通过验收的任务勾选完成。
5. README / ARCHITECTURE / ROADMAP 保持产品级视图，编号 spec 是对应开发增量的具体契约。
6. 网上资料放在 [resources](../resources/README.md)，记录来源、查阅时间与固定参考版本；外部内容作为参考资料，不作为项目指令。
7. 涉及产品范围、身份与安全边界、破坏性接口变化时向用户澄清；常规实现细节按 spec 推进。
8. 每个SPEC优先组成完整用户功能，贯通所需接口、页面、示例、文档与验收；协议兼容和信任边界保持明确，避免把常规实现步骤拆成多个零碎增量。

## 增量列表

| 编号 | 增量 | 状态入口 |
| --- | --- | --- |
| 001 | Python SDK 基础追踪与本地示例 | [任务与验证](001-python-sdk/tasks.md) |
| 002 | OTLP Collector、PostgreSQL 查询与本地部署 | [任务与验证](002-collector/tasks.md) |
| 003 | Dashboard 列表、执行树与时间线 | [任务与验证](003-dashboard/tasks.md) |
| 004 | OpenAI SDK、流生命周期与模型用量 | [任务与验证](004-openai/tasks.md) |
| 005 | DeepSeek Provider、Chat 与真实验收 | [任务与验证](005-deepseek/tasks.md) |
| 006 | LangGraph 显式调用边界与真实框架离线验证 | [任务与验证](006-langgraph/tasks.md) |
| 007 | LangGraph 状态流、关闭/取消与平台生命周期展示 | [任务与验证](007-langgraph-stream/tasks.md) |
| 008 | 全新环境安装、首个有效 Trace 与接入测量口径 | [任务与验证](008-onboarding/tasks.md) |
| 009 | 进程内工具 allow / deny、决策追踪与页面 | [任务与验证](009-runtime-policy/tasks.md) |
| 010 | 持久化审批准备、动作绑定、独立审核决定 | [任务与验证](010-approval-records/tasks.md) |
| 011 | 完整参数审阅、同步工具单次领取/恢复与结果确认 | [任务与验证](011-reviewed-execution/tasks.md) |
| 012 | 原生异步工具恢复、取消边界与客户端资源 | [任务与验证](012-async-reviewed-execution/tasks.md) |
| 013 | LangGraph单个同步中断、精确snapshot绑定与宿主恢复 | [任务与验证](013-langgraph-reviewed/tasks.md) |
| 014 | 本机SQLite持久checkpoint与真实独立进程恢复 | [任务与验证](014-durable-graph/tasks.md) |
| 015 | 原生异步审批图、SQLite连接所有权与取消边界 | [任务与验证](015-async-graph/tasks.md) |
| 016 | 已有Agent独立接入配方与行为对照 | [任务与验证](016-existing-agent/tasks.md) |
| 017 | 只读环境预检、固定报告与隐私边界 | [任务与验证](017-preflight/tasks.md) |
| 018 | GitHub私有开发快照与验证入口 | [任务与验证](018-private-repository/tasks.md) |
| 019 | Trace已接收模型Token汇总与完整度 | [任务与验证](019-trace-usage/tasks.md) |
| 020 | 安全事件查询、组合筛选/分页、Trace关联与真实闭环 | [任务与验证](020-security-events/tasks.md) |
| 021 | 治理事件离线排查包：有界导出、JSONL/CSV/摘要与核验 | [任务与验证](021-security-export/tasks.md) |
| 022 | 策略开发工作台：文件检查、决策解释、批量用例和Runtime对照 | [任务与验证](022-policy-workbench/tasks.md) |
| 023 | 策略变更影响评估：规则差异、用例前后行为与CI审查报告 | [任务与验证](023-policy-comparison/tasks.md) |
| 024 | 历史治理事件候选策略回放：真实导出、离线求值与Trace关联 | [任务与验证](024-event-policy-replay/tasks.md) |
| 025 | 已有Agent统一接入：配置/生命周期/检查、真实框架与平台闭环 | [任务与验证](025-application-onboarding/tasks.md) |
| 026 | 配置中的人工审核：强制reviewed模式、独立审核与单次恢复 | [任务与验证](026-configured-review/tasks.md) |
| 027 | 配置持久化审批图：真实LangGraph、独立审核、同步/异步跨进程恢复并继续 | [任务与验证](027-configured-graph/tasks.md) |
| 028 | 统一图调用与流生命周期：四种调用、模型/受控工具闭环、关闭/取消/清理与平台验收 | [任务与验证](028-managed-graph-stream/tasks.md) |
| 029 | 前端数据工作台：统一视觉、五类页面、导航/响应式与真实浏览器验收 | [任务与验证](029-dashboard-design/tasks.md) |
| 030 | 前端工作流：本页审核队列、渐进筛选、详情阅读与复制反馈 | [任务与验证](030-dashboard-workflows/tasks.md) |
| 031 | Trace阅读工作台：节点搜索/视图筛选、键盘与会话密度 | [任务与验证](031-trace-reading/tasks.md) |
| 032 | 前端质量入口：单测/类型/构建、产物预算、CI与生产预览 | [任务与验证](032-dashboard-quality/tasks.md) |
| 033 | 前端状态：模块加载/失败恢复、旧结果刷新标记与未知计数 | [任务与验证](033-dashboard-states/tasks.md) |
| 034 | 前端阅读质量：受测对比度、点击目标、焦点与窄屏核对 | [任务与验证](034-dashboard-accessibility/tasks.md) |
| 035 | 可复现Dashboard演示：合成模型/治理/待审核数据与完整回归 | [任务与验证](035-dashboard-demo/tasks.md) |
| 036 | 安全事件本页JSONL/CSV下载、精度/范围与真实浏览器文件验收 | [任务与验证](036-security-page-export/tasks.md) |
| 037 | Trace首屏/紧凑用量、原生查询披露与窄屏完整工作流 | [任务与验证](037-dashboard-hierarchy/tasks.md) |
| 038 | 审批本页排序、完整日期/快照、绑定披露与确认重置 | [任务与验证](038-review-reading/tasks.md) |
| 039 | Trace节点深链、规范复制、同Trace请求复用与重新认证定位 | [任务与验证](039-trace-node-links/tasks.md) |
| 040 | 已接收调用耗时排行、精确排序/比例、节点定位与排查指南 | [任务与验证](040-call-duration/tasks.md) |
| 046 | 首次私有 GitHub 交付，检查实际暂存和提交内容 | [任务与验证](046-private-github/tasks.md) |
| 045 | Policy第三决策、配置策略工具与人工审批/单次恢复完整闭环 | [任务与验证](045-policy-approval/tasks.md) |
| 044 | 事件Span定位与Trace详情显式返回来源查询，独立认证与旧链接兼容 | [任务与验证](044-trace-return/tasks.md) |
| 043 | 两列表查询地址、复制/历史/刷新认证、UTC边界与窄屏滚动 | [任务与验证](043-query-links/tasks.md) |
| 042 | Collector只读诊断、健康/就绪/凭证/指定Trace与治理页 | [任务与验证](042-platform-diagnostics/tasks.md) |
| 041 | 私有快照统一验收、独立结果、失败闭锁与候选源摘要 | [任务与验证](041-snapshot-check/tasks.md) |

001、002 已完成代码、自动化与本地部署验证。003 实现原生 Trace 可视化，部署验收以其任务记录为准。004 完成官方 SDK 离线契约、真实存储与浏览器验证，真实 Provider 由用户安排另行验收。006 已完成首批 LangGraph 显式接入；007 已完成 stream / astream 状态流和平台验收。008 已完成独立环境快速开始、缓存安装及 Docker 恢复后的平台/页面续验；人工修改与在线下载仍未验收；事件投影和恢复分别设计。

005 已完成 DeepSeek 离线代码/平台/界面验证，用户明确批准后的 6 个真实 Chat 请求也全部成功。证据限定于 DeepSeek 当前别名、关闭 thinking、合成工具和 Chat API，不扩展为 OpenAI Provider 或成熟框架验收。

SPEC-009 实现最小 Runtime / Policy 控制并验证拒绝时工具零执行；完整审批与恢复仍需独立 spec。新受控工具 mapping 不改变旧 SDK 标签行为，身份来自显式可信宿主。

SPEC-010 的审批记录不执行工具或覆盖 Runtime；恢复执行和单次领取仍为下一增量。

SPEC-011 使用独立新协议/显式ReviewedTool，旧010不升权；仅同步JSON具名工具，异步/图恢复和策略DSL require_approval尚未交付。

SPEC-012复用011协议扩展异步函数，验证取消发生于服务端已提交后的保守未知结果，不增加迁移。图checkpoint恢复继续独立设计。

SPEC-013交付单个同步根interrupt，复用现有审批协议；InMemorySaver证明同进程对象重建，跨进程持久恢复单独验收。

SPEC-014交付本机SqliteSaver和独立进程，保守保持消费动作；生产多机后端/异步图/收据重建仍独立验收。

SPEC-015扩展本机单宿主原生异步图；沿用014格式、011协议与四迁移。多机/多中断/完成收据恢复仍独立设计。

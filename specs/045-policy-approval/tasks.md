# SPEC-045 任务

状态：已验证，2026-10-29。本轮仅完成SPEC-045，停止后不启动下一项。

- [x] 冻结完整范围与兼容/失败契约。
- [x] Policy v2、工作台/比较/回放。
- [x] 治理v2、Collector查询与Dashboard。
- [x] 配置v4与同步/异步策略工具、票据恢复。
- [x] 原生/真实LangGraph完整示例与独立安装。
- [x] 故障矩阵、真实PG/浏览器及全部回归。
- [x] 指南、兼容快照与验收记录。

## 完整能力与验收

| 契约 | 已实现与证据 |
| --- | --- |
| AC4501 | Policy v2三分支与优先级；旧v1拒绝新规则，摘要/指纹不变；case、check/explain/compare及历史事件回放支持第三决策与版本化报告。Policy 24、CLI契约76项回归通过。 |
| AC4502 | 配置v4显式policy工具，同步/异步allow直接返回、deny零执行、require_approval只返回票据。无客户端/未披露完整参数不绑定，最后allow复查变化也不执行。Runtime 126项通过。 |
| AC4503 | 恢复前核对完整票据/当前绑定，原永久claim只消费一次；待定/拒绝/过期、参数/策略/版本变化、并发、准备/领取/确认响应丢失、部分失败和取消均实际验证。四个新增真实PG方法包含完整矩阵；旧强制reviewed不因allow绕过审批。 |
| AC4504 | 治理v2 request/execute，严格effect/reason/phase/outcome/status；SDK 59、Collector 34项通过。导出8条第三决策事件并离线核验/回放；当前OpenAPI除两个枚举新增值外与020一致，011兼容继续检查；四迁移与依赖锁保持。 |
| AC4505 | 原生/真实StateGraph × 同步/异步 × 三种身份，独立进程request/resume，真实HTTP/PG计数。核心与异步图profile用新wheel和官方缓存独立安装，以-I -S运行并逐字节核对库源码；Policy独立环境无SDK/第三方依赖也可解释v2。 |

完整统一检查见本机 `artifacts/spec045/final/result.json`，不是继承旧SPEC结果：376 Python（59 SDK、24 Policy、126 Runtime、34 Collector、76契约、57真实PG）及102前端，共478项，零失败/错误/跳过。前端类型、生产构建及资源预算通过。统一运行前后584个候选文件摘要相同；后续仅补充本验收文件与文档状态，原摘要不冒称覆盖归档后的文档字节。机器记录见[validation.json](validation.json)。

首轮 `artifacts/spec045/verification` 未通过：既有平台诊断测试的Windows测试服务器未按时清理。修复测试夹具的有界关机、Windows Selector事件循环和异常后的schema清理；定向两次干净通过，之后完整统一回归通过。首轮记录保留，不计入通过证据。确认无存活进程后仅清理该轮遗留的专用测试schema，没有重置既有演示数据。

## 实际页面闭环

独立安装的异步StateGraph生成Action `d01c1edc200d4b268a65e3cb11d9ce70`。在本机5199生产preview展开全部参数并确认批准，此时合成业务文件仍不存在；新宿主进程resume后仅一行，再次resume被拒且不新增。页面显示已确认完成；按Action查询得到原请求“待审批快照”和执行“已完成”两条事件，各自定位正确Trace/Span。原请求节点明确不执行工具且不入耗时排行，Agent返回票据不显示成工具已执行；390px和键盘返回原精确查询通过。

045验收使用独立Collector 8859与PG schema `ui045`；原ui029服务/数据保留。截图在本机 `artifacts/ui045/`：`review-pending.png`、`review-completed.png`、`action-events.png`、`request-node.png`、`request-mobile.png`、`events-mobile.png`。请求Span `00ca5d5c01384c71`，执行Span `569d326515659944`，以Action关联，不伪造跨进程同一Trace。

## 边界

示例没有LLM调用，图是显式request/resume驱动，持久的是审批票据；它不宣称LangGraph checkpointer恢复。旧二元Dashboard/导出客户端需要随Collector升级才能读取第三决策；历史等待事件不是当前待办状态。尚未交付生产身份/租户、多interrupt、多机协调或跨系统恰好一次。独立安装验证是本机缓存离线安装，不能替代在线首次接入耗时验收。本轮无模型请求、GitHub远端、提交、推送或发布。

# SPEC-024 任务

状态：已验证，2026-10-25。

- [x] 冻结真实事件到候选决策的完整工作流及信任边界。
- [x] 验证快照API、回放脚本和保守报告/退出码。
- [x] 故障/分类/真实SDK-HTTP-PG导出与停服回放验收。
- [x] 操作示例、独立依赖验证、全回归和环境清理证据。

## 完整交付

同一次读取的已验证事件快照API、离线回放CLI、保守状态/退出码、来源摘要与关联结果、真实导出流程及示例一起交付。无Policy/Runtime/Collector执行语义或服务协议变化。

新增9方法（契约8、真实PG1），原305全部重跑：263 Python（SDK59、Policy20、Runtime67、Collector32、契约43、真实PG42）与51前端，共314方法全部通过，无失败/错误/跳过；子场景和进程不重复计数。机器结果见[validation.json](validation.json)。

| AC | 实测证据 |
| --- | --- |
| 2401 | read_bundle返回已验证manifest/rows，verify_bundle旧接口不变；回放对三个文件各读取一次；损坏/超限先于Policy求值失败，源文件不改，输出保护/错误隐私及真实CLI 0/1/2退出码通过 |
| 2402 | 受控6事件覆盖放宽1/收紧2/原因变化1/不变2，保留error/cancelled与1790000000000000001纳秒；同Action不同Trace/Span不合并；缺配置/历史policy_error、仅revision变化、空包和未出现过输入的边界核对 |
| 2403 | 真实SDK Agent→OTLP HTTP→Collector/PG，25尝试/50Span/15业务调用，导出25事件后停止服务。离线允许候选得放宽5/不变20，revision差异25；空规则候选得收紧15/原因变化5/不变5，25事件关联唯一，原outcome保持完成5/拒绝10/异常5/取消5 |

独立target复用023 Policy wheel，在-I/-S进程中只显式加入仓库脚本路径与Policy target，6事件回放成功；断言未导入SDK/Runtime/Collector/OTel，无第三方依赖。首次受限进程无法读取先前安装目录而失败；在与安装阶段相同的授权环境复验通过，未修改产品逻辑绕过验证。没有新Policy wheel或镜像构建声明。

本机明细：artifacts/check/result.json与tests.log、artifacts/event-policy-replay-frontend.json、artifacts/event-policy-replay/isolated.json、docker.json和合成独立运行报告。62 pins、44来源、两平台缓存哈希与历史59条收据保持；OpenAPI精确为020，旧011兼容测试保持，pip check、文档/候选源码检查通过。

专用aegis-spec024-check健康、测试schema清零后关闭容器/网络，卷保留，用户现有服务未改。SDK/Policy/Runtime/Collector/UI源码不改，前端测试重跑，类型/构建/页面证据继承020，Policy安装包继承023。无LLM请求、策略自动部署、审批执行、GitHub远端/推送或远端CI。

边界：应用遥测及清单不是可信完整审计；相同revision不证明相同历史配置。退出0只针对非空包内已接收事件，不证明全空间等价或部署批准。候选只产生决策，不产生原工具结果，也不解除审批领取。

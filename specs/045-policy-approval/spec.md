# SPEC-045：策略驱动的人工审批闭环

2026-10-29设计冻结。本SPEC交付Policy→配置宿主→同步/异步工具→审批准备/独立人工决定→显式单次恢复→平台排查与离线策略工具的完整场景，不拆成按钮增量。真实模型请求不在本轮；每次继续一个SPEC，完成后停止。

AC4501 Policy v2增加require_approval/explicit_require_approval，优先级deny>require_approval>allow，相同级按rule id。旧v1拒绝第三种规则，旧求值和指纹/审批摘要字节保持。Case v2、check/explain/compare/replay支持第三种决策；收紧程度deny<require_approval<allow。未知版本/无匹配/错误仍失败关闭，不自动部署策略。

AC4502 Application v4新增execution=policy及policy_tool。旧v1-v3不接收policy模式或v2策略。单一显式绑定在invoke(JSON具名参数,summary)时allow返回执行结果、deny抛ActionDenied且函数零执行、require_approval返回PendingReview票据且函数零执行；必须预先提供独立审批客户端、工具版本与完整参数披露，禁止缺客户端回退。固定参数/default快照和显式action_id可重用准备，宿主负责保存票据。原direct遇到第三决策失败关闭；原reviewed/reviewed_graph仍强制审批，不因allow自动执行。

AC4503 PendingReview保存原审批record；resume(record,arguments,summary)重新构建当前工具/策略/参数完整绑定并在领取前验证票据，复用永久单次claim/complete，绝不把record当授权。批准/未过期/当前策略允许allow或require_approval才可能执行；拒绝、待定、过期、篡改、版本/策略/摘要改变均零执行。并发最多一次，领取/确认响应丢失保守unknown且不重试业务，异步取消保持传播与消费事实。原协议/单次恢复保持；新prepare可显式绑定Trace/Span以关联规则与审批，不改变旧默认None。

AC4504 治理映射v2保留第三决策和rule/revision/action，phase=request/execute；request正常结尾awaiting_approval，execute正常completed，异常/取消error/cancelled。普通allow/deny仍发原v1。Collector严格校验新映射并通过现有存储追加接受，安全事件API枚举追加新effect/outcome、固定字段保持。Dashboard展示需审批、待审批/流程异常及关联规则，审批记录按Action ID关联请求/执行治理事件与其Trace；输入输出/完整参数不进入遥测。导出/核验/离线回放、筛选和页面下载同步支持新决策。审批本体仍由现有记录提供真实状态，遥测等待事件是发生时快照，不冒称实时状态。

AC4505 原生与真实LangGraph同步/异步离线示例，合成工具、无LLM；外部驱动保存票据并显式恢复，图不通过重跑请求节点恢复工具。实际SDK/HTTP/PostgreSQL及Dashboard核对待定/批准/拒绝/超时/篡改/策略或工具版本变化/并发/故障与取消；离线策略检查/比较/导出回放与独立安装验收。全Python/真实PG、完整前端/类型/构建/预算、旧OpenAPI兼容及迁移不变一起检查。新增协议以045快照为当前基线，原020仅枚举有意追加，旧端点/字段不得删改。未交付生产身份、多租户或多机恰好一次。

绑定细化：策略入口的审批record沿用trace_id/span_id=None，以Action ID关联治理事件。这样同一action_id在导出开启时重复准备不会因新Span改变审批绑定；审核页提供Action精确事件入口，再进入原请求Trace。底层新增显式Trace绑定选项时，调用方须保存并复用原标识，不能把重试产生的新Span当原绑定。
